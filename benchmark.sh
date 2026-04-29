git clone --recurse-submodules https://github.com/ludvig-sandh/multiqueue_experiments.git

# Enter repo
cd multiqueue_experiments

git switch containerized-benchmark

# Import DIMACS into data
cd data
wget http://iridia.ulb.ac.be/~fmascia/files/DIMACS_all_ascii.tar.bz2
tar -xvf DIMACS_all_ascii.tar.bz2
rm DIMACS_all_ascii.tar.bz2
cd ..

# Run experiments
python3 tools/benchmarker.py data/DIMACS_all_ascii/brock200_1.clq

mkdir ../results
mv benchmark_results_brock200_1.csv ../results/benchmark_results_brock200_1.csv

# Cleanup
rm -rf multiqueue_experiments
