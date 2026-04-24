#include "util/problems/bnb_problem.hpp"
#include "util/build_info.hpp"

#include "cxxopts.hpp"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <stack>
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

    Problem problem(instance);

    std::vector<node_type> children;
    children.reserve(1 << 20);
    std::stack<node_type> stack;

    std::clog << "Working...\n";
    auto t_start = std::chrono::steady_clock::now();

    auto root = problem.root();
    auto incumbent = root.lower_bound;
    stack.push(std::move(root));

    while (!stack.empty()) {
        auto node = stack.top();
        sum_sizes += stack.size();
        stack.pop();

        if (node.upper_bound <= incumbent) {
            continue;
        }

        children.clear();
        problem.branch(node, incumbent, children);
        std::reverse(children.begin(), children.end());

        for (auto& child : children) {
            if (child.lower_bound > incumbent) {
                incumbent = child.lower_bound;
            }
            if (child.upper_bound > incumbent) {
                stack.push(std::move(child));
            }
        }

        max_size = std::max(max_size, stack.size());
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

template <class Problem>
int bnb_sequential_stack_solver(int argc, char **argv) {
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
    branch_and_bound<Problem>(settings);
    return EXIT_SUCCESS;
}
