from benchmarking import BenchmarkGroup, Params, parse_instance_arg, run_benchmark_group


# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
GROUP = BenchmarkGroup(
    name="batch",
    timeout=60*30,
    params_fallback=Params(
        problem="Maximum Clique Problem",
        num_repetitions=25,
        threads=512
    ),
    params_x=[
        Params(pq_type="locked_stack", name="Globally locked Stack"),
        Params(pq_type="work_stealing", name="Simple work stealing"),
        Params(pq_type="multilifo", name="MultiLIFO"),
        Params(pq_type="treiber_stack", name="Treiber stack (elimination)"),
        Params(pq_type="2d_stack", name="2D stack"),
        Params(pq_type="locked_pq", name="Globally locked PQ"),
        Params(pq_type="pr", name="PR"),
        Params(pq_type="mq_stick_swap", name="MultiQueue (stick swap)"),
    ],
    params_y=[
        Params(batch=1),
        Params(batch=4),
        Params(batch=16),
        Params(batch=64),
        Params(batch=256),
        Params(batch=1024),
    ],
)


def main() -> None:
    args = parse_instance_arg("Run scalability benchmark matrix for an input instance.")
    run_benchmark_group(GROUP, args.instance)


if __name__ == "__main__":
    main()
