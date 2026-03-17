#include "util/bnb_problem.hpp"
#include "util/build_info.hpp"
#include "util/knapsack_instance.hpp"
#include "util/knapsack_problem.hpp"

#include "cxxopts.hpp"

#include <chrono>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <queue>
#include <vector>


struct Settings {
    std::filesystem::path instance_file;
};

void register_cmd_options(Settings& settings, cxxopts::Options& cmd) {
    cmd.add_options()("instance", "The instance file", cxxopts::value<std::filesystem::path>(settings.instance_file),
                      "PATH");
    cmd.parse_positional({"instance"});
}

void write_settings_human_readable(Settings const& settings, std::ostream& out) {
    out << "Instance file: " << settings.instance_file << '\n';
}

void write_settings_json(Settings const& settings, std::ostream& out) {
    out << '{';
    out << std::quoted("instance_file") << ':' << settings.instance_file;
    out << '}';
}

template <class Problem>
void branch_and_bound(Settings const& settings) noexcept {
    using node_type = typename Problem::node_type;
    using compare_type = typename Problem::Compare;
    using instance_type = typename Problem::instance_type;

    long long processed_nodes{0};
    std::size_t sum_sizes{0};
    std::size_t max_size{0};

    instance_type instance;
    std::clog << "Reading instance...\n";
    try {
        instance = instance_type(settings.instance_file);
    } catch (std::exception const& e) {
        std::cerr << "Error reading instance file: " << e.what() << '\n';
        std::exit(EXIT_FAILURE);
    }
    std::clog << "Instance has " << instance.size() << " items and " << std::fixed << instance.capacity()
              << " capacity\n";

    Problem problem(instance);

    std::vector<node_type> container, kids;
    container.reserve(1 << 24);
    kids.reserve(1 << 20);
    std::priority_queue<node_type, std::vector<node_type>, compare_type> pq({}, std::move(container));

    std::clog << "Working...\n";
    auto t_start = std::chrono::steady_clock::now();
    
    auto root = problem.root();
    auto incumbent = root.lower_bound;

    if (root.upper_bound > incumbent) {
        pq.push(root);
    }
    
    while (!pq.empty()) {
        auto node = pq.top();
        sum_sizes += pq.size();
        pq.pop();

        if (node.upper_bound <= incumbent) {
            // for best-first, this implies all remaining nodes are also <= incumbent, so safe to break
            break;
        }

        kids.clear();
        problem.branch(node, incumbent, kids);

        for (auto& c : kids) {
            if (c.lower_bound > incumbent) {
                incumbent = c.lower_bound;
            }
            if (c.upper_bound > incumbent) {
                pq.push(std::move(c));
            }
        }

        max_size = std::max(max_size, pq.size());
        ++processed_nodes;
    }

    auto t_end = std::chrono::steady_clock::now();

    std::clog << "Done\n\n";
    std::clog << "= Results =\n";
    std::clog << "Time (s): " << std::fixed << std::setprecision(3)
              << std::chrono::duration<double>(t_end - t_start).count() << '\n';
    std::clog << "Solution: " << incumbent << '\n';
    std::clog << "Processed nodes: " << processed_nodes << '\n';
    std::clog << "Average PQ size: " << static_cast<double>(sum_sizes) / static_cast<double>(processed_nodes) << '\n';
    std::clog << "Max PQ size: " << max_size << '\n';

    std::cout << '{';
    std::cout << std::quoted("settings") << ':';
    write_settings_json(settings, std::cout);
    std::cout << ',';
    std::cout << std::quoted("instance") << ':';
    std::cout << '{';
    std::cout << std::quoted("num_items") << ':' << instance.size() << ',';
    std::cout << std::quoted("capacity") << ':' << std::fixed << instance.capacity();
    std::cout << '}' << ',';
    std::cout << std::quoted("results") << ':';
    std::cout << '{';
    std::cout << std::quoted("time_ns") << ':' << std::chrono::nanoseconds{t_end - t_start}.count() << ',';
    std::cout << std::quoted("processed_nodes") << ':' << processed_nodes << ',';
    std::cout << std::quoted("solution") << ':' << incumbent << ',';
    std::cout << std::quoted("average_pq_size") << ':'
              << static_cast<double>(sum_sizes) / static_cast<double>(processed_nodes) << ',';
    std::cout << std::quoted("max_pq_size") << ':' << max_size;
    std::cout << '}';
    std::cout << '}' << '\n';
}

int main(int argc, char* argv[]) {
    write_build_info(std::clog);
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
    Settings settings{};
    register_cmd_options(settings, cmd);

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

    std::clog << "= Settings =\n";
    write_settings_human_readable(settings, std::clog);
    std::clog << '\n';
    if (settings.instance_file.empty()) {
        std::cerr << "Error: No instance file specified" << '\n';
        std::cerr << "Use --help for usage information" << '\n';
        return EXIT_FAILURE;
    }
    std::clog << "= Running benchmark =\n";
    branch_and_bound<KnapsackProblem>(settings);
    return EXIT_SUCCESS;
}
