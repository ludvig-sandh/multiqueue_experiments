#include "util/bnb_sequential_stack_driver.hpp"
#include "util/problems/mdkp_problem.hpp"

int main(int argc, char* argv[]) {
    bnb_sequential_stack_solver<MDKPProblem>(argc, argv);
}
