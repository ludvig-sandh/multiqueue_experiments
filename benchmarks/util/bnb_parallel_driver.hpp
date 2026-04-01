#pragma once

#include "build_info.hpp"
#include "selector.hpp"
#include "termination_detection.hpp"
#include "thread_coordination.hpp"

#include <cxxopts.hpp>

#include <atomic>
#include <cassert>
#include <chrono>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <numeric>
#include <type_traits>
#include <utility>
#include <vector>
#include <type_traits>


template <class Problem>
using pq_type = PQ<false, typename Problem::data_type, typename Problem::node_type>;

template <class Problem>
using pq_value = typename pq_type<Problem>::value_type;  // std::pair<key, payload>

template <class Problem>
struct RunConfig {
    int num_threads = 4;
    int batch_size = 1;
    std::filesystem::path instance_file{};
    typename pq_type<Problem>::settings_type pq_settings{};
};

template <class Problem>
void register_cmd_options(RunConfig<Problem>& cfg, cxxopts::Options& cmd) {
    // clang-format off
    cmd.add_options()
        ("j,threads", "The number of threads", cxxopts::value<int>(cfg.num_threads), "NUMBER")
        ("b,batch", "The size of a node batch", cxxopts::value<int>(cfg.batch_size), "NUMBER")
        ("instance", "Instance file", cxxopts::value<std::filesystem::path>(cfg.instance_file), "FILE");
    // clang-format on
    cfg.pq_settings.register_cmd_options(cmd);
    cmd.parse_positional({"instance"});
}

template <class Problem>
void write_settings_human_readable(RunConfig<Problem> const& cfg, std::ostream& out) {
    out << "Threads: " << cfg.num_threads << '\n';
    out << "Batch size: " << cfg.batch_size << '\n';
    out << "Instance file: " << cfg.instance_file << '\n';
    cfg.pq_settings.write_human_readable(out);
}

template <class Problem>
void write_settings_json(RunConfig<Problem> const& cfg, std::ostream& out) {
    out << '{';
    out << std::quoted("instance_file") << ':' << cfg.instance_file << ',';
    out << std::quoted("pq") << ':';
    cfg.pq_settings.write_json(out);
    out << '}';
}

struct Counter {
    long long pushed_nodes{0};
    long long processed_nodes{0};
    long long ignored_nodes{0};
};

template <class Problem>
struct SharedData {
    using data_type = typename Problem::data_type;
    using instance_type = typename Problem::instance_type;

    instance_type instance;
    Problem problem;  // holds a const ref to instance or pointer
    std::atomic<data_type> incumbent{0};
    termination_detection::TerminationDetection termination_detection;
    std::atomic_llong missing_nodes{0};

    SharedData(instance_type inst, int num_threads)
        : instance(std::move(inst)),
          problem(instance),
          incumbent(0),
          termination_detection(num_threads),
          missing_nodes(0) {}
};

template <class Problem>
void process_node(pq_value<Problem> const& item,
                  typename pq_type<Problem>::handle_type& handle,
                  Counter& counter,
                  SharedData<Problem>& data,
                  std::vector<typename Problem::node_type>& batch,
                  std::size_t batch_size) {
    auto incumbent = data.incumbent.load(std::memory_order_relaxed);
    auto const& first_node = item.second;
    if (first_node.upper_bound <= incumbent) {
        ++counter.ignored_nodes;
        return;
    }

    // Create a local batch of nodes to process, repeatedly bushing back children into it.
    // Stop when <batch size> nodes have been processed.
    batch.clear();
    batch.push_back(first_node);
    typename std::remove_reference<decltype(batch)>::type children;
    for (size_t i{0}; i < batch_size; ++i) {
        if (batch.empty()) {
            break;
        }
        auto const node = batch.back();
        batch.pop_back();

        if (node.upper_bound <= incumbent) {
            continue;
        }

        children.clear();
        data.problem.branch(node, incumbent, children);

        for (auto it = children.rbegin(); it != children.rend(); ++it) {
            auto& child = *it;
            while (child.lower_bound > incumbent) {
                if (data.incumbent.compare_exchange_weak(incumbent, child.lower_bound, std::memory_order_relaxed)) {
                    incumbent = child.lower_bound;
                    std::cout << "new best lower bound found: " << child.lower_bound << "\n";
                    std::cout << "pushed nodes: " << counter.pushed_nodes << ", processed: " << counter.processed_nodes << "\n";
                    break;
                }
            }

            auto child_ub = child.upper_bound;
            if (child_ub > incumbent) {
                batch.push_back(std::move(child));
            }
        }

    }

    // Push the rest of the batch (unprocessed nodes) into the shared PQ.
    for (auto& child : batch) {
        auto child_ub = child.upper_bound;
        if (child_ub > incumbent) {
            if (handle.push({child_ub, std::move(child)})) {
                ++counter.pushed_nodes;
            }
        }
    }

    ++counter.processed_nodes;
}

