#pragma once

#include "util.hpp"

#include "multififo/relaxed_concurrent_fifo/contenders/multififo/multififo.hpp"

#include <cstddef>
#include <cxxopts.hpp>
#include <iomanip>
#include <optional>
#include <ostream>
#include <utility>

namespace wrapper::multilifo {

#ifdef MULTILIFO_NUM_POP_CANDIDATES
static constexpr int num_pop_candidates = MULTILIFO_NUM_POP_CANDIDATES;
#else
static constexpr int num_pop_candidates = 2;
#endif

using mode_type = ::multififo::mode::StickRandom<num_pop_candidates>;

template <bool Min, typename Key = unsigned long, typename T = Key>
class MultiLifo {
   public:
    using key_type = Key;
    using mapped_type = T;
    using value_type = std::pair<key_type, mapped_type>;

   private:
    using pq_type = ::multififo::MultiLifo<value_type, mode_type>;

    struct Settings {
        int factor = 2;
        int stickiness = 16;
        int seed = 1;

        void register_cmd_options(cxxopts::Options& cmd) {
            cmd.add_options()("c,queue-factor", "The number of queues per thread", cxxopts::value<int>(factor),
                              "NUMBER");
            cmd.add_options()("k,stickiness", "The stickiness period", cxxopts::value<int>(stickiness), "NUMBER");
            cmd.add_options()("multilifo-seed", "Seed for the multilifo", cxxopts::value<int>(seed), "NUMBER");
        }

        [[nodiscard]] bool validate() const {
            if (factor <= 0) {
                std::cerr << "Error: Queue factor must be at least 1\n";
                return false;
            }
            if (stickiness <= 0) {
                std::cerr << "Error: Stickiness must be at least 1\n";
                return false;
            }
            return true;
        }

        void write_human_readable(std::ostream& out) const {
            out << "Queue factor: " << factor << '\n';
            out << "Stickiness: " << stickiness << '\n';
            out << "Seed: " << seed << '\n';
        }

        void write_json(std::ostream& out) const {
            out << '{';
            out << std::quoted("queue_factor") << ':' << factor << ',';
            out << std::quoted("stickiness") << ':' << stickiness << ',';
            out << std::quoted("seed") << ':' << seed;
            out << '}';
        }
    };

    class Handle {
        friend MultiLifo;

        typename pq_type::handle handle_;

        explicit Handle(typename pq_type::handle&& handle) : handle_(std::move(handle)) {
        }

       public:
        bool push(value_type const& value) {
            return handle_.push(value);
        }

        std::optional<value_type> try_pop() {
            return handle_.pop();
        }
    };

   public:
    using handle_type = Handle;
    using settings_type = Settings;

   private:
    pq_type pq_;

   public:
    explicit MultiLifo(int num_threads, std::size_t initial_capacity, Settings const& settings)
        : pq_{num_threads, initial_capacity, settings.factor, settings.stickiness, settings.seed} {
        (void)Min;
    }

    static void write_human_readable(std::ostream& out) {
        out << "MultiLifo\n";
        out << "  Mode: stick_random\n";
        out << "  Pop candidates: " << num_pop_candidates << '\n';
    }

    handle_type get_handle() {
        return handle_type{pq_.get_handle()};
    }
};

}  // namespace wrapper::multilifo
