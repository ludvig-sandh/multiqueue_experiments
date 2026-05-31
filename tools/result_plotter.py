from __future__ import annotations

import argparse
import csv
import math
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
    "stickiness": ("stickiness", "name"),
    "comparison": ("name", "instance"),
}

LAYOUTS = ("heatmap", "graph")
SPREADS = ("none", "minmax", "stddev", "minmax_band", "stddev_band")
HEATMAP_COLOR_MODES = ("time", "row-slowdown", "row_slowdown")
HEATMAP_WIDTH_MODES = ("auto", "regular", "compact")
VALUES = ("time", "visited-nodes", "work-amplification", "efficiency")

TITLE_FONT_SIZE = 15
AXIS_LABEL_FONT_SIZE = 13
TICK_LABEL_FONT_SIZE = 11
CELL_LABEL_FONT_SIZE = 11
LEGEND_FONT_SIZE = 11
COLORBAR_LABEL_FONT_SIZE = 12
COLORBAR_TICK_FONT_SIZE = 11
BEST_TILE_EDGE_COLOR = "#f2b705"
BEST_TILE_LINE_WIDTH = 2.6


def read_results(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["time_s"] = float(row["time_s"]) if row["time_s"] else None
            row["processed_nodes"] = (
                float(row["processed_nodes"]) if row.get("processed_nodes") else None
            )
            row["ignored_nodes"] = (
                float(row["ignored_nodes"]) if row.get("ignored_nodes") else None
            )
            row["visited_nodes"] = (
                row["processed_nodes"] + (row["ignored_nodes"] or 0)
                if row["processed_nodes"] is not None
                else None
            )
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


def format_multiplier(value: float) -> str:
    if value < 10:
        return f"{value:.1f}x"
    return f"{value:g}x"


def format_value(value: float, value_kind: str) -> str:
    if value_kind == "visited-nodes":
        return format_compact_count(value)
    if value_kind == "work-amplification":
        return f"{value:.2f}x"
    if value_kind == "efficiency":
        if abs(value) < 0.1:
            return f"{value:.1%}"
        return f"{value:.0%}"
    return f"{value:.3f}"


def format_compact_count(value: float) -> str:
    for suffix, factor in (("G", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if abs(value) >= factor:
            scaled = round(value / factor, 1)
            if suffix == "K" and abs(scaled) >= 10:
                return f"{scaled:.0f}{suffix}"
            if scaled.is_integer():
                return f"{scaled:.0f}{suffix}"
            return f"{scaled:.1f}{suffix}"
    return f"{value:.0f}"


def value_column(value_kind: str) -> str:
    if value_kind in {"visited-nodes", "work-amplification"}:
        return "visited_nodes"
    return "time_s"


def value_label(value_kind: str) -> str:
    if value_kind == "visited-nodes":
        return "Visited Nodes"
    if value_kind == "work-amplification":
        return "Work Amplification"
    if value_kind == "efficiency":
        return "Parallel Efficiency"
    return "Time (s)"


def row_best_ratio_label(value_kind: str) -> str:
    if value_kind == "visited-nodes":
        return "Increase vs row best"
    if value_kind == "work-amplification":
        return "Increase vs row best"
    if value_kind == "efficiency":
        return "Drop vs row best"
    return "Slowdown vs row best"


def higher_is_better(value_kind: str) -> bool:
    return value_kind == "efficiency"


def mark_best_label(label: str) -> str:
    lines = label.splitlines()
    lines[0] += r" $\star$"
    return "\n".join(lines)


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


def combine_processed_share(
    processed_share_samples: dict[
        tuple[str, str], dict[object, list[tuple[float | None, float | None, float | None]]]
    ],
    sample_statuses: dict[tuple[str, str], dict[object, list[str]]],
):
    grid: dict[tuple[str, str], dict[object, float | None]] = defaultdict(dict)
    for key, row_samples in processed_share_samples.items():
        for x_value, samples in row_samples.items():
            if failure_status(sample_statuses[key][x_value]) is not None:
                grid[key][x_value] = None
                continue

            valid_samples = [
                (processed_nodes, ignored_nodes, visited_nodes)
                for processed_nodes, ignored_nodes, visited_nodes in samples
                if (
                    processed_nodes is not None
                    and ignored_nodes is not None
                    and visited_nodes is not None
                    and visited_nodes > 0
                )
            ]
            if not valid_samples:
                grid[key][x_value] = None
                continue

            processed_sum = sum(
                processed_nodes
                for processed_nodes, _ignored_nodes, _visited_nodes in valid_samples
            )
            visited_sum = sum(
                visited_nodes
                for _processed_nodes, _ignored_nodes, visited_nodes in valid_samples
            )
            grid[key][x_value] = processed_sum / visited_sum if visited_sum > 0 else None

    return grid


def filter_empty_rows(row_keys, row_labels, grid):
    filtered_keys = []
    filtered_labels = []
    for key, label in zip(row_keys, row_labels):
        if any(value is not None for value in grid[key].values()):
            filtered_keys.append(key)
            filtered_labels.append(label)
    return filtered_keys, filtered_labels


def normalize_to_row_baseline(grid, samples, x_values):
    normalized_grid: dict[tuple[str, str], dict[object, float | None]] = defaultdict(dict)
    normalized_samples: dict[tuple[str, str], dict[object, list[float | None]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for key, row_values in grid.items():
        baseline_value = next(
            (
                row_values[x_value]
                for x_value in x_values
                if row_values.get(x_value) is not None and row_values[x_value] > 0
            ),
            None,
        )

        for x_value in x_values:
            value = row_values.get(x_value)
            if baseline_value is None or value is None:
                normalized_grid[key][x_value] = None
            else:
                normalized_grid[key][x_value] = value / baseline_value

            normalized_samples[key][x_value] = [
                sample / baseline_value
                if baseline_value is not None and sample is not None
                else None
                for sample in samples[key][x_value]
            ]

    return normalized_grid, normalized_samples


def normalize_to_efficiency(grid, samples, thread_samples, x_values):
    efficiency_grid: dict[tuple[str, str], dict[object, float | None]] = defaultdict(dict)
    efficiency_samples: dict[tuple[str, str], dict[object, list[float | None]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for key, row_values in grid.items():
        baseline_time = next(
            (
                row_values[x_value]
                for x_value in x_values
                if row_values.get(x_value) is not None and row_values[x_value] > 0
            ),
            None,
        )

        for x_value in x_values:
            value = row_values.get(x_value)
            threads = [
                thread_count
                for thread_count in thread_samples[key][x_value]
                if thread_count is not None and thread_count > 0
            ]
            mean_threads = sum(threads) / len(threads) if threads else None

            if baseline_time is None or value is None or mean_threads is None:
                efficiency_grid[key][x_value] = None
            else:
                efficiency_grid[key][x_value] = (baseline_time / value) / mean_threads

            efficiency_samples[key][x_value] = [
                (baseline_time / sample) / mean_threads
                if (
                    baseline_time is not None
                    and sample is not None
                    and sample > 0
                    and mean_threads is not None
                )
                else None
                for sample in samples[key][x_value]
            ]

    return efficiency_grid, efficiency_samples


def build_heatmap_data(rows: list[dict], x_axis: str, y_axis: str, value_kind: str):
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
    processed_share_samples: dict[
        tuple[str, str], dict[object, list[tuple[float | None, float | None, float | None]]]
    ] = defaultdict(lambda: defaultdict(list))
    thread_samples: dict[tuple[str, str], dict[object, list[float | None]]] = defaultdict(
        lambda: defaultdict(list)
    )
    sample_statuses: dict[tuple[str, str], dict[object, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        key = row_key(row)
        x_value = parse_axis_value(row[x_axis])
        samples[key][x_value].append(row[value_column(value_kind)])
        thread_samples[key][x_value].append(
            float(row["threads"]) if row.get("threads") else None
        )
        processed_share_samples[key][x_value].append(
            (row["processed_nodes"], row["ignored_nodes"], row["visited_nodes"])
        )
        sample_statuses[key][x_value].append(row["status"])

    grid, failure_grid = combine_samples(samples, sample_statuses)
    processed_share_grid = combine_processed_share(processed_share_samples, sample_statuses)
    if value_kind == "work-amplification":
        grid, samples = normalize_to_row_baseline(grid, samples, x_values)
    elif value_kind == "efficiency":
        grid, samples = normalize_to_efficiency(grid, samples, thread_samples, x_values)
    unique_row_keys, row_labels = filter_empty_rows(unique_row_keys, row_labels, grid)

    return (
        problem,
        instance,
        unique_row_keys,
        row_labels,
        x_values,
        grid,
        failure_grid,
        samples,
        processed_share_grid,
    )


def build_comparison_data(rows: list[dict], value_kind: str):
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
    processed_share_samples: dict[
        tuple[str, str], dict[object, list[tuple[float | None, float | None, float | None]]]
    ] = defaultdict(lambda: defaultdict(list))
    thread_samples: dict[tuple[str, str], dict[object, list[float | None]]] = defaultdict(
        lambda: defaultdict(list)
    )
    sample_statuses: dict[tuple[str, str], dict[object, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        key = (row["instance"], row["instance"])
        x_value = row["name"]
        samples[key][x_value].append(row[value_column(value_kind)])
        thread_samples[key][x_value].append(
            float(row["threads"]) if row.get("threads") else None
        )
        processed_share_samples[key][x_value].append(
            (row["processed_nodes"], row["ignored_nodes"], row["visited_nodes"])
        )
        sample_statuses[key][x_value].append(row["status"])

    grid, failure_grid = combine_samples(samples, sample_statuses)
    processed_share_grid = combine_processed_share(processed_share_samples, sample_statuses)
    if value_kind == "work-amplification":
        grid, samples = normalize_to_row_baseline(grid, samples, x_values)
    elif value_kind == "efficiency":
        grid, samples = normalize_to_efficiency(grid, samples, thread_samples, x_values)
    row_keys, row_labels = filter_empty_rows(row_keys, row_labels, grid)

    return (
        problem,
        "DIMACS comparison",
        row_keys,
        row_labels,
        x_values,
        grid,
        failure_grid,
        samples,
        processed_share_grid,
    )


def failure_style(status: str) -> tuple[str, str, str, str]:
    if status == "oom":
        return "#bdb2ff", "xx", "OOM", "Out of memory"
    if status == "timeout":
        return "#d9d9d9", "///", "TO", "Timed out"
    return "#f4b6b6", "\\\\\\", "FAIL", "Failed"


def graph_colors(count: int):
    colors = []
    for cmap_name in ("tab20", "tab20b", "tab20c"):
        colors.extend(plt.get_cmap(cmap_name).colors)
    if count <= len(colors):
        return colors[:count]

    fallback_cmap = plt.get_cmap("hsv")
    colors.extend(fallback_cmap(i / (count - len(colors))) for i in range(count - len(colors)))
    return colors


def plot_heatmap(
    problem: str,
    instance: str,
    row_keys,
    row_labels,
    x_values,
    grid,
    failure_grid,
    processed_share_grid,
    x_axis: str,
    y_axis: str,
    color_mode: str,
    value_kind: str,
    mark_row_best: bool = False,
    compact_columns: bool = False,
) -> None:
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch

    n_rows = len(row_keys)
    n_cols = len(x_values)

    # Collect all values for normalization.
    all_values = [
        entry
        for row in grid.values()
        for entry in row.values()
        if entry is not None
    ]

    row_best_value = max if higher_is_better(value_kind) else min
    row_best_times = {
        key: row_best_value(
            value
            for value in (grid[key].get(x_value) for x_value in x_values)
            if value is not None
        )
        for key in row_keys
        if any(grid[key].get(x_value) is not None for x_value in x_values)
    }
    all_slowdowns = [
        row_best_times[key] / value
        if higher_is_better(value_kind)
        else value / row_best_times[key]
        for key in row_keys
        if key in row_best_times
        for value in (grid[key].get(x_value) for x_value in x_values)
        if value is not None
    ]
    max_slowdown = max(all_slowdowns) if all_slowdowns else None

    has_value_data = bool(all_values)
    if color_mode == "time" and has_value_data:
        vmin = min(all_values)
        vmax = max(all_values)
        if vmin <= 0:
            raise ValueError("Logarithmic heatmap colors require all plotted values to be positive.")
        norm = mcolors.LogNorm(vmin=vmin, vmax=vmax)
        colorbar_label = value_label(value_kind)
    elif color_mode == "row-slowdown" and max_slowdown is not None:
        norm = mcolors.LogNorm(vmin=1.0, vmax=max(max_slowdown, 1.000001))
        colorbar_label = row_best_ratio_label(value_kind)
    else:
        norm = None
        colorbar_label = value_label(value_kind)
    if color_mode == "row-slowdown":
        cmap = plt.get_cmap("RdYlGn_r")  # green=best, red=worse than row best
    elif higher_is_better(value_kind):
        cmap = plt.get_cmap("RdYlGn")
    else:
        cmap = plt.get_cmap("RdYlGn_r")  # green=low, red=high

    if compact_columns:
        fig_width = max(6.6, 0.75 * n_cols + 2.4)
    else:
        fig_width = max(7.8, 1.2 * n_cols + 2.8)
    fig_height = max(3.2, 0.42 * n_rows + 1.8)
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
            best_value = row_best_times.get(key)

            label = None
            hatch = None
            is_row_best = (
                mark_row_best
                and value is not None
                and best_value is not None
                and math.isclose(value, best_value)
            )

            if not has_result:
                color = "white"
            elif status is not None:
                color, hatch, label, _legend_label = failure_style(status)
                seen_failures.add(status)
            elif value is None:
                color = "white"
            else:
                if color_mode == "row-slowdown" and best_value is not None:
                    slowdown = best_value / value if higher_is_better(value_kind) else value / best_value
                    color = cmap(norm(slowdown)) if norm is not None else "white"
                    if value_kind == "visited-nodes":
                        processed_share = processed_share_grid[key].get(x_value)
                        if processed_share is not None:
                            label = f"{format_value(value, value_kind)}\n({processed_share:.0%})"
                        else:
                            label = f"{format_value(value, value_kind)}\n(n/a)"
                    elif value_kind == "work-amplification":
                        label = format_value(value, value_kind)
                    elif value_kind == "efficiency":
                        label = format_value(value, value_kind)
                    else:
                        label = f"{format_value(value, value_kind)}\n({slowdown:.1f}x)"
                else:
                    color = cmap(norm(value)) if norm is not None else "white"
                    if value_kind == "visited-nodes":
                        processed_share = processed_share_grid[key].get(x_value)
                        if processed_share is not None:
                            label = f"{format_value(value, value_kind)}\n({processed_share:.0%})"
                        else:
                            label = f"{format_value(value, value_kind)}\n(n/a)"
                    elif value_kind == "work-amplification":
                        label = format_value(value, value_kind)
                    elif value_kind == "efficiency":
                        label = format_value(value, value_kind)
                    elif baseline_value is not None:
                        speedup = baseline_value / value
                        label = f"{format_value(value, value_kind)}\n({speedup:.1f}x)"
                    else:
                        label = format_value(value, value_kind)
                if is_row_best:
                    label = mark_best_label(label)

            rect = plt.Rectangle(
                (col_idx, row_idx),
                1,
                1,
                facecolor=color,
                edgecolor=BEST_TILE_EDGE_COLOR if is_row_best else "black",
                linewidth=BEST_TILE_LINE_WIDTH if is_row_best else 1.0,
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
                    fontsize=CELL_LABEL_FONT_SIZE,
                    fontweight="bold" if is_row_best else "normal",
                    linespacing=0.9,
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

    ax.set_xlabel(format_axis_label(x_axis), fontsize=AXIS_LABEL_FONT_SIZE, labelpad=5)
    ax.set_ylabel(format_axis_label(y_axis), fontsize=AXIS_LABEL_FONT_SIZE, labelpad=5)
    ax.set_title(f"{problem} - {instance}", fontsize=TITLE_FONT_SIZE, pad=8)

    ax.tick_params(length=0, labelsize=TICK_LABEL_FONT_SIZE, pad=2)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if has_value_data:
        from matplotlib.ticker import FuncFormatter

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        colorbar = plt.colorbar(sm, ax=ax, label=colorbar_label, pad=0.015, fraction=0.04)
        colorbar.ax.tick_params(labelsize=COLORBAR_TICK_FONT_SIZE)
        colorbar.set_label(colorbar_label, fontsize=COLORBAR_LABEL_FONT_SIZE)
        if color_mode == "row-slowdown":
            ticks = [1.0]
            tick = 10.0
            while max_slowdown is not None and tick < max_slowdown:
                ticks.append(tick)
                tick *= 10.0
            colorbar.set_ticks(ticks)
            colorbar.ax.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _pos: format_multiplier(value))
            )

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
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            borderaxespad=0.0,
            frameon=False,
            ncol=len(handles),
            fontsize=LEGEND_FONT_SIZE,
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
    value_kind: str,
) -> None:
    fig_width = max(6.8, 0.75 * len(x_values) + 2.8)
    fig, ax = plt.subplots(figsize=(fig_width, 4.6))
    x_positions = {x_value: idx for idx, x_value in enumerate(x_values)}
    band_spread = spread.endswith("_band")
    spread_kind = spread.removesuffix("_band")
    colors = graph_colors(len(row_keys))

    for row_idx, key in enumerate(row_keys):
        color = colors[row_idx]
        points = []
        yerr_lower = []
        yerr_upper = []

        for x_value in x_values:
            mean_value = grid[key].get(x_value)
            if mean_value is None:
                continue

            points.append((x_positions[x_value], mean_value))
            raw_values = [
                value
                for value in samples[key][x_value]
                if value is not None
            ]

            if spread_kind == "minmax" and raw_values:
                yerr_lower.append(mean_value - min(raw_values))
                yerr_upper.append(max(raw_values) - mean_value)
            elif spread_kind == "stddev" and len(raw_values) > 1:
                stddev = statistics.stdev(raw_values)
                yerr_lower.append(stddev)
                yerr_upper.append(stddev)
            else:
                yerr_lower.append(0)
                yerr_upper.append(0)

        if not points:
            continue

        line_x_values = [x_value for x_value, _value in points]
        line_values = [value for _x_value, value in points]
        if band_spread:
            line = ax.plot(
                line_x_values,
                line_values,
                marker="o",
                linewidth=2.5,
                color=color,
                label=row_labels[row_idx],
            )[0]
            lower = [
                max(value - err, value * 1e-12)
                for value, err in zip(line_values, yerr_lower)
            ]
            upper = [
                value + err for value, err in zip(line_values, yerr_upper)
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
            if spread != "none":
                log_yerr_lower = [
                    min(err, value * (1 - 1e-12))
                    for value, err in zip(line_values, yerr_lower)
                ]
                yerr = [log_yerr_lower, yerr_upper]
            else:
                yerr = None
            ax.errorbar(
                line_x_values,
                line_values,
                yerr=yerr,
                marker="o",
                linewidth=2.5,
                color=color,
                capsize=4 if spread != "none" else 0,
                label=row_labels[row_idx],
            )

    ax.set_xticks(range(len(x_values)))
    ax.set_xticklabels(x_values)
    ax.set_xlabel(format_axis_label(x_axis), fontsize=AXIS_LABEL_FONT_SIZE, labelpad=5)
    ax.set_ylabel(value_label(value_kind), fontsize=AXIS_LABEL_FONT_SIZE, labelpad=5)
    ax.set_yscale("log")
    ax.set_title(f"{problem} — {instance}", fontsize=TITLE_FONT_SIZE, pad=8)
    ax.tick_params(axis="both", labelsize=TICK_LABEL_FONT_SIZE)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        fontsize=LEGEND_FONT_SIZE,
    )

    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", type=Path, default=CSV_PATH)
    parser.add_argument("--mode", choices=MODE_AXES)
    parser.add_argument("--layout", choices=LAYOUTS, default="heatmap")
    parser.add_argument("--spread", choices=SPREADS, default="none")
    parser.add_argument("--heatmap-colors", choices=HEATMAP_COLOR_MODES, default="time")
    parser.add_argument("--heatmap-width", choices=HEATMAP_WIDTH_MODES, default="auto")
    parser.add_argument("--value", choices=VALUES, default="time")
    args = parser.parse_args()
    heatmap_colors = args.heatmap_colors.replace("_", "-")
    compact_heatmap = (
        args.heatmap_width == "compact"
        or (args.heatmap_width == "auto" and args.mode == "comparison")
    )

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
            processed_share_grid,
        ) = build_comparison_data(rows, args.value)
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
            processed_share_grid,
        ) = build_heatmap_data(rows, x_axis, y_axis, args.value)
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
            args.value,
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
            processed_share_grid,
            x_axis,
            y_axis,
            heatmap_colors,
            args.value,
            mark_row_best=args.mode == "comparison",
            compact_columns=compact_heatmap,
        )


if __name__ == "__main__":
    main()
