import argparse
import csv
import json
import re
import signal
import shlex
import subprocess
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import List

TIMEOUT = 60*10  # Seconds allowed per benchmark
TERMINAL_STATUSES = {"timeout", "oom"}
CSV_FIELDNAMES = [
    "problem",
    "pq_type",
    "name",
    "instance",
    "threads",
    "batch",
    "status",
    "returncode",
    "time_s",
    "processed_nodes",
    "ignored_nodes",
]

@dataclass(frozen=True)
class Params:
    problem: str | None = None
    pq_type: str | None = None
    name: str | None = None
    instance: str | None = None
    threads: int | None = None
    batch: int | None = None
    stickiness: int | None = None
    num_repetitions: int | None = None

    def __str__(self):
        return (
            f"{self.problem}_{self.pq_type}"
            f"_j={self.threads}"
            f"_b={self.batch}"
            f"_k={self.stickiness}"
            f"_r={self.num_repetitions}"
        )

    def __repr__(self):
        return self.__str__(self)

@dataclass
class BenchmarkResult:
    params: Params
    target: str
    command: str
    status: str
    returncode: int | None
    time_s: float | None
    processed_nodes: int | None
    ignored_nodes: int | None

### Specify benchmark parameters here ###
# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
params_fallback = Params(
    problem="max_clique",
    batch=None,
    stickiness=16,
    num_repetitions=2
)

params_x = [
    Params(pq_type="seq_stack", name="Sequential Stack", threads=1),
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
]

params_y = [
    Params(threads=1),
    Params(threads=2),
    Params(threads=4),
    Params(threads=8),
    Params(threads=16),
    Params(threads=24)
]
### ###


def generate_all_benchmarks(params_x, params_y, params_fallback) -> List[Params]:
    params = []
    
    for param_x in params_x:
        for param_y in params_y:
            combined = {}

            for f in fields(Params):
                val_x = getattr(param_x, f.name)
                val_y = getattr(param_y, f.name)
                val_fallback = getattr(params_fallback, f.name)

                combined[f.name] = (
                    val_x if val_x is not None
                    else val_y if val_y is not None
                    else val_fallback
                )

            if combined["name"] is None:
                combined["name"] = combined["pq_type"]
            if combined["num_repetitions"] is None:
                combined["num_repetitions"] = 1

            params.append(Params(**combined))
    
    # remove duplicates while preserving the order implied by params_x/params_y
    return list(dict.fromkeys(params))

def make_target_name(params: Params) -> str:
    if params.problem is None or params.pq_type is None:
        raise ValueError(f"Missing problem or pq_type in {params}")
    return f"{params.problem}_{params.pq_type}"


def build_target(target: str) -> None:
    cmd = ["cmake", "--build", "build", "--target", target, "-j"]
    print(f"[build] {' '.join(shlex.quote(x) for x in cmd)}")
    subprocess.run(cmd, check=True)


def make_run_command(params: Params) -> list[str]:
    target = make_target_name(params)

    if params.pq_type is None:
        raise ValueError(f"Missing pq_type in {params}")
    if params.instance is None:
        raise ValueError(f"Missing instance in {params}")

    cmd = [
        f"./build/benchmarks/{target}",
        "--instance", params.instance,
    ]

    if params.threads is not None and "seq" not in params.pq_type:
        cmd += ["-j", str(params.threads)]

    if params.batch is not None and "seq" not in params.pq_type:
        cmd += ["-b", str(params.batch)]

    if params.stickiness is not None and "mq_stick_" in params.pq_type:
        cmd += ["--stickiness", str(params.stickiness)]

    return cmd


def parse_time_seconds(output: str) -> float:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                return data["results"]["time_ns"] / 1e9
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    m = re.search(r"Time \(s\):\s*([0-9]*\.?[0-9]+)", output)
    if m:
        return float(m.group(1))

    raise ValueError("Could not find benchmark time in output:\n" + output)

