#include "util/bnb_parallel_driver.hpp"
#include "util/problems/mdkp_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_parallel_solver<MDKPProblem>(argc, argv);
}
