from pathlib import Path

from benchmarking import BenchmarkGroup, Params, run_benchmark_group


DIMACS_INSTANCES_PATH = Path("data/dimacs_instances.txt")


# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
GROUP = BenchmarkGroup(
    name="comparison",
    params_fallback=Params(
        problem="max_clique",
        batch=None,
        stickiness=16,
        num_repetitions=5,
        threads=24
    ),
    params_x=[
        
    ],
    params_y=[
        Params(pq_type="locked_stack", name="Globally locked Stack"),
        Params(pq_type="pmc", name="PMC library"),
        Params(pq_type="work_stealing", name="Simple work stealing"),
        Params(pq_type="multilifo", name="MultiLIFO", num_repetitions=20),
        Params(pq_type="treiber_stack", name="Treiber stack (elimination)"),
        Params(pq_type="2d_stack", name="2D stack"),
        Params(pq_type="seq_pq", name="Sequential PQ", threads=1),
        Params(pq_type="locked_pq", name="Globally locked PQ"),
        Params(pq_type="pr", name="PR (batch=16)", batch=16),
        Params(pq_type="mq_stick_swap", name="MultiQueue (stick swap, batch=16)", batch=16),
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
        params_fallback=GROUP.params_fallback,
        params_x=[Params(instance=instance) for instance in dimacs_instances],
        params_y=GROUP.params_y,
    )
    run_benchmark_group(group, "dimacs")


if __name__ == "__main__":
    main()
