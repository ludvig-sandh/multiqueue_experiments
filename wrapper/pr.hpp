#pragma once

extern "C" {
#include "PR-bench-impl/gc/gc.h"
#include "PR-bench-impl/prioq.h"
}
#undef min
#undef max

#include "util.hpp"

#include <limits>
#include <memory>
#include <optional>
#include <ostream>
#include <type_traits>
#include <utility>

namespace wrapper::pr {

template <bool Min, typename Key = unsigned long, typename T = Key>
class PR {
    static_assert(std::is_integral_v<Key>, "PR priority queue only supports integral keys");

   public:
    using key_type = Key;
    using mapped_type = T;
    using value_type = std::pair<key_type, mapped_type>;

    using handle_type = util::SelfHandle<PR>;
    using settings_type = util::EmptySettings;

   private:
    static constexpr unsigned long sentinel = std::numeric_limits<unsigned long>::max();

    static unsigned long queue_key(key_type key) {
        auto k = static_cast<unsigned long>(key);

        if constexpr (Min) {
            return k + 1;
        } else {
            return sentinel - k - 1;
        }
    }

    struct Deleter {
        void operator()(::pq_t* pq) const {
            if (pq == nullptr) {
                return;
            }

            while (void* raw = ::deletemin(pq)) {
                delete static_cast<value_type*>(raw);
            }

            ::pq_destroy(pq);
            ::_destroy_gc_subsystem();
        }
    };

    alignas(64) std::unique_ptr<::pq_t, Deleter> pq_;

   public:
    explicit PR(int /*thread_count*/, std::size_t /*capacity*/, settings_type const& /*settings*/) {
        ::_init_gc_subsystem();
        pq_.reset(::pq_init(32));
    }

    PR(PR const&) = delete;
    PR& operator=(PR const&) = delete;

    PR(PR&&) noexcept = default;
    PR& operator=(PR&&) noexcept = default;

    void push(value_type const& value) {
        auto* p = new value_type(value);
        ::insert(pq_.get(), queue_key(value.first), p);
    }

    std::optional<value_type> try_pop() {
        std::unique_ptr<value_type> value{static_cast<value_type*>(::deletemin(pq_.get()))};

        if (!value) {
            return std::nullopt;
        }

        return *value;
    }

    static void write_human_readable(std::ostream& out) {
        out << "PR priority queue\n";
    }

    handle_type get_handle() {
        return handle_type{*this};
    }
};

}  // namespace wrapper::pr