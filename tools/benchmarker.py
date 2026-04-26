import csv
import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import List

TIMEOUT = 60*5  # Seconds allowed per benchmark
CSV_FIELDNAMES = [
    "problem",
    "pq_type",
    "name",
    "instance",
    "threads",
    "batch",
    "stickiness",
    "num_repetitions",
    "time_s",
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
    command: list[str]
    time_s: float | None

### Specify benchmark parameters here ###
# Set num_repetitions in params_x, params_y, or params_fallback.
# Omitted values resolve to 1 after benchmark parameters are combined.
params_fallback = Params(
    problem="max_clique",
    instance="data/DIMACS_all_ascii/brock200_1.clq",
    threads=1,
    batch=1,
    stickiness=16,
    num_repetitions=1
)

params_x = [
    Params(pq_type="seq_stack", name="Sequential Stack", threads=1),
    Params(pq_type="locked_stack", name="Globally locked Stack"),
    Params(pq_type="multilifo", name="MultiLIFO", num_repetitions=20),
    Params(pq_type="work_stealing", name="Simple work stealing"),
    Params(pq_type="seq_pq", name="Sequential PQ", threads=1),
    Params(pq_type="locked_pq", name="Globally locked PQ"),
    Params(pq_type="mq_stick_swap", name="MultiQueue (stick swap, batch=16)", batch=16),
    Params(pq_type="pmc", name="PMC library")
]

params_y = [
    Params(threads=1),
    Params(threads=2),
    Params(threads=4),
    Params(threads=8),
    Params(threads=16),
    Params(threads=24),
    # Params(threads=72),
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

def configure_build():
    cmd = ["cmake", "--preset", "default"]
    print(f"[configure] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_benchmark(params: Params) -> BenchmarkResult:
    target = make_target_name(params)
    cmd = make_run_command(params)
    quoted_cmd = " ".join(shlex.quote(x) for x in cmd)
    total_time_s = 0.0

    num_repetitions = params.num_repetitions if params.num_repetitions is not None else 1
    if num_repetitions < 1:
        raise ValueError(f"num_repetitions must be at least 1 for {params}")

    for _ in range(num_repetitions):
        try:
            completed = subprocess.run(
                cmd,
                check=True,
                text=True,
                capture_output=True,
                timeout=TIMEOUT
            )
        except subprocess.TimeoutExpired:
            return BenchmarkResult(
                params=params,
                target=target,
                command=quoted_cmd,
                time_s=None,
            )
        total_time_s += parse_time_seconds(completed.stdout)

    return BenchmarkResult(
        params=params,
        target=target,
        command=quoted_cmd,
        time_s=total_time_s / num_repetitions,
    )

def instance_name(path: str | None) -> str | None:
    if path is None:
        return None
    return Path(path).stem

def cache_value(value) -> str:
    return "" if value is None else str(value)

def params_cache_key(params: Params) -> tuple[str, ...]:
    return (
        cache_value(params.problem),
        cache_value(params.pq_type),
        cache_value(params.name),
        cache_value(instance_name(params.instance)),
        cache_value(params.threads),
        cache_value(params.batch),
        cache_value(params.stickiness),
        cache_value(params.num_repetitions),
    )

def row_cache_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("problem", ""),
        row.get("pq_type", ""),
        row.get("name", ""),
        row.get("instance", ""),
        row.get("threads", ""),
        row.get("batch", ""),
        row.get("stickiness", ""),
        row.get("num_repetitions", "1"),
    )

def ensure_csv(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        write_csv_header(csv_path)
        return

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        existing_fieldnames = reader.fieldnames or []
        if existing_fieldnames == CSV_FIELDNAMES:
            return

        rows = list(reader)

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            normalized_row = {
                field: row.get(field, "1" if field == "num_repetitions" else "")
                for field in CSV_FIELDNAMES
            }
            writer.writerow(normalized_row)

def write_csv_header(csv_path: Path) -> None:
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()

def load_cached_results(csv_path: Path) -> dict[tuple[str, ...], float | None]:
    cached_results: dict[tuple[str, ...], float | None] = {}

    if not csv_path.exists():
        return cached_results

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            time_s = float(row["time_s"]) if row.get("time_s") else None
            cached_results[row_cache_key(row)] = time_s

    return cached_results

def append_result_to_csv(csv_path: Path, result: BenchmarkResult) -> None:
    row = asdict(result.params)
    row["instance"] = instance_name(row["instance"])
    row["time_s"] = result.time_s if result.time_s is not None else ""

    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writerow(row)


def main():
    benchmarks = generate_all_benchmarks(params_x, params_y, params_fallback)
    total = len(benchmarks)
    csv_path = Path("benchmark_results.csv")

    print(f"Generated {total} benchmark configurations")
    print(f"Writing results to {csv_path}")

    ensure_csv(csv_path)
    cached_results = load_cached_results(csv_path)
    missing_count = sum(
        params_cache_key(params) not in cached_results
        for params in benchmarks
    )
    cached_count = total - missing_count

    print(f"Found {cached_count} cached results; {missing_count} benchmarks to run")

    if missing_count > 0:
        configure_build()

    built_targets: set[str] = set()
    results: list[BenchmarkResult] = []
    ran_count = 0
    skipped_count = 0

    for i, params in enumerate(benchmarks, start=1):
        remaining = total - i
        target = make_target_name(params)
        cache_key = params_cache_key(params)

        if cache_key in cached_results:
            result = BenchmarkResult(
                params=params,
                target=target,
                command=" ".join(shlex.quote(x) for x in make_run_command(params)),
                time_s=cached_results[cache_key],
            )
            results.append(result)
            skipped_count += 1
            if result.time_s is None:
                print(f"[{i}/{total}] CACHED  {params}  TIMEOUT")
            else:
                print(f"[{i}/{total}] CACHED  {params}  time={result.time_s:.6f}s")
            continue

        print(f"[{i}/{total}] Running {params} ({remaining} left)")

        if target not in built_targets:
            build_target(target)
            built_targets.add(target)

        try:
            result = run_benchmark(params)
            results.append(result)
            append_result_to_csv(csv_path, result)
            cached_results[cache_key] = result.time_s
            ran_count += 1

            if result.time_s is None:
                print(f"[{i}/{total}] TIMEOUT  {result.params}  after {TIMEOUT:.0f}s")
            else:
                print(f"[{i}/{total}] DONE  {result.params}  time={result.time_s:.6f}s")
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
    completed_count = sum(result.time_s is not None for result in results)
    timeout_count = sum(result.time_s is None for result in results)
    print(f"Completed: {completed_count}/{total}")
    print(f"Timed out: {timeout_count}/{total}")
    print(f"Cached: {skipped_count}/{total}")
    print(f"Ran: {ran_count}/{total}")
    print(f"CSV file: {csv_path}")

    for r in results:
        if r.time_s is None:
            print(f"{r.params}, TIMEOUT after {TIMEOUT:.0f}s")
        else:
            print(f"{r.params}, {r.time_s:.6f}s")


if __name__ == "__main__":
    main()
