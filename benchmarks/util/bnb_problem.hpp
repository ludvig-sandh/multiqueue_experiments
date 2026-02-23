#pragma once

#include "knapsack_instance.hpp"

#include <utility>
#include <vector>

template <class ValueType>
struct Bounds {
    ValueType lower;
    ValueType upper;
};

// TODO: Generalise this to an abstract class where each B&B problem implementation is simply a derivation of this.
// This is just a placeholder that implements the backend for the standard 0-1 knapsack.

template <class ValueType, class NodeType>
class BnBProblem {
public:
    using data_type = ValueType;
    using node_type = NodeType;

    explicit BnBProblem(KnapsackInstance<ValueType> const& inst) : inst_(inst) {}

    // Returns (root_node, initial_incumbent)
    [[nodiscard]] std::pair<node_type, ValueType> root() const noexcept {
        auto [lb, ub] = inst_.compute_bounds_linear(inst_.capacity(), 0);
        node_type r{ub, 0, inst_.capacity(), 0};
        return {r, lb};
    }

    [[nodiscard]] Bounds<ValueType> bounds(node_type const& n) const noexcept {
        auto [lb, ub] = inst_.compute_bounds_linear(n.free_capacity, n.index + 1);
        return {n.value + lb, n.value + ub};
    }

    // Generate children to push (can incorporate incumbent-based filtering)
    [[nodiscard]] void children(node_type const& n, ValueType incumbent, std::vector<node_type>& out) const {
        out.clear();

        if (n.index + 2 >= inst_.size()) return;

        auto [lb, ub] = inst_.compute_bounds_linear(n.free_capacity, n.index + 1);

        // Exclude item
        {
            node_type child{n.value + ub, n.index + 1, n.free_capacity, n.value};
            if (child.upper_bound > incumbent) out.push_back(std::move(child));
        }

        // Inlcude item
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
    KnapsackInstance<ValueType> const& inst_;
};
