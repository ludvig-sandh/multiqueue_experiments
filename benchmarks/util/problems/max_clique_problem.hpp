#pragma once

#include "bnb_problem.hpp"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>

// -------- trailing zero count --------
inline unsigned ctz64(std::uint64_t x) {
#if defined(__GNUG__) || defined(__clang__)
    // Undefined for x==0, caller must ensure x!=0 (same contract as countr_zero usage)
    return static_cast<unsigned>(__builtin_ctzll(x));
#elif defined(_MSC_VER)
    unsigned long idx;
    _BitScanForward64(&idx, x);
    return static_cast<unsigned>(idx);
#else
    // Portable fallback (rarely used, but safe)
    unsigned n = 0;
    while ((x & 1u) == 0u) {
        x >>= 1;
        ++n;
    }
    return n;
#endif
}

// -------- popcount --------
inline unsigned popcount64(std::uint64_t x) {
#if defined(__GNUG__) || defined(__clang__)
    return static_cast<unsigned>(__builtin_popcountll(x));
#elif defined(_MSC_VER)
    return static_cast<unsigned>(__popcnt64(x));
#else
    // Portable fallback
    unsigned c = 0;
    while (x) {
        x &= (x - 1);
        ++c;
    }
    return c;
#endif
}

struct Bitset {
    using word_t = std::uint64_t;
    static constexpr std::size_t W = 64;

    std::size_t nbits{};
    std::vector<word_t> w;

    Bitset() = default;
    explicit Bitset(std::size_t n) : nbits(n), w((n + W - 1) / W, 0) {}

    void set(std::size_t i) { w[i / W] |= (word_t(1) << (i % W)); }
    void reset(std::size_t i) { w[i / W] &= ~(word_t(1) << (i % W)); }
    bool test(std::size_t i) const { return (w[i / W] >> (i % W)) & word_t(1); }

    void clear_all() { std::fill(w.begin(), w.end(), word_t(0)); }

    void set_all() {
        std::fill(w.begin(), w.end(), ~word_t(0));
        if (!w.empty()) {
            std::size_t rem = nbits % W;
            if (rem != 0) {
                w.back() &= ((word_t(1) << rem) - 1);
            }
        }
    }

    bool any() const {
        for (auto x : w) if (x) return true;
        return false;
    }

    std::size_t count() const {
        std::size_t c = 0;
        for (auto x : w) c += popcount64(x);
        return c;
    }

    // this &= other
    void intersect_with(Bitset const& other) {
        for (std::size_t i = 0; i < w.size(); ++i) w[i] &= other.w[i];
    }

    // out = a & b
    static Bitset intersection(Bitset const& a, Bitset const& b) {
        Bitset out(a.nbits);
        for (std::size_t i = 0; i < out.w.size(); ++i) out.w[i] = a.w[i] & b.w[i];
        return out;
    }

    // Returns nbits if empty
    std::size_t find_any() const {
        for (std::size_t wi = 0; wi < w.size(); ++wi) {
            word_t x = w[wi];
            if (x == 0) continue;
            return wi * W + std::size_t(ctz64(x));
        }
        return nbits;
    }

    template <class F>
    void for_each_set_bit(F&& f) const {
        for (std::size_t wi = 0; wi < w.size(); ++wi) {
            word_t x = w[wi];
            while (x) {
                unsigned b = ctz64(x);
                std::size_t v = wi * W + std::size_t(b);
                if (v < nbits) f(v);
                x &= (x - 1);
            }
        }
    }
};

struct MaxCliqueInstance {
    std::size_t n{};
    std::vector<Bitset> adj; // adj[v] = neighbors of v

    MaxCliqueInstance() = default;

