#include "util/bnb_problem.hpp"
#include "util/bnb_parallel_driver.hpp"
#include "util/max_clique_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_parallel_solver<MaxCliqueProblem>(argc, argv);
}
