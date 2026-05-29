#include "util/bnb_work_stealing_driver.hpp"
#include "util/problems/mdkp_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_parallel_work_stealing_solver<MDKPProblem>(argc, argv);
}