    explicit MaxCliqueInstance(std::filesystem::path const& file) {
        std::ifstream in(file);
        if (!in) throw std::runtime_error("cannot open instance file");

        // Try DIMACS first; if no 'p' line appears, fall back to simple "n m" header.
        std::string line;
        bool saw_dimacs_p = false;
        std::size_t m_dimacs = 0;

        // We may need to buffer edges if DIMACS (since n comes from p-line)
        std::vector<std::pair<std::size_t, std::size_t>> edges;

        // Peek file (read all lines)
        std::vector<std::string> lines;
        while (std::getline(in, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            lines.push_back(line);
        }

        // DIMACS scan
        for (auto const& ln : lines) {
            if (ln.empty()) continue;
            if (ln[0] == 'c') continue;
            if (ln[0] == 'p') {
                std::istringstream ss(ln);
                char p;
                std::string kind;
                ss >> p >> kind >> n >> m_dimacs;
                if (!ss || (kind != "edge" && kind != "col" && kind != "clq")) {
                    throw std::runtime_error("DIMACS 'p' line parse failed or unsupported");
                }
                saw_dimacs_p = true;
                break;
            }
        }

        if (saw_dimacs_p) {
            adj.assign(n, Bitset(n));
            for (auto const& ln : lines) {
                if (ln.empty()) continue;
                if (ln[0] == 'c') continue;
                if (ln[0] == 'p') continue;
                if (ln[0] == 'e') {
                    std::istringstream ss(ln);
                    char e;
                    std::size_t u1, v1;
                    ss >> e >> u1 >> v1;
                    if (!ss) continue;
                    // DIMACS edges are 1-based
                    if (u1 == 0 || v1 == 0) continue;
                    std::size_t u = u1 - 1, v = v1 - 1;
                    if (u >= n || v >= n || u == v) continue;
                    adj[u].set(v);
                    adj[v].set(u);
                }
            }
            return;
        }

        // Fallback: simple edge list: "n m" then m pairs u v (assume 0-based)
        {
            std::istringstream ss(lines.empty() ? "" : lines[0]);
            std::size_t m;
            ss >> n >> m;
            if (!ss) throw std::runtime_error("could not parse simple header 'n m'");
            adj.assign(n, Bitset(n));

            std::size_t read_edges = 0;
            for (std::size_t i = 1; i < lines.size() && read_edges < m; ++i) {
                std::istringstream es(lines[i]);
                std::size_t u, v;
                es >> u >> v;
                if (!es) continue;
                if (u >= n || v >= n || u == v) continue;
                adj[u].set(v);
                adj[v].set(u);
                ++read_edges;
            }
            // If fewer than m edges found, still accept (some files may contain blanks/comments).
            return;
        }
    }

    std::size_t size() const noexcept { return n; }
    Bitset const& neighbors(std::size_t v) const noexcept { return adj[v]; }
};


// Upper bound: greedy sequential coloring of the induced subgraph on P.
// The number of colors is an upper bound on clique size in P.
inline unsigned greedy_coloring_upper_bound(MaxCliqueInstance const& G, Bitset const& P) {
    Bitset remaining = P;
    unsigned colors = 0;

    while (remaining.any()) {
        ++colors;

        // Build one color class as a maximal independent set.
        Bitset avail = remaining;
        Bitset colored(P.nbits);

        while (avail.any()) {
            std::size_t v = avail.find_any();
            if (v >= avail.nbits) break;

            colored.set(v);
            avail.reset(v);

            // Remove neighbors of v from avail so chosen vertices are mutually non-adjacent.
            auto const& Nv = G.neighbors(v);
            for (std::size_t i = 0; i < avail.w.size(); ++i) {
                avail.w[i] &= ~Nv.w[i];
            }
        }

        // Remove colored vertices from remaining
        for (std::size_t i = 0; i < remaining.w.size(); ++i) {
            remaining.w[i] &= ~colored.w[i];
        }
    }

    return colors;
}

// Tomita/MCQ-style coloring: return a candidate order and an upper-bound per position.
inline void color_sort_with_bounds(MaxCliqueInstance const& G,
                                   Bitset const& P,
                                   std::vector<unsigned>& order,
                                   std::vector<unsigned>& color_bound) {
    order.clear();
    color_bound.clear();

    Bitset remaining = P;
    unsigned color = 0;

    while (remaining.any()) {
        ++color;

        Bitset avail = remaining;
        Bitset colored(P.nbits);

        while (avail.any()) {
            std::size_t v = avail.find_any();
            if (v >= avail.nbits) break;

            colored.set(v);
            avail.reset(v);

            auto const& Nv = G.neighbors(v);
            for (std::size_t i = 0; i < avail.w.size(); ++i) {
                avail.w[i] &= ~Nv.w[i];
            }
        }

        colored.for_each_set_bit([&](std::size_t v) {
            order.push_back(static_cast<unsigned>(v));
            color_bound.push_back(color);
        });

        for (std::size_t i = 0; i < remaining.w.size(); ++i) {
            remaining.w[i] &= ~colored.w[i];
        }
    }
}

// Lower bound: greedy clique completion from P
inline unsigned greedy_completion_lower_bound(MaxCliqueInstance const& G, Bitset P) {
    unsigned added = 0;
    while (P.any()) {
        std::size_t v = P.find_any();
        if (v >= P.nbits) break;

        ++added;

        // Next candidates must be adjacent to v.
        P = Bitset::intersection(P, G.neighbors(v));
    }
    return added;
}

class MaxCliqueProblem : public BnBProblem<MaxCliqueProblem> {
public:
    using data_type = unsigned;
    using instance_type = MaxCliqueInstance;