template <class Problem>
[[gnu::noinline]] Counter benchmark_thread(thread_coordination::Context& thread_context,
                                           pq_type<Problem>& pq,
                                           SharedData<Problem>& data,
                                           std::size_t batch_size) {
    Counter counter;
    auto handle = pq.get_handle();

    std::vector<typename Problem::node_type> children;

    if (thread_context.id() == 0) {
        auto root = data.problem.root();
        auto initial_best = root.lower_bound;
        data.incumbent.store(initial_best, std::memory_order_relaxed);

        auto root_ub = root.upper_bound;
        if (root_ub > initial_best) {
            handle.push({root_ub, std::move(root)});
            ++counter.pushed_nodes;
        }
    }

    thread_context.synchronize();
    while (true) {
        std::optional<pq_value<Problem>> item;
        
        while (data.termination_detection.repeat([&]() {
            item = handle.try_pop();
            return item.has_value();
        })) {
            process_node<Problem>(*item, handle, counter, data, children, batch_size);
        }

        data.missing_nodes.fetch_add(counter.pushed_nodes - counter.processed_nodes - counter.ignored_nodes,
                                     std::memory_order_relaxed);
        
        thread_context.synchronize();
        if (data.missing_nodes.load(std::memory_order_relaxed) == 0) {
            break;
        }
        thread_context.synchronize();

        if (thread_context.id() == 0) {
            data.missing_nodes.store(0, std::memory_order_relaxed);
            data.termination_detection.reset();
        }
        thread_context.synchronize();
    }
    return counter;
}

