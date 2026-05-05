#pragma once

#include "2d-stacks/wrapper.hpp"

#include <atomic>
#include <cstddef>
#include <cxxopts.hpp>
#include <iomanip>
#include <iostream>
#include <memory>
#include <optional>
#include <ostream>
#include <stdexcept>
#include <string>
#include <utility>

namespace wrapper::two_d_stack {

template <bool Min, typename Key = unsigned long, typename T = Key>
class TwoDStack {
   public:
    using key_type = Key;
    using mapped_type = T;
    using value_type = std::pair<key_type, mapped_type>;

    struct Settings {
        std::uint64_t width = 64;
        std::uint64_t depth = 1024;

        void register_cmd_options(cxxopts::Options& cmd) {
            cmd.add_options()("two-d-width", "The 2D stack width", cxxopts::value<std::uint64_t>(width), "NUMBER");
            cmd.add_options()("two-d-depth", "The 2D stack depth", cxxopts::value<std::uint64_t>(depth), "NUMBER");
        }

        [[nodiscard]] bool validate() const {
            if (width == 0) {
                std::cerr << "Error: 2D stack width must be at least 1\n";
                return false;
            }
            if (depth == 0) {
                std::cerr << "Error: 2D stack depth must be at least 1\n";
                return false;
            }
            return true;
        }

        void write_human_readable(std::ostream& out) const {
            out << "2D stack width: " << width << '\n';
            out << "2D stack depth: " << depth << '\n';
        }

        void write_json(std::ostream& out) const {
            out << '{';
            out << std::quoted("width") << ':' << width << ',';
            out << std::quoted("depth") << ':' << depth;
            out << '}';
        }
    };

   private:
    class Handle {
        friend TwoDStack;

        ::TwoDimStack::Handle handle_;

        explicit Handle(::TwoDimStack::Handle&& handle) : handle_(std::move(handle)) {
        }

       public:
        bool push(value_type const& value) {
            auto item = std::make_unique<value_type>(value);
            handle_.push(item.get());
            item.release();
            return true;
        }

        std::optional<value_type> try_pop() {
            std::unique_ptr<value_type> value{static_cast<value_type*>(handle_.pop())};
            if (!value) {
                return std::nullopt;
            }
            return *value;
        }
    };

   public:
    using handle_type = Handle;
    using settings_type = Settings;

   private:
    static std::uint64_t require_positive(std::uint64_t value, char const* name) {
        if (value == 0) {
            throw std::invalid_argument(std::string{"2D stack "} + name + " must be at least 1");
        }
        return value;
    }

    ::TwoDimStack stack_;
    std::atomic<int> next_thread_id_{0};

   public:
    explicit TwoDStack(int /*num_threads*/, std::size_t /*initial_capacity*/, Settings const& settings)
        : stack_{require_positive(settings.width, "width"), require_positive(settings.depth, "depth")} {
        (void)Min;
    }

    static void write_human_readable(std::ostream& out) {
        out << "2D Stack\n";
    }

    handle_type get_handle() {
        auto thread_id = next_thread_id_.fetch_add(1, std::memory_order_relaxed);
        return handle_type{stack_.register_thread(thread_id)};
    }
};

}  // namespace wrapper::two_d_stack
