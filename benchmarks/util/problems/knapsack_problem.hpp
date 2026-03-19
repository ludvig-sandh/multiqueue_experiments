#pragma once

#include "bnb_problem.hpp"
#include "knapsack_instance.hpp"

class KnapsackProblem : public BnBProblem<KnapsackProblem> {
public:
    using data_type = unsigned long;
    using instance_type = KnapsackInstance<data_type>;

    struct Node {
        data_type upper_bound;
        data_type lower_bound;
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

    [[nodiscard]] node_type root_impl() const noexcept {
        auto [lb, ub] = inst_.compute_bounds_linear(inst_.capacity(), 0);
        return {ub, lb, 0, inst_.capacity(), 0};
    }

    void branch_impl(node_type const& node, data_type incumbent, std::vector<node_type>& out) const {
        (void)incumbent;
        
        if (node.index + 2 >= inst_.size()) return;

        auto [lb, ub] = inst_.compute_bounds_linear(node.free_capacity, node.index + 1);

        // Exclude item
        {
            node_type child{node.value + ub, node.value + lb, node.index + 1, node.free_capacity, node.value};
            out.push_back(std::move(child));
        }

        // Include item
        if (node.free_capacity >= inst_.weight(node.index)) {
            node_type child = node;
            child.value = node.value + inst_.value(node.index);
            child.free_capacity = node.free_capacity - inst_.weight(node.index);
            child.index = node.index + 1;
            
            out.push_back(std::move(child));
        }
    }

private:
    [[nodiscard]] Bounds<data_type> bounds_impl(node_type const& n) const noexcept {
        auto [lb, ub] = inst_.compute_bounds_linear(n.free_capacity, n.index + 1);
        return {n.value + lb, n.value + ub};
    }

    instance_type const& inst_;
};
