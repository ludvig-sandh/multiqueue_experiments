from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


CSV_PATH = Path("benchmark_results.csv")
X_AXIS = "threads"
Y_AXIS = "name"

MODE_AXES = {
    "threads": ("threads", "name"),
    "batch": ("batch", "name"),
    "comparison": ("name", "instance"),
}

LAYOUTS = ("heatmap", "graph")
SPREADS = ("none", "minmax", "stddev", "minmax_band", "stddev_band")


def read_results(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["time_s"] = float(row["time_s"]) if row["time_s"] else None
            row["status"] = row.get("status") or ("ok" if row["time_s"] is not None else "timeout")
            rows.append(row)
    return rows


def parse_axis_value(value: str):
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def format_axis_label(axis: str) -> str:
    return axis.replace("_", " ").title()


def unique_in_order(values):
    return list(dict.fromkeys(values))


def failure_status(statuses: list[str]) -> str | None:
    non_ok_statuses = [status.strip() for status in statuses if status.strip() and status.strip() != "ok"]
    if not non_ok_statuses:
        return None
    if "oom" in non_ok_statuses:
        return "oom"
    if "timeout" in non_ok_statuses:
        return "timeout"
    return "failed"


def combine_samples(
    samples: dict[tuple[str, str], dict[object, list[float | None]]],
    sample_statuses: dict[tuple[str, str], dict[object, list[str]]],
):
    grid: dict[tuple[str, str], dict[object, float | None]] = defaultdict(dict)
    failure_grid: dict[tuple[str, str], dict[object, str | None]] = defaultdict(dict)
    for key, row_samples in samples.items():
        for x_value, times in row_samples.items():
            status = failure_status(sample_statuses[key][x_value])
            failure_grid[key][x_value] = status
            if status is not None or any(time_s is None for time_s in times):
                grid[key][x_value] = None
                continue
            grid[key][x_value] = sum(times) / len(times)

    return grid, failure_grid


def build_heatmap_data(rows: list[dict], x_axis: str, y_axis: str):
    if not rows:
        raise ValueError("CSV file contains no benchmark rows")

    missing_axes = sorted(
        axis for axis in {x_axis, y_axis} if axis not in rows[0]
    )
    if missing_axes:
        raise ValueError(
            f"CSV file is missing required column(s): {', '.join(missing_axes)}"
        )

    problems = {row["problem"] for row in rows}
    instances = {row["instance"] for row in rows}

    if len(problems) != 1 or len(instances) != 1:
        raise ValueError(
            "This script expects the CSV to contain exactly one problem and one instance."
        )

    problem = next(iter(problems))
    instance = next(iter(instances))

    x_values = sorted({parse_axis_value(row[x_axis]) for row in rows})

    def row_key(row: dict) -> tuple[str, str]:
        return (
            row[y_axis],
            row["pq_type"],
        )

    unique_row_keys: list[tuple[str, str]] = []
    for row in rows:
        key = row_key(row)
        if key not in unique_row_keys:
            unique_row_keys.append(key)

    def format_row_label(key: tuple[str, str]) -> str:
        y_value, _pq_type = key
        return y_value

    row_labels = [format_row_label(key) for key in unique_row_keys]

    samples: dict[tuple[str, str], dict[object, list[float | None]]] = defaultdict(
        lambda: defaultdict(list)
    )
    sample_statuses: dict[tuple[str, str], dict[object, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        key = row_key(row)
        x_value = parse_axis_value(row[x_axis])
        samples[key][x_value].append(row["time_s"])
        sample_statuses[key][x_value].append(row["status"])

    grid, failure_grid = combine_samples(samples, sample_statuses)

    return problem, instance, unique_row_keys, row_labels, x_values, grid, failure_grid, samples


def build_comparison_data(rows: list[dict]):
    if not rows:
        raise ValueError("CSV file contains no benchmark rows")

    missing_axes = sorted(
        axis for axis in {"problem", "instance", "name"} if axis not in rows[0]
    )
    if missing_axes:
        raise ValueError(
            f"CSV file is missing required column(s): {', '.join(missing_axes)}"
        )

    problems = {row["problem"] for row in rows}
    if len(problems) != 1:
        raise ValueError("Comparison mode expects the CSV to contain exactly one problem.")

    problem = next(iter(problems))
    x_values = unique_in_order(row["name"] for row in rows)
    row_labels = unique_in_order(row["instance"] for row in rows)
    row_keys = [(instance, instance) for instance in row_labels]

    samples: dict[tuple[str, str], dict[object, list[float | None]]] = defaultdict(
        lambda: defaultdict(list)
    )
    sample_statuses: dict[tuple[str, str], dict[object, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        key = (row["instance"], row["instance"])
        x_value = row["name"]
        samples[key][x_value].append(row["time_s"])
        sample_statuses[key][x_value].append(row["status"])

    grid, failure_grid = combine_samples(samples, sample_statuses)

    return problem, "DIMACS comparison", row_keys, row_labels, x_values, grid, failure_grid, samples


def failure_style(status: str) -> tuple[str, str, str, str]:
    if status == "oom":
        return "#bdb2ff", "xx", "OOM", "Out of memory"
    if status == "timeout":
        return "#d9d9d9", "///", "TO", "Timed out"
    return "#f4b6b6", "\\\\\\", "FAIL", "Failed"


def plot_heatmap(
    problem: str,
    instance: str,
    row_keys,
    row_labels,
    x_values,
    grid,
    failure_grid,
    x_axis: str,
    y_axis: str,
) -> None:
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch

    n_rows = len(row_keys)
    n_cols = len(x_values)

    # Collect all times for normalization
    all_times = [
        entry
        for row in grid.values()
        for entry in row.values()
        if entry is not None
    ]

    has_timing_data = bool(all_times)
    if has_timing_data:
        vmin = min(all_times)
        vmax = max(all_times)
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    else:
        norm = None
    cmap = plt.get_cmap("RdYlGn_r")  # reversed so green=fast, red=slow

    fig_width = max(8, 1.4 * n_cols + 3)
    fig_height = max(4, 0.7 * n_rows + 2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    seen_failures: set[str] = set()

    for row_idx in range(n_rows):
        for col_idx in range(n_cols):
            key = row_keys[row_idx]
            x_value = x_values[col_idx]
            has_result = x_value in grid[key]
            value = grid[key].get(x_value)
            status = failure_grid[key].get(x_value)
            baseline_x_value = x_values[0]
            baseline_value = grid[key].get(baseline_x_value)

            label = None
            hatch = None

            if not has_result:
                color = "white"
            elif status is not None:
                color, hatch, label, _legend_label = failure_style(status)
                seen_failures.add(status)
            elif value is None:
                color, hatch, label, _legend_label = failure_style("timeout")
                seen_failures.add("timeout")
            else:
                color = cmap(norm(value)) if norm is not None else "white"
                if baseline_value is not None:
                    speedup = baseline_value / value
                    label = f"{value:.3f}\n({speedup:.1f}x)"
                else:
                    label = f"{value:.3f}"

            rect = plt.Rectangle(
                (col_idx, row_idx),
                1,
                1,
                facecolor=color,
                edgecolor="black",
                linewidth=1.0,
                hatch=hatch,
            )
            ax.add_patch(rect)

            if label is not None:
                ax.text(
                    col_idx + 0.5,
                    row_idx + 0.5,
                    label,
                    ha="center",
                    va="center",
                    fontsize=9,
                )

    ax.set_xlim(0, n_cols)
    ax.set_ylim(0, n_rows)
    ax.invert_yaxis()

    ax.set_xticks([i + 0.5 for i in range(n_cols)])
    ax.set_xticklabels(x_values)
    if x_axis == "name":
        ax.tick_params(axis="x", labelrotation=35)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

    ax.set_yticks([i + 0.5 for i in range(n_rows)])
    ax.set_yticklabels(row_labels)

    ax.set_xlabel(format_axis_label(x_axis))
    ax.set_ylabel(format_axis_label(y_axis))
    ax.set_title(f"{problem} — {instance}")

    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if has_timing_data:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="Time (s)")

    if seen_failures:
        handles = []
        for status in ("timeout", "oom", "failed"):
            if status not in seen_failures:
                continue
            color, hatch, _label, legend_label = failure_style(status)
            handles.append(
                Patch(
                    facecolor=color,
                    edgecolor="black",
                    hatch=hatch,
                    label=legend_label,
                )
            )
        ax.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            borderaxespad=0.0,
        )

    plt.tight_layout()
    plt.show()


def plot_graph(
    problem: str,
    instance: str,
    row_keys,
    row_labels,
    x_values,
    grid,
    samples,
    x_axis: str,
    spread: str,
) -> None:
    fig_width = max(8, 1.2 * len(x_values) + 3)
    fig, ax = plt.subplots(figsize=(fig_width, 5))
    x_positions = {x_value: idx for idx, x_value in enumerate(x_values)}
    band_spread = spread.endswith("_band")
    spread_kind = spread.removesuffix("_band")

    for row_idx, key in enumerate(row_keys):
        points = []
        yerr_lower = []
        yerr_upper = []

        for x_value in x_values:
            mean_time = grid[key].get(x_value)
            if mean_time is None:
                continue

            points.append((x_positions[x_value], mean_time))
            raw_times = [
                time_s
                for time_s in samples[key][x_value]
                if time_s is not None
            ]

            if spread_kind == "minmax" and raw_times:
                yerr_lower.append(mean_time - min(raw_times))
                yerr_upper.append(max(raw_times) - mean_time)
            elif spread_kind == "stddev" and len(raw_times) > 1:
                stddev = statistics.stdev(raw_times)
                yerr_lower.append(stddev)
                yerr_upper.append(stddev)
            else:
                yerr_lower.append(0)
                yerr_upper.append(0)

        if not points:
            continue

        line_x_values = [x_value for x_value, _time_s in points]
        line_times = [time_s for _x_value, time_s in points]
        if band_spread:
            line = ax.plot(
                line_x_values,
                line_times,
                marker="o",
                linewidth=2,
                label=row_labels[row_idx],
            )[0]
            lower = [
                time_s - err for time_s, err in zip(line_times, yerr_lower)
            ]
            upper = [
                time_s + err for time_s, err in zip(line_times, yerr_upper)
            ]
            ax.fill_between(
                line_x_values,
                lower,
                upper,
                color=line.get_color(),
                alpha=0.18,
                linewidth=0,
            )
        else:
            yerr = [yerr_lower, yerr_upper] if spread != "none" else None
            ax.errorbar(
                line_x_values,
                line_times,
                yerr=yerr,
                marker="o",
                linewidth=2,
                capsize=4 if spread != "none" else 0,
                label=row_labels[row_idx],
            )

    ax.set_xticks(range(len(x_values)))
    ax.set_xticklabels(x_values)
    ax.set_xlabel(format_axis_label(x_axis))
    ax.set_ylabel("Execution Time (s)")
    ax.set_title(f"{problem} — {instance}")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0.0)

    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path, default=CSV_PATH)
    parser.add_argument("--mode", choices=MODE_AXES)
    parser.add_argument("--layout", choices=LAYOUTS, default="heatmap")
    parser.add_argument("--spread", choices=SPREADS, default="none")
    args = parser.parse_args()

    x_axis, y_axis = MODE_AXES[args.mode] if args.mode else (X_AXIS, Y_AXIS)

    csv_path = args.csv_path
    rows = read_results(csv_path)
    if args.mode == "comparison":
        if args.layout == "graph":
            raise ValueError("Comparison mode is only supported with --layout heatmap.")
        (
            problem,
            instance,
            row_keys,
            row_labels,
            x_values,
            grid,
            failure_grid,
            samples,
        ) = build_comparison_data(rows)
    else:
        (
            problem,
            instance,
            row_keys,
            row_labels,
            x_values,
            grid,
            failure_grid,
            samples,
        ) = build_heatmap_data(rows, x_axis, y_axis)
    if args.layout == "graph":
        plot_graph(
            problem,
            instance,
            row_keys,
            row_labels,
            x_values,
            grid,
            samples,
            x_axis,
            args.spread,
        )
    else:
        plot_heatmap(
            problem,
            instance,
            row_keys,
            row_labels,
            x_values,
            grid,
            failure_grid,
            x_axis,
            y_axis,
        )


if __name__ == "__main__":
    main()
