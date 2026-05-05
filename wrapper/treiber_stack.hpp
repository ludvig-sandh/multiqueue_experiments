#pragma once

#include "util.hpp"

#include <cds/container/treiber_stack.h>
#include <cds/gc/hp.h>
#include <cds/init.h>
#include <cds/threading/model.h>

#include <cstddef>
#include <memory>
#include <optional>
#include <ostream>
#include <utility>

namespace wrapper::treiber_stack {

class Runtime {
   public:
    Runtime() {
        cds::Initialize();
        hp_ = std::make_unique<cds::gc::HP>();
    }

    Runtime(Runtime const&) = delete;
    Runtime& operator=(Runtime const&) = delete;

    ~Runtime() {
        hp_.reset();
        cds::Terminate();
    }

   private:
    std::unique_ptr<cds::gc::HP> hp_;
};

inline std::shared_ptr<Runtime> runtime() {
    static std::weak_ptr<Runtime> weak;
    auto shared = weak.lock();
    if (!shared) {
        shared = std::make_shared<Runtime>();
        weak = shared;
    }
    return shared;
}

class ThreadAttachment {
   public:
    ThreadAttachment() {
        cds::threading::Manager::attachThread();
    }

    ThreadAttachment(ThreadAttachment const&) = delete;
    ThreadAttachment& operator=(ThreadAttachment const&) = delete;

    ThreadAttachment(ThreadAttachment&& other) noexcept : attached_{std::exchange(other.attached_, false)} {
    }

    ThreadAttachment& operator=(ThreadAttachment&& other) noexcept {
        if (this != &other) {
            detach();
            attached_ = std::exchange(other.attached_, false);
        }
        return *this;
    }

    ~ThreadAttachment() {
        detach();
    }

   private:
    void detach() {
        if (attached_) {
            cds::threading::Manager::detachThread();
            attached_ = false;
        }
    }

    bool attached_{true};
};

template <bool Min, typename Key = unsigned long, typename T = Key>
class TreiberStack {
   public:
    using key_type = Key;
    using mapped_type = T;
    using value_type = std::pair<key_type, mapped_type>;

    struct Traits : public cds::container::treiber_stack::make_traits<cds::opt::enable_elimination<true>>::type {};

   private:
    using stack_type = cds::container::TreiberStack<cds::gc::HP, value_type, Traits>;

    class Handle {
        friend TreiberStack;

        ThreadAttachment attachment_;
        stack_type* stack_;

        explicit Handle(stack_type& stack) : stack_{&stack} {
        }

       public:
        bool push(value_type const& value) {
            return stack_->push(value);
        }

        std::optional<value_type> try_pop() {
            std::optional<value_type> value;
            if (!stack_->pop_with([&](value_type& item) { value.emplace(std::move(item)); })) {
                return std::nullopt;
            }
            return value;
        }
    };

   public:
    using handle_type = Handle;
    using settings_type = util::EmptySettings;

   private:
    std::shared_ptr<Runtime> runtime_;
    stack_type stack_;

   public:
    explicit TreiberStack(int /*thread_count*/, std::size_t /*capacity*/, settings_type const& /*settings*/)
        : runtime_{runtime()} {
        (void)Min;
    }

    TreiberStack(TreiberStack const&) = delete;
    TreiberStack& operator=(TreiberStack const&) = delete;

    static void write_human_readable(std::ostream& out) {
        out << "Treiber stack\n";
        out << "  Elimination: enabled\n";
    }

    handle_type get_handle() {
        return handle_type{stack_};
    }
};

}  // namespace wrapper::treiber_stack
