#include "util/problems/bnb_problem.hpp"

#include <iostream>

#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <random>
#include <vector>

template <typename WeightType = long long, typename ValueType = double>
class MDKPInstance {
    static_assert(std::is_arithmetic_v<WeightType> && std::is_arithmetic_v<ValueType>,
                  "WeightType and ValueType must be arithmetic types");

   public:
    struct Item {
        std::vector<WeightType> weights;
        ValueType value;
    };

   private:
    std::vector<Item> items_;
    std::vector<WeightType> capacities_{};

    std::vector<std::size_t> global_order_;
    std::vector<std::vector<std::size_t>> order_by_constraint_;

    double efficiency_global(std::size_t idx) const {
        // value / sum_c (w_c / cap_c)
        auto const& it = items_[idx];
        double denom = 0.0;
        for (std::size_t c = 0; c < capacities_.size(); ++c) {
            denom += static_cast<double>(it.weights[c]) / static_cast<double>(capacities_[c]);
        }
        return denom > 0.0 ? static_cast<double>(it.value) / denom
                        : std::numeric_limits<double>::infinity();
    }

    double efficiency_1d(std::size_t idx, std::size_t c) const {
        auto const& it = items_[idx];
        auto w = it.weights[c];
        if (w == 0) return std::numeric_limits<double>::infinity();
        return static_cast<double>(it.value) / static_cast<double>(w);
    }

    void build_orders() {
        const std::size_t n = items_.size();
        const std::size_t m = capacities_.size();

        global_order_.resize(n);
        std::iota(global_order_.begin(), global_order_.end(), 0);
        std::sort(global_order_.begin(), global_order_.end(),
                [&](std::size_t a, std::size_t b) { return efficiency_global(a) > efficiency_global(b); });

        order_by_constraint_.assign(m, {});
        for (std::size_t c = 0; c < m; ++c) {
            order_by_constraint_[c].resize(n);
            std::iota(order_by_constraint_[c].begin(), order_by_constraint_[c].end(), 0);
            std::sort(order_by_constraint_[c].begin(), order_by_constraint_[c].end(),
                    [&](std::size_t a, std::size_t b) { return efficiency_1d(a, c) > efficiency_1d(b, c); });
        }
    }

   public:
    MDKPInstance() = default;
    MDKPInstance(std::filesystem::path const& file) {
        std::ifstream in{file};
        if (!in) {
            throw std::runtime_error{"Could not open file"};
        }

        std::size_t num_items{};
        in >> num_items;
        if (!in || in.eof()) {
            throw std::runtime_error{"Could not get number of items"};
        }

        std::size_t num_constraints{};
        in >> num_constraints;
        if (!in || in.eof()) {
            throw std::runtime_error{"Could not get number of constraints"};
        }

        ValueType solution{};
        in >> solution;
        if (!in || in.eof()) {
            throw std::runtime_error{"Could not get solution"};
        }

        items_.resize(num_items);
        for (std::size_t i{0}; i < num_items; ++i) {
            if (!in || in.eof()) {
                throw std::runtime_error{"Unexpected end of file"};
            }
            in >> items_[i].value;
            if (!in || in.eof()) {
                throw std::runtime_error{"Could not read item value"};
            }
        }

        WeightType weight{};
        for (std::size_t c{0}; c < num_constraints; ++c) {
            for (std::size_t i{0}; i < num_items; ++i) {
                if (!in || in.eof()) {
                    throw std::runtime_error{"Unexpected end of file"};
                }
                in >> weight;
                items_[i].weights.push_back(weight);
                if (!in || in.eof()) {
                    throw std::runtime_error{"Could not read item weight"};
                }
            }
        }

        capacities_.resize(num_constraints);
        for (std::size_t c{0}; c < num_constraints; ++c) {
            if (!in || in.eof()) {
                throw std::runtime_error{"Unexpected end of file"};
            }
            in >> capacities_[c];
            if (!in) {
                throw std::runtime_error{"Could not read constraint capacity"};
            }
        }

        build_orders();
    }

    [[nodiscard]] std::size_t size() const noexcept {
        return items_.size();
    }

    [[nodiscard]] std::size_t num_constraints() const noexcept {
        return capacities_.size();
    }

    [[nodiscard]] WeightType capacity(std::size_t constraint) const noexcept {
        return capacities_.at(constraint);
    }

    [[nodiscard]] std::vector<WeightType> capacities() const noexcept {
        return capacities_;
    }

    [[nodiscard]] WeightType weight(std::size_t index, std::size_t constraint) const noexcept {
        return items_.at(index).weights.at(constraint);
    }

