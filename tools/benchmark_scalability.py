from benchmarking import BenchmarkGroup, Params, parse_instance_arg, run_benchmark_group


# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
GROUP = BenchmarkGroup(
    name="scalability",
    timeout=60*30,
    params_fallback=Params(
        problem="Maximum Clique Problem",
        batch=None,
        num_repetitions=5,
    ),
    params_x=[
        # Params(pq_type="seq_stack", name="Sequential Stack", threads=1),
        # Params(pq_type="locked_stack", name="Globally locked Stack", batch=16),
        # Params(pq_type="pmc", name="PMC library"),
        Params(pq_type="ciaranm", name="CiaranM solver"),
        # Params(pq_type="work_stealing", name="Simple work stealing", batch=16),
        # Params(pq_type="multilifo", name="MultiLIFO", num_repetitions=20, batch=16),
        # Params(pq_type="treiber_stack", name="Treiber stack (elimination)", batch=16),
        # Params(pq_type="2d_stack", name="2D stack", batch=16),
        # Params(pq_type="seq_pq", name="Sequential PQ", threads=1),
        # Params(pq_type="locked_pq", name="Globally locked PQ", batch=16),
        # Params(pq_type="pr", name="PR", batch=16),
        # Params(pq_type="mq_stick_swap", name="MultiQueue (stick swap)", batch=16),
    ],
    params_y=[
        Params(threads=1),
        Params(threads=2),
        Params(threads=4),
        Params(threads=8),
        Params(threads=16),
        Params(threads=32),
        Params(threads=64),
        Params(threads=128),
        Params(threads=256),
        Params(threads=512)
    ],
)


def main() -> None:
    args = parse_instance_arg("Run scalability benchmark matrix for an input instance.")
    run_benchmark_group(GROUP, args.instance)


if __name__ == "__main__":
    main()
