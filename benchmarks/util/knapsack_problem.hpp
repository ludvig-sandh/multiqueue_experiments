#pragma once

#include "bnb_problem.hpp"
#include "knapsack_instance.hpp"

class KnapsackProblem : public BnBProblem<KnapsackProblem> {
public:
    using data_type = unsigned long;
    using instance_type = KnapsackInstance<data_type>;

    struct Node {
        data_type upper_bound;
        std::size_t index;
        data_type free_capacity;
        data_type value;
    };
    using node_type = Node;

    // Optional comparator for std::priority_queue (max-UB first)
    struct Compare {
        bool operator()(node_type const& a, node_type const& b) const noexcept {
            return a.upper_bound < b.upper_bound;
        }
    };

    explicit KnapsackProblem(instance_type const& inst) : inst_(inst) {}

    [[nodiscard]] std::pair<node_type, data_type> root_impl() const noexcept {
        auto [lb, ub] = inst_.compute_bounds_linear(inst_.capacity(), 0);
        return {node_type{ub, 0, inst_.capacity(), 0}, lb};
    }

    [[nodiscard]] Bounds<data_type> bounds_impl(node_type const& n) const noexcept {
        auto [lb, ub] = inst_.compute_bounds_linear(n.free_capacity, n.index + 1);
        return {n.value + lb, n.value + ub};
    }

    void children_impl(node_type const& n, data_type incumbent, std::vector<node_type>& out) const {
        out.clear();

        if (n.index + 2 >= inst_.size()) return;

        auto [lb, ub] = inst_.compute_bounds_linear(n.free_capacity, n.index + 1);

        // Exclude item
        {
            node_type child{n.value + ub, n.index + 1, n.free_capacity, n.value};
            if (child.upper_bound > incumbent) out.push_back(std::move(child));
        }

        // Include item
        if (n.free_capacity >= inst_.weight(n.index)) {
            node_type child = n;
            child.value = n.value + inst_.value(n.index);
            child.free_capacity = n.free_capacity - inst_.weight(n.index);
            child.index = n.index + 1;
            child.upper_bound = n.upper_bound;

            if (child.upper_bound > incumbent) out.push_back(std::move(child));
        }
    }

private:
    instance_type const& inst_;
};
