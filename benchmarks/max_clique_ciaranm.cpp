#include "util/build_info.hpp"

#include "cxxopts.hpp"

#include <clique/max_clique_params.hh>
#include <clique/tbmcsa1_max_clique.hh>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <fstream>
#include <iostream>
#include <sstream>
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

clique::Graph read_dimacs(std::filesystem::path const& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("unable to open instance file: " + path.string());
    }

    clique::Graph graph;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) {
            continue;
        }

        std::istringstream line_stream(line);
        char type = '\0';
        line_stream >> type;
        if (!line_stream || type == 'c') {
            continue;
        }

        if (type == 'p') {
            std::string format;
            int num_vertices = 0;
            int num_edges = 0;
            if (!(line_stream >> format >> num_vertices >> num_edges) || (format != "edge" && format != "col")) {
                throw std::runtime_error("invalid DIMACS problem line: " + line);
            }
            if (graph.size() != 0) {
                throw std::runtime_error("multiple DIMACS problem lines in: " + path.string());
            }
            graph.resize(num_vertices);
            continue;
        }

        if (type == 'e') {
            int a = 0;
            int b = 0;
            if (!(line_stream >> a >> b)) {
                throw std::runtime_error("invalid DIMACS edge line: " + line);
            }
            if (a <= 0 || b <= 0 || a > graph.size() || b > graph.size()) {
                throw std::runtime_error("DIMACS edge index out of bounds: " + line);
            }
            if (a == b) {
                throw std::runtime_error("DIMACS self-loop: " + line);
            }
            graph.add_edge(a - 1, b - 1);
            continue;
        }

        throw std::runtime_error("invalid DIMACS line: " + line);
    }

    if (!in.eof()) {
        throw std::runtime_error("error reading instance file: " + path.string());
    }

    return graph;
}

void benchmark_ciaranm(Settings const& settings) {
    std::clog << "Reading instance...\n";
    clique::Graph graph = read_dimacs(settings.instance_file);

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
