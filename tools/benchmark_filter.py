import csv
from pathlib import Path

from benchmarking import BenchmarkGroup, Params, benchmark_csv_path, run_benchmark_group


DIMACS_INSTANCES_PATH = Path("data/dimacs_instances.txt")
FILTERED_DIMACS_INSTANCES_PATH = Path("filtered_dimacs_instances.txt")
MIN_TIME_S = 1.0
MAX_TIME_S = 60 * 30  # 30 mins

GROUP = BenchmarkGroup(
    name="filter",
    timeout=MAX_TIME_S,
    params_fallback=Params(
        problem="Maximum Clique Problem",
        batch=None,
        stickiness=16,
        num_repetitions=1,
        threads=1,
    ),
    params_x=[],
    params_y=[
        Params(pq_type="seq_stack", name="Sequential Stack", threads=1),
    ],
)


def read_dimacs_instances(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def csv_instance_rows(csv_path: Path) -> dict[str, list[dict]]:
    rows_by_instance: dict[str, list[dict]] = {}
    if not csv_path.exists():
        return rows_by_instance

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            instance = row.get("instance", "")
            row["status"] = (row.get("status") or ("ok" if row.get("time_s") else "timeout")).strip()
            row["time_s"] = float(row["time_s"]) if row.get("time_s") else None
            rows_by_instance.setdefault(instance, []).append(row)

    return rows_by_instance


def should_keep_instance(rows: list[dict]) -> bool:
    if not rows:
        return False
    return all(
        row["status"] == "ok"
        and row["time_s"] is not None
        and row["time_s"] >= MIN_TIME_S
        for row in rows
    )


def write_filtered_instances(
    instances: list[str],
    rows_by_instance: dict[str, list[dict]],
    output_path: Path,
) -> None:
    lines = []
    for instance in instances:
        instance_rows = rows_by_instance.get(Path(instance).stem, [])
        lines.append(instance if should_keep_instance(instance_rows) else f"# {instance}")

    output_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    dimacs_instances = read_dimacs_instances(DIMACS_INSTANCES_PATH)
    group = BenchmarkGroup(
        name=GROUP.name,
        timeout=GROUP.timeout,
        params_fallback=GROUP.params_fallback,
        params_x=[Params(instance=instance) for instance in dimacs_instances],
        params_y=GROUP.params_y,
    )

    run_benchmark_group(group, "dimacs")

    csv_path = benchmark_csv_path(group, "dimacs")
    rows_by_instance = csv_instance_rows(csv_path)
    write_filtered_instances(
        dimacs_instances,
        rows_by_instance,
        FILTERED_DIMACS_INSTANCES_PATH,
    )
    kept_count = sum(
        1
        for instance in dimacs_instances
        if should_keep_instance(rows_by_instance.get(Path(instance).stem, []))
    )
    print(
        f"Wrote {FILTERED_DIMACS_INSTANCES_PATH}: "
        f"{kept_count} active, {len(dimacs_instances) - kept_count} commented out"
        f" (non-ok or faster than {MIN_TIME_S:g}s)"
    )


if __name__ == "__main__":
    main()
