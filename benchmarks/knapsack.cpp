#include "util/bnb_parallel_driver.hpp"
#include "util/problems/knapsack_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_parallel_solver<KnapsackProblem>(argc, argv);
}