    [[nodiscard]] ValueType value(std::size_t index) const noexcept {
        return items_.at(index).value;
    }

    [[nodiscard]] std::pair<ValueType, ValueType>
    compute_bounds(std::vector<WeightType> remaining, std::size_t index) const noexcept {
        const std::size_t m = capacities_.size();

        // Lower bound: greedily select items that definitely fit based on a heuristic order
        ValueType lb = 0;
        {
            auto rem = remaining;
            for (std::size_t k = 0; k < global_order_.size(); ++k) {
                std::size_t i = global_order_[k];
                if (i < index) continue;

                auto const& it = items_[i];
                bool fits = true;
                for (std::size_t c = 0; c < m; ++c) {
                    if (it.weights[c] > rem[c]) { fits = false; break; }
                }
                if (!fits) continue;

                for (std::size_t c = 0; c < m; ++c) rem[c] -= it.weights[c];
                lb += it.value;
            }
        }

        // Upper bound: min over 1D fractional relaxations
        ValueType ub = std::numeric_limits<ValueType>::infinity();

        for (std::size_t c = 0; c < m; ++c) {
            double cap = static_cast<double>(remaining[c]);
            double ub_c = 0.0;

            // Fractional knapsack on constraint c only, over items i >= index
            for (std::size_t pos = 0; pos < order_by_constraint_[c].size(); ++pos) {
                std::size_t i = order_by_constraint_[c][pos];
                if (i < index) continue;

                auto const& it = items_[i];
                double w = static_cast<double>(it.weights[c]);
                double v = static_cast<double>(it.value);

                if (w == 0.0) {
                    // zero weight in this constraint => can take fully in this 1D relaxation
                    ub_c += v;
                    continue;
                }

                if (w <= cap) {
                    cap -= w;
                    ub_c += v;
                } else {
                    // fractional take
                    ub_c += v * (cap / w);
                    break;
                }
            }

            ub = std::min(ub, static_cast<ValueType>(ub_c));
        }

        if (!std::isfinite(static_cast<double>(ub))) ub = lb;

        return {lb, ub};
    }
};

class MDKPProblem : public BnBProblem<MDKPProblem> {
public:
    using data_type = double;
    using weight_type = long long;
    using instance_type = MDKPInstance<weight_type, data_type>;

    struct Node {
        data_type upper_bound;
        data_type lower_bound;
        std::size_t index;
        std::vector<weight_type> free_capacities;
        data_type value;
    };
    using node_type = Node;

    // Optional comparator for std::priority_queue (max-UB first)
    struct Compare {
        bool operator()(node_type const& a, node_type const& b) const noexcept {
            return a.upper_bound < b.upper_bound;
        }
    };

    explicit MDKPProblem(instance_type const& inst) : inst_(inst) {}

    [[nodiscard]] node_type root_impl() const noexcept {
        auto [lb, ub] = inst_.compute_bounds(inst_.capacities(), 0);
        return node_type{ub, lb, 0, inst_.capacities(), 0};
    }

    void branch_impl(node_type const& n, data_type incumbent, std::vector<node_type>& out) const {
        if (n.index + 2 >= inst_.size()) return;

        auto [lb, ub] = inst_.compute_bounds(n.free_capacities, n.index + 1);

        // Exclude item
        {
            node_type child{n.value + ub, n.value + lb, n.index + 1, n.free_capacities, n.value};
            if (child.upper_bound > incumbent) out.push_back(std::move(child));
        }

        // Include item
        bool can_fit_item = true;
        for (std::size_t c{0}; c < inst_.num_constraints(); ++c) {
            if (n.free_capacities[c] < inst_.weight(n.index, c)) {
                can_fit_item = false;
                break;
            }
        }

        if (can_fit_item) {
            node_type child = n;
            child.value = n.value + inst_.value(n.index);
            for (std::size_t c{0}; c < inst_.num_constraints(); ++c) {
                child.free_capacities[c] -= inst_.weight(n.index, c);
            }
            child.index = n.index + 1;
            child.upper_bound = n.upper_bound;
            child.lower_bound = n.lower_bound;

            if (child.upper_bound > incumbent) out.push_back(std::move(child));
        }
    }

private:
    [[nodiscard]] Bounds<data_type> bounds_impl(node_type const& n) const noexcept {
        auto [lb, ub] = inst_.compute_bounds(n.free_capacities, n.index + 1);
        return {n.value + lb, n.value + ub};
    }

    instance_type const& inst_;
};
