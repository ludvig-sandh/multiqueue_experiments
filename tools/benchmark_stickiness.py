from benchmarking import BenchmarkGroup, Params, parse_instance_arg, run_benchmark_group


# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
GROUP = BenchmarkGroup(
    name="stickiness",
    timeout=60*30,
    params_fallback=Params(
        problem="Maximum Clique Problem",
        num_repetitions=5,
        threads=512
    ),
    params_x=[
        Params(pq_type="multilifo", name="MultiLIFO"),
        Params(pq_type="mq_pq", name="MultiQueue (pq)"),
        Params(pq_type="mq_random", name="MultiQueue (random)"),
        Params(pq_type="mq_random_strict", name="MultiQueue (random strict)"),
        Params(pq_type="mq_stick_mark", name="MultiQueue (stick mark)"),
        Params(pq_type="mq_stick_random", name="MultiQueue (stick random)"),
        Params(pq_type="mq_stick_swap", name="MultiQueue (stick swap)"),
    ],
    params_y=[
        Params(stickiness=1),
        Params(stickiness=4),
        Params(stickiness=16),
        Params(stickiness=64),
        Params(stickiness=256),
        Params(stickiness=1024),
    ],
)


def main() -> None:
    args = parse_instance_arg("Run scalability benchmark matrix for an input instance.")
    run_benchmark_group(GROUP, args.instance)


if __name__ == "__main__":
    main()