def parse_processed_nodes(output: str) -> int | None:
    m = re.search(r"^Processed nodes:\s*([0-9]+)\s*$", output, re.MULTILINE)
    if m:
        return int(m.group(1))
    return None

def parse_ignored_nodes(output: str) -> int | None:
    m = re.search(r"^Ignored nodes:\s*([0-9]+)\s*$", output, re.MULTILINE)
    if m:
        return int(m.group(1))
    return None

def is_oom_failure(returncode: int, output: str) -> bool:
    if returncode == -signal.SIGKILL:
        return True

    oom_patterns = [
        "std::bad_alloc",
        "bad allocation",
        "cannot allocate memory",
        "out of memory",
    ]
    output_lower = output.lower()
    return any(pattern in output_lower for pattern in oom_patterns)

def failure_status(returncode: int, output: str) -> str:
    if is_oom_failure(returncode, output):
        return "oom"
    return "failed"

def configure_build():
    cmd = ["cmake", "--preset", "default"]
    print(f"[configure] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_benchmark(params: Params, repetitions: int, csv_path: Path) -> list[BenchmarkResult]:
    target = make_target_name(params)
    cmd = make_run_command(params)
    quoted_cmd = " ".join(shlex.quote(x) for x in cmd)
    results: list[BenchmarkResult] = []

    for _ in range(repetitions):
        try:
            completed = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                timeout=TIMEOUT
            )
        except subprocess.TimeoutExpired:
            result = BenchmarkResult(
                params=params,
                target=target,
                command=quoted_cmd,
                status="timeout",
                returncode=None,
                time_s=None,
                processed_nodes=None,
                ignored_nodes=None,
            )
            append_result_to_csv(csv_path, result)
            results.append(result)
            break

        output = completed.stdout + "\n" + completed.stderr
        if completed.returncode != 0:
            result = BenchmarkResult(
                params=params,
                target=target,
                command=quoted_cmd,
                status=failure_status(completed.returncode, output),
                returncode=completed.returncode,
                time_s=None,
                processed_nodes=parse_processed_nodes(output),
                ignored_nodes=parse_ignored_nodes(output),
            )
            append_result_to_csv(csv_path, result)
            results.append(result)
            break

        result = BenchmarkResult(
            params=params,
            target=target,
            command=quoted_cmd,
            status="ok",
            returncode=completed.returncode,
            time_s=parse_time_seconds(output),
            processed_nodes=parse_processed_nodes(output),
            ignored_nodes=parse_ignored_nodes(output),
        )
        append_result_to_csv(csv_path, result)
        results.append(result)

    return results

def instance_name(path: str | None) -> str | None:
    if path is None:
        return None
    return Path(path).stem

def cache_value(value) -> str:
    return "" if value is None else str(value)

def parse_optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)

def params_cache_key(params: Params) -> tuple[str, ...]:
    return (
        cache_value(params.problem),
        cache_value(params.pq_type),
        cache_value(params.name),
        cache_value(instance_name(params.instance)),
        cache_value(params.threads),
        cache_value(params.batch),
    )

def row_cache_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("problem", ""),
        row.get("pq_type", ""),
        row.get("name", ""),
        row.get("instance", ""),
        row.get("threads", ""),
        row.get("batch", ""),
    )

def num_repetitions(params: Params) -> int:
    value = params.num_repetitions if params.num_repetitions is not None else 1
    if value < 1:
        raise ValueError(f"num_repetitions must be at least 1 for {params}")
    return value

def has_terminal_result(results: list[BenchmarkResult]) -> bool:
    return any(result.status in TERMINAL_STATUSES for result in results)

def missing_repetitions(
    cached_results: dict[tuple[str, ...], list[BenchmarkResult]],
    params: Params,
) -> int:
    cached_rows = cached_results.get(params_cache_key(params), [])
    if has_terminal_result(cached_rows):
        return 0

    cached_count = len(cached_rows)
    return max(0, num_repetitions(params) - cached_count)

