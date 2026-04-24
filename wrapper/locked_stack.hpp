#pragma once

#include "util.hpp"

#include <cstddef>
#include <mutex>
#include <optional>
#include <utility>
#include <vector>

namespace wrapper::locked_stack {

template <bool Min, typename Key = unsigned long, typename T = Key>
class LockedStack {
   public:
    using key_type = Key;
    using mapped_type = T;
    using value_type = std::pair<key_type, mapped_type>;

   private:
    std::vector<value_type> stack_{};
    std::mutex m_;

   public:
    using handle_type = util::SelfHandle<LockedStack>;
    using settings_type = util::EmptySettings;

    LockedStack(int /*unused*/, std::size_t initial_capacity, settings_type const& /*unused*/) {
        stack_.reserve(initial_capacity);
    }

    void push(value_type const& value) {
        std::lock_guard<std::mutex> lock{m_};
        stack_.push_back(value);
    }

    std::optional<value_type> try_pop() {
        std::lock_guard<std::mutex> lock{m_};
        if (stack_.empty()) {
            return std::nullopt;
        }
        auto value = std::move(stack_.back());
        stack_.pop_back();
        return value;
    }

    static void write_human_readable(std::ostream& out) {
        out << "Locked Stack\n";
    }

    handle_type get_handle() {
        return handle_type{*this};
    }
};

}  // namespace wrapper::locked_stack
