from pathlib import Path

from benchmarking import BenchmarkGroup, Params, run_benchmark_group


DIMACS_INSTANCES_PATH = Path("data/filtered_dimacs_instances.txt")


# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
GROUP = BenchmarkGroup(
    name="comparison",
    timeout=60*30,
    params_fallback=Params(
        problem="max_clique",
        batch=None,
        num_repetitions=5,
        threads=512
    ),
    params_x=[
        
    ],
    params_y=[
        Params(pq_type="locked_stack", name="Globally locked Stack", batch=16),
        Params(pq_type="pmc", name="PMC library"),
        Params(pq_type="ciaranm", name="CiaranM solver"),
        Params(pq_type="work_stealing", name="Simple work stealing", batch=16),
        Params(pq_type="multilifo", name="MultiLIFO", num_repetitions=20, batch=16),
        Params(pq_type="treiber_stack", name="Treiber stack (elimination)", batch=16),
        Params(pq_type="2d_stack", name="2D stack", batch=16),
        Params(pq_type="locked_pq", name="Globally locked PQ", batch=16),
        Params(pq_type="pr", name="PR", batch=16),
        Params(pq_type="mq_stick_swap", name="MultiQueue (stick swap)", batch=16),
    ],
)


def main() -> None:
    dimacs_instances = [
        line.strip()
        for line in DIMACS_INSTANCES_PATH.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    group = BenchmarkGroup(
        name=GROUP.name,
        timeout=GROUP.timeout,
        params_fallback=GROUP.params_fallback,
        params_x=[Params(instance=instance) for instance in dimacs_instances],
        params_y=GROUP.params_y,
    )
    run_benchmark_group(group, "dimacs")


if __name__ == "__main__":
    main()
