#include "util/build_info.hpp"
#include "libpmc.h"

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
#include <stack>
#include <chrono>
#include <iomanip>
#include <iostream>


struct Settings {
    int num_threads = 4;
    int batch_size = 1; // Dummy value
    std::filesystem::path instance_file;
};

void register_cmd_options(Settings& settings, cxxopts::Options& cmd) {
    cmd.add_options()
        ("j,threads", "The number of threads", cxxopts::value<int>(settings.num_threads), "NUMBER")
        ("b,batch", "Ignored batch size option", cxxopts::value<int>(settings.batch_size), "NUMBER")
        ("instance", "The instance file", cxxopts::value<std::filesystem::path>(settings.instance_file),
                      "PATH");
    cmd.parse_positional({"instance"});
}

void write_settings_human_readable(Settings const& settings, std::ostream& out) {
    out << "Threads: " << settings.num_threads << '\n';
    out << "Instance file: " << settings.instance_file << '\n';
}

void write_settings_json(Settings const& settings, std::ostream& out) {
    out << '{';
    out << std::quoted("instance_file") << ':' << settings.instance_file;
    out << '}';
}

void benchmark_pmc(Settings const& settings) noexcept {
    std::clog << "Working...\n";

    auto t_start = std::chrono::steady_clock::now();

    // Replace 1 with your benchmark thread setting once you add it to Settings,
    // e.g. settings.num_threads.
    int best_value = max_clique_size_from_file(settings.instance_file.c_str(), settings.num_threads);

    auto t_end = std::chrono::steady_clock::now();

    if (best_value < 0) {
        std::cerr << "Error reading or solving instance file: " << settings.instance_file << '\n';
        std::exit(EXIT_FAILURE);
    }

    std::clog << "Done\n\n";
    std::clog << "= Results =\n";
    std::clog << "Time (s): " << std::fixed << std::setprecision(3)
              << std::chrono::duration<double>(t_end - t_start).count() << '\n';
    std::clog << "Solution: " << best_value << '\n';
    std::clog << "Processed nodes: n/a\n";
    std::clog << "Average PQ size: n/a\n";
    std::clog << "Max PQ size: n/a\n";

    std::cout << '{';
    std::cout << std::quoted("settings") << ':';
    write_settings_json(settings, std::cout);
    std::cout << ',';
    std::cout << std::quoted("results") << ':';
    std::cout << '{';
    std::cout << std::quoted("time_ns") << ':'
              << std::chrono::nanoseconds{t_end - t_start}.count() << ',';
    std::cout << std::quoted("solution") << ':' << best_value;
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
    benchmark_pmc(settings);
    return EXIT_SUCCESS;
}
