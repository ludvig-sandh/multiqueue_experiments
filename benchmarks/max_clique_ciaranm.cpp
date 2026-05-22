#include "util/build_info.hpp"

#include "cxxopts.hpp"

#include <clique/dimacs.hh>
#include <clique/max_clique_params.hh>
#include <clique/tbmcsa1_max_clique.hh>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

struct Settings {
    int num_threads = 4;
    int batch_size = 1; // Accepted for benchmark-script compatibility.
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

void benchmark_ciaranm(Settings const& settings) {
    std::clog << "Reading instance...\n";
    clique::Graph graph = clique::read_dimacs(settings.instance_file.string());

    clique::MaxCliqueParams params;
    params.n_threads = static_cast<unsigned>(settings.num_threads);
    params.abort.store(false);

    std::clog << "Working...\n";
    params.start_time = std::chrono::steady_clock::now();
    clique::MaxCliqueResult result = clique::tbmcsa1_max_clique(graph, params);
    auto t_end = std::chrono::steady_clock::now();
    auto work_time = std::chrono::duration_cast<std::chrono::nanoseconds>(t_end - params.start_time);

    std::clog << "Done\n\n";
    std::clog << "= Results =\n";
    std::clog << "Time (s): " << std::fixed << std::setprecision(3)
              << std::chrono::duration<double>(work_time).count() << '\n';
    std::clog << "Solution: " << result.size << '\n';
    std::clog << "Processed nodes: " << result.nodes << '\n';
    std::clog << "Average PQ size: n/a\n";
    std::clog << "Max PQ size: n/a\n";

    std::cout << '{';
    std::cout << std::quoted("settings") << ':';
    write_settings_json(settings, std::cout);
    std::cout << ',';
    std::cout << std::quoted("results") << ':';
    std::cout << '{';
    std::cout << std::quoted("time_ns") << ':' << work_time.count() << ',';
    std::cout << std::quoted("solution") << ':' << result.size << ',';
    std::cout << std::quoted("processed_nodes") << ':' << result.nodes;
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
    if (settings.num_threads <= 0) {
        std::cerr << "Error: Number of threads must be positive" << '\n';
        return EXIT_FAILURE;
    }

    try {
        std::clog << "= Running benchmark =\n";
        benchmark_ciaranm(settings);
    } catch (std::exception const& e) {
        std::cerr << "Error running benchmark: " << e.what() << '\n';
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
