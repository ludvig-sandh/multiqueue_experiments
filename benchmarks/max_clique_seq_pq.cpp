#include "util/bnb_sequential_pq_driver.hpp"
#include "util/problems/max_clique_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_sequential_pq_solver<MaxCliqueProblem>(argc, argv);
}
