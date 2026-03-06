#include "util/bnb_problem.hpp"
#include "util/build_info.hpp"
#include "util/max_clique_problem.hpp"

#include "cxxopts.hpp"

#include <bit>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>
#include <queue>
#include <chrono>
#include <iomanip>
#include <iostream>


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
    using data_type = typename Problem::data_type;
    using node_type = typename Problem::node_type;
    using instance_type = typename Problem::instance_type;
    using pq_item = std::pair<data_type, node_type>;
    struct PQCompare {
        bool operator()(pq_item const& a, pq_item const& b) const noexcept { return a.first < b.first; }
    };

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

    Problem problem(instance);

    std::vector<pq_item> container;
    std::vector<node_type> kids;
    container.reserve(1 << 24);
    kids.reserve(1 << 20);
    std::priority_queue<pq_item, std::vector<pq_item>, PQCompare> pq(PQCompare{}, std::move(container));

    std::clog << "Working...\n";
    auto t_start = std::chrono::steady_clock::now();
    
    auto [root, best_value] = problem.root();
    std::cout << best_value << "\n";
    auto root_ub = problem.bounds(root).upper;
    pq.push({root_ub, std::move(root)});
    auto t_temp = std::chrono::steady_clock::now();
    
    while (!pq.empty()) {
        auto item = std::move(pq.top());
        sum_sizes += pq.size();
        pq.pop();
        auto node_ub = item.first;
        auto node = std::move(item.second);

        if (processed_nodes % 100 == 0) {
            auto t_now = std::chrono::steady_clock::now();
            auto diff = std::chrono::duration<double>(t_now - t_temp).count();
            if (diff >= 1) {
                t_temp = t_now;
                std::cout << "Processed nodes: " << processed_nodes << "\n";
            }
        }

        auto [lower, upper] = problem.bounds(node);
        if (node_ub <= best_value) {
            continue;
        }
        if (upper <= best_value) {
            continue;
        }

        if (lower > best_value) {
            std::cout << "new best lower bound found: " << lower << "\n";
            best_value = lower;
        }

        problem.children(node, best_value, kids);
        for (auto& c : kids) {
            pq.push({c.upper_bound, std::move(c)});
        }

        max_size = std::max(max_size, pq.size());
        ++processed_nodes;
    }

    auto t_end = std::chrono::steady_clock::now();

    std::clog << "Done\n\n";
    std::clog << "= Results =\n";
    std::clog << "Time (s): " << std::fixed << std::setprecision(3)
              << std::chrono::duration<double>(t_end - t_start).count() << '\n';
    std::clog << "Solution: " << best_value << '\n';
    std::clog << "Processed nodes: " << processed_nodes << '\n';
    std::clog << "Average PQ size: " << static_cast<double>(sum_sizes) / static_cast<double>(processed_nodes) << '\n';
    std::clog << "Max PQ size: " << max_size << '\n';

    std::cout << '{';
    std::cout << std::quoted("settings") << ':';
    write_settings_json(settings, std::cout);
    std::cout << ',';
    std::cout << std::quoted("instance") << ':';
    std::cout << std::quoted("results") << ':';
    std::cout << '{';
    std::cout << std::quoted("time_ns") << ':' << std::chrono::nanoseconds{t_end - t_start}.count() << ',';
    std::cout << std::quoted("processed_nodes") << ':' << processed_nodes << ',';
    std::cout << std::quoted("solution") << ':' << best_value << ',';
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
    branch_and_bound<MaxCliqueProblem>(settings);
    return EXIT_SUCCESS;
}
