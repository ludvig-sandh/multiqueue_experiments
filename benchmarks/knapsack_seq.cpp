#include "util/bnb_sequential_driver.hpp"
#include "util/knapsack_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_sequential_solver<KnapsackProblem>(argc, argv);
}