template <class Problem>
void run_benchmark(RunConfig<Problem> const& cfg) {
    using instance_type = typename Problem::instance_type;

    instance_type instance;
    std::clog << "Reading instance...\n";
    try {
        instance = instance_type(cfg.instance_file);
    } catch (std::exception const& e) {
        std::cerr << "Error reading instance file: " << e.what() << '\n';
        std::exit(EXIT_FAILURE);
    }
    // std::clog << "Instance has " << instance.size() << " items and " << std::fixed << instance.capacity()
            //   << " capacity\n";

    SharedData<Problem> shared_data{std::move(instance), cfg.num_threads};
    std::vector<Counter> thread_counter(static_cast<std::size_t>(cfg.num_threads));
    auto pq = pq_type<Problem>(cfg.num_threads, std::size_t(10'000'000), cfg.pq_settings);

    std::clog << "Working...\n";
    auto start_time = std::chrono::steady_clock::now();
    thread_coordination::Dispatcher dispatcher{cfg.num_threads, [&](auto ctx) {
                                                   auto t_id = static_cast<std::size_t>(ctx.id());
                                                   thread_counter[t_id] = benchmark_thread<Problem>(ctx, pq, shared_data,
                                                        static_cast<std::size_t>(cfg.batch_size));
                                               }};
    dispatcher.wait();
    auto end_time = std::chrono::steady_clock::now();
    std::clog << "Done\n";
    auto total_counts =
        std::accumulate(thread_counter.begin(), thread_counter.end(), Counter{}, [](auto sum, auto const& counter) {
            sum.pushed_nodes += counter.pushed_nodes;
            sum.processed_nodes += counter.processed_nodes;
            sum.ignored_nodes += counter.ignored_nodes;
            return sum;
        });
    std::clog << '\n';
    std::clog << "= Results =\n";
    std::clog << "Time (s): " << std::fixed << std::setprecision(3)
              << std::chrono::duration<double>(end_time - start_time).count() << '\n';
    std::clog << "Solution: " << shared_data.incumbent.load() << '\n';
    std::clog << "Processed nodes: " << total_counts.processed_nodes << '\n';
    std::clog << "Ignored nodes: " << total_counts.ignored_nodes << '\n';
    if (total_counts.processed_nodes + total_counts.ignored_nodes != total_counts.pushed_nodes) {
        std::cerr << "Warning: Not all nodes were popped\n";
        std::cerr << "Probably the priority queue discards duplicate keys\n";
    }
    std::cout << '{';
    std::cout << std::quoted("settings") << ':';
    write_settings_json(cfg, std::cout);
    std::cout << ',';
    // std::cout << std::quoted("instance") << ':';
    // std::cout << '{';
    // std::cout << std::quoted("num_items") << ':' << shared_data.instance.size() << ',';
    // std::cout << std::quoted("capacity") << ':' << std::fixed << shared_data.instance.capacity();
    // std::cout << '}' << ',';
    std::cout << std::quoted("results") << ':';
    std::cout << '{';
    std::cout << std::quoted("time_ns") << ':' << std::chrono::nanoseconds{end_time - start_time}.count() << ',';
    std::cout << std::quoted("processed_nodes") << ':' << total_counts.processed_nodes << ',';
    std::cout << std::quoted("ignored_nodes") << ':' << total_counts.ignored_nodes << ',';
    std::cout << std::quoted("solution") << ':' << shared_data.incumbent.load();
    std::cout << '}';
    std::cout << '}' << '\n';
}

template <class Problem>
int bnb_parallel_solver(int argc, char **argv) {
    write_build_info(std::clog);
    std::clog << '\n';

    std::clog << "= Priority queue =\n";
    pq_type<Problem>::write_human_readable(std::clog);
    std::clog << '\n';

    std::clog << "= Command line =\n";
    for (int i = 0; i < argc; ++i) {
        std::clog << argv[i];
        if (i != argc - 1) {
            std::clog << ' ';
        }
    }
    std::clog << '\n' << '\n';

    cxxopts::Options cmd(argv[0]);
    cmd.add_options()("h,help", "Print this help");

    RunConfig<Problem> cfg{};
    register_cmd_options(cfg, cmd);

    try {
        auto args = cmd.parse(argc, argv);
        if (args.count("help") > 0) {
            std::cerr << cmd.help() << '\n';
            return EXIT_SUCCESS;
        }
    } catch (cxxopts::OptionParseException const& e) {
        std::cerr << "Error parsing command line: " << e.what() << '\n';
        std::cerr << "Use --help for usage information" << '\n';
        return EXIT_FAILURE;
    }

    if (cfg.num_threads <= 0) {
        std::cerr << "Error: number of threads must be positive\n";
        return EXIT_FAILURE;
    }

    if (cfg.batch_size <= 0) {
        std::cerr << "Error: batch size must be positive\n";
        return EXIT_FAILURE;
    }

    std::clog << "= Settings =\n";
    write_settings_human_readable(cfg, std::clog);
    std::clog << '\n';

    if (cfg.instance_file.empty()) {
        std::cerr << "Error: No instance file specified" << '\n';
        std::cerr << "Use --help for usage information" << '\n';
        return EXIT_FAILURE;
    }

    std::clog << "= Running benchmark =\n";
    run_benchmark<Problem>(cfg);
    return EXIT_SUCCESS;
}
