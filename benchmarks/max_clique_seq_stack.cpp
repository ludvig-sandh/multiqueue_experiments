#include "util/bnb_sequential_stack_driver.hpp"
#include "util/problems/max_clique_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_sequential_stack_solver<MaxCliqueProblem>(argc, argv);
}