    struct Node {
        data_type upper_bound; // PQ key
        data_type lower_bound;
        data_type clique_size; // |C|
        Bitset candidates;     // P
    };
    using node_type = Node;

    struct Compare {
        bool operator()(node_type const& a, node_type const& b) const noexcept {
            return a.upper_bound < b.upper_bound; // max-UB first
        }
    };

    explicit MaxCliqueProblem(instance_type const& inst) : G_(inst) {}

    [[nodiscard]] node_type root_impl() const noexcept {
        Bitset P(G_.size());
        P.set_all();

        data_type lb = greedy_completion_lower_bound(G_, P);
        data_type ub = greedy_coloring_upper_bound(G_, P);

        return node_type{ub, lb, 0u, std::move(P)};
    }

    void branch_impl(node_type const& n, data_type incumbent, std::vector<node_type>& out) const {
        order_.clear();
        bound_.clear();
        color_sort_with_bounds(G_, n.candidates, order_, bound_);
        if (bound_.empty()) return;

        if (n.clique_size + bound_.back() <= incumbent) return;

        // MCQ/Tomita-style expansion over an ordered P: after each branch, remove v from P.
        Bitset remaining = n.candidates;

        // Expand in reverse coloring order; color bounds give branch-and-bound cutoff.
        for (std::size_t idx = order_.size(); idx-- > 0;) {
            if (n.clique_size + bound_[idx] <= incumbent) break;

            unsigned v = order_[idx];
            Bitset childP = Bitset::intersection(remaining, G_.neighbors(v));
            data_type child_clique = n.clique_size + 1;
            data_type child_ub = child_clique + greedy_coloring_upper_bound(G_, childP);
            data_type child_lb = child_clique + greedy_completion_lower_bound(G_, childP);

            out.push_back(node_type{child_ub, child_lb, child_clique, std::move(childP)});

            remaining.reset(v);
        }
    }

private:
    [[nodiscard]] Bounds<data_type> bounds_impl(node_type const& n) const noexcept {
        data_type ub = n.clique_size + greedy_coloring_upper_bound(G_, n.candidates);
        data_type lb = n.clique_size + greedy_completion_lower_bound(G_, n.candidates);
        return {lb, ub};
    }

    instance_type const& G_;
    inline static thread_local std::vector<unsigned> order_{};
    inline static thread_local std::vector<unsigned> bound_{};
};