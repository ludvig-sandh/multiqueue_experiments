#pragma once

#include <type_traits>
#include <utility>
#include <vector>

// Generic bounds container
template <class T>
struct Bounds {
    T lower;
    T upper;
};

/*
CRTP interface for Branch-and-Bound "problem policies".

A Derived problem must provide:
  - using data_type = ...
  - struct Node { ... };  (or using node_type = ...)
  - std::pair<node_type, data_type> root_impl() const noexcept;
  - Bounds<data_type> bounds_impl(node_type const&) const noexcept;
  - void children_impl(node_type const&, data_type incumbent, std::vector<node_type>& out) const;

Optionally, a Derived can provide:
  - struct Compare { bool operator()(node_type const&, node_type const&) const noexcept; }
    (useful for std::priority_queue)
*/
template <class Derived>
class BnBProblem {
public:

    // Root node + initial incumbent
    [[nodiscard]] auto root() const noexcept {
        return derived().root_impl();
    }

    // Node bounds (must be valid for pruning)
    template <class Node>
    [[nodiscard]] auto bounds(Node const& n) const noexcept {
        return derived().bounds_impl(n);
    }

    // Generate children (can filter using incumbent)
    template <class Node, class Value>
    void children(Node const& n, Value incumbent, std::vector<Node>& out) const {
        derived().children_impl(n, incumbent, out);
    }

private:
    Derived const& derived() const noexcept {
        return static_cast<Derived const&>(*this);
    }
};