def has_complete_cached_results(
    cached_results: dict[tuple[str, ...], list[BenchmarkResult]],
    params: Params,
) -> bool:
    return missing_repetitions(cached_results, params) == 0

def ensure_csv(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        write_csv_header(csv_path)
        return

    rows_to_migrate: list[dict[str, str]] | None = None
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        existing_fieldnames = reader.fieldnames or []
        if existing_fieldnames == CSV_FIELDNAMES:
            return

        old_fieldnames = [name for name in CSV_FIELDNAMES if name not in {"status", "returncode"}]
        if existing_fieldnames == old_fieldnames:
            rows_to_migrate = list(reader)

    if rows_to_migrate is not None:
        with csv_path.open("w", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for row in rows_to_migrate:
                row["status"] = "ok" if row.get("time_s") else "timeout"
                row["returncode"] = ""
                writer.writerow(row)
        return

    raise ValueError(
        f"{csv_path} uses CSV fields {existing_fieldnames}, expected {CSV_FIELDNAMES}. "
        "Move or remove the old file before recording raw repetition rows."
    )

def write_csv_header(csv_path: Path) -> None:
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()

def load_cached_results(csv_path: Path) -> dict[tuple[str, ...], list[BenchmarkResult]]:
    cached_results: dict[tuple[str, ...], list[BenchmarkResult]] = {}

    if not csv_path.exists():
        return cached_results

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            time_s = float(row["time_s"]) if row.get("time_s") else None
            params = Params(
                problem=row.get("problem") or None,
                pq_type=row.get("pq_type") or None,
                name=row.get("name") or None,
                instance=row.get("instance") or None,
                threads=parse_optional_int(row.get("threads")),
                batch=parse_optional_int(row.get("batch")),
            )
            returncode = parse_optional_int(row.get("returncode"))
            target = make_target_name(params)
            cached_results.setdefault(row_cache_key(row), []).append(
                BenchmarkResult(
                    params=params,
                    target=target,
                    command="",
                    status=row.get("status") or ("ok" if time_s is not None else "timeout"),
                    returncode=returncode,
                    time_s=time_s,
                    processed_nodes=parse_optional_int(row.get("processed_nodes")),
                    ignored_nodes=parse_optional_int(row.get("ignored_nodes")),
                )
            )

    return cached_results

def append_result_to_csv(csv_path: Path, result: BenchmarkResult) -> None:
    row = {
        "problem": result.params.problem,
        "pq_type": result.params.pq_type,
        "name": result.params.name,
        "instance": instance_name(result.params.instance),
        "threads": result.params.threads,
        "batch": result.params.batch,
        "status": result.status,
        "returncode": result.returncode if result.returncode is not None else "",
        "time_s": result.time_s if result.time_s is not None else "",
        "processed_nodes": result.processed_nodes if result.processed_nodes is not None else "",
        "ignored_nodes": result.ignored_nodes if result.ignored_nodes is not None else "",
    }

    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writerow(row)

def result_summary_label(results: list[BenchmarkResult]) -> str:
    statuses = sorted({result.status for result in results})
    return ", ".join(status.upper() for status in statuses)

def average_completed_time(results: list[BenchmarkResult]) -> float | None:
    completed_times = [result.time_s for result in results if result.time_s is not None]
    if not completed_times:
        return None
    return sum(completed_times) / len(completed_times)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run configured benchmark matrix for an input instance.")
    parser.add_argument("instance", help="Path to the benchmark input instance")
    return parser.parse_args()


def main():
    args = parse_args()
    fallback = replace(params_fallback, instance=args.instance)
    benchmarks = generate_all_benchmarks(params_x, params_y, fallback)
    total = len(benchmarks)
    csv_path = Path(f"benchmark_results_{instance_name(fallback.instance)}.csv")

    print(f"Generated {total} benchmark configurations")
    print(f"Writing results to {csv_path}")

    ensure_csv(csv_path)
    cached_results = load_cached_results(csv_path)
    missing_rows = sum(missing_repetitions(cached_results, params) for params in benchmarks)
    missing_configs = sum(
        missing_repetitions(cached_results, params) > 0 for params in benchmarks
    )
    cached_count = total - missing_configs

    print(
        f"Found {cached_count} fully cached results; "
        f"{missing_configs} benchmarks need {missing_rows} more rows"
    )

    if missing_rows > 0:
        configure_build()

    built_targets: set[str] = set()
    results: list[BenchmarkResult] = []
    ran_count = 0
    skipped_count = 0

    for i, params in enumerate(benchmarks, start=1):
        remaining = total - i
        target = make_target_name(params)
        cache_key = params_cache_key(params)
        cached_result_rows = cached_results.get(cache_key, [])
        missing_rows_for_params = missing_repetitions(cached_results, params)

        if missing_rows_for_params == 0:
            results.extend(cached_result_rows)
            skipped_count += 1
            average_time_s = average_completed_time(cached_result_rows)
            if average_time_s is None:
                print(f"[{i}/{total}] CACHED  {params}  {len(cached_result_rows)} rows, {result_summary_label(cached_result_rows)}")
            elif any(result.status != "ok" for result in cached_result_rows):
                print(
                    f"[{i}/{total}] CACHED  {params}  {len(cached_result_rows)} rows, "
                    f"{result_summary_label(cached_result_rows)}, avg completed={average_time_s:.6f}s"
                )
            else:
                print(f"[{i}/{total}] CACHED  {params}  {len(cached_result_rows)} rows, avg={average_time_s:.6f}s")
            continue

        print(
            f"[{i}/{total}] Running {params} "
            f"({missing_rows_for_params} missing rows, {len(cached_result_rows)} cached, {remaining} configs left)"
        )

        if target not in built_targets:
            build_target(target)
            built_targets.add(target)

        try:
            result_rows = run_benchmark(params, missing_rows_for_params, csv_path)
            results.extend(cached_result_rows)
            results.extend(result_rows)
            cached_results[cache_key] = cached_result_rows + result_rows
            ran_count += 1

            average_time_s = average_completed_time(result_rows)
            if average_time_s is None:
                print(f"[{i}/{total}] {result_summary_label(result_rows)}  {params}")
            elif any(result.status != "ok" for result in result_rows):
                print(
                    f"[{i}/{total}] {result_summary_label(result_rows)}  {params}  "
                    f"added {len(result_rows)} rows, avg completed={average_time_s:.6f}s"
                )
            else:
                print(
                    f"[{i}/{total}] DONE  {params}  "
                    f"added {len(result_rows)} rows, avg added={average_time_s:.6f}s"
                )
        except subprocess.CalledProcessError as e:
            print(f"[{i}/{total}] FAIL  {params}  returncode={e.returncode}")
            if e.stdout:
                print("stdout:")
                print(e.stdout)
            if e.stderr:
                print("stderr:")
                print(e.stderr)
        except Exception as e:
            print(f"[{i}/{total}] FAIL  {params}  error={e}")

    print("\n=== Final summary ===")
    completed_count = sum(result.status == "ok" for result in results)
    print(f"Completed rows: {completed_count}/{len(results)}")
    for status in sorted({result.status for result in results if result.status != "ok"}):
        status_count = sum(result.status == status for result in results)
        print(f"{status.title()} rows: {status_count}/{len(results)}")
    print(f"Cached: {skipped_count}/{total}")
    print(f"Ran: {ran_count}/{total}")
    print(f"CSV file: {csv_path}")

    for r in results:
        if r.status == "ok" and r.time_s is not None:
            print(f"{r.params}, {r.time_s:.6f}s")
        elif r.status == "timeout":
            print(f"{r.params}, TIMEOUT after {TIMEOUT:.0f}s")
        elif r.status == "oom":
            print(f"{r.params}, OOM returncode={r.returncode}")
        else:
            print(f"{r.params}, FAIL status={r.status} returncode={r.returncode}")


if __name__ == "__main__":
    main()
