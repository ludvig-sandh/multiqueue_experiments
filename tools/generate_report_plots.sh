#!/bin/bash
set -euo pipefail

python3 tools/result_plotter.py athena_results/batch/batch_brock400_4_athena.csv --mode batch --heatmap-colors row-slowdown
python3 tools/result_plotter.py athena_results/batch/batch_brock400_4_athena.csv --mode batch --layout graph
python3 tools/result_plotter.py athena_results/batch/batch_DSJC1000_5_athena.csv --mode batch --heatmap-colors row-slowdown
python3 tools/result_plotter.py athena_results/batch/batch_DSJC1000_5_athena.csv --mode batch --layout graph
python3 tools/result_plotter.py athena_results/batch/batch_gen200_p0.9_44_athena.csv --mode batch --heatmap-colors row-slowdown
python3 tools/result_plotter.py athena_results/batch/batch_gen200_p0.9_44_athena.csv --mode batch --layout graph

python3 tools/result_plotter.py athena_results/scalability/scalability_brock400_4.csv --heatmap-width compact
python3 tools/result_plotter.py athena_results/scalability/scalability_brock400_4.csv --layout graph

python3 tools/result_plotter.py athena_results/scalability/scalability_DSJC1000_5.csv --heatmap-width compact
python3 tools/result_plotter.py athena_results/scalability/scalability_DSJC1000_5.csv --layout graph

python3 tools/result_plotter.py athena_results/scalability/scalability_gen200_p0.9_44.csv --heatmap-width compact
python3 tools/result_plotter.py athena_results/scalability/scalability_gen200_p0.9_44.csv --layout graph

python3 tools/result_plotter.py athena_results/comparison/comparison_dimacs.csv --mode comparison --heatmap-colors row-slowdown --heatmap-width compact