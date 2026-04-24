from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


CSV_PATH = Path("benchmark_results.csv")


def read_results(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["threads"] = int(row["threads"])
            row["batch"] = int(row["batch"]) if row["batch"] else None
            row["stickiness"] = int(row["stickiness"]) if row["stickiness"] else None
            row["time_s"] = float(row["time_s"]) if row["time_s"] else None
            rows.append(row)
    return rows


def build_heatmap_data(rows: list[dict]):
    if not rows:
        raise ValueError("CSV file contains no benchmark rows")

    problems = {row["problem"] for row in rows}
    instances = {row["instance"] for row in rows}

    if len(problems) != 1 or len(instances) != 1:
        raise ValueError(
            "This script expects the CSV to contain exactly one problem and one instance."
        )

    problem = next(iter(problems))
    instance = next(iter(instances))

    thread_values = sorted({row["threads"] for row in rows})

    def row_key(row: dict) -> tuple[str, int | None, int | None]:
        return (
            row["pq_type"],
            row["batch"],
            row["stickiness"],
        )

    unique_row_keys = sorted({row_key(row) for row in rows})

    def format_row_label(key: tuple[str, int | None, int | None]) -> str:
        pq_type, batch, stickiness = key
        parts = [pq_type]
        if batch is not None:
            parts.append(f"b={batch}")
        if stickiness is not None:
            parts.append(f"k={stickiness}")
        return "  ".join(parts)

    row_labels = [format_row_label(key) for key in unique_row_keys]

    grid: dict[tuple[str, int | None, int | None], dict[int, float | None]] = defaultdict(dict)
    for row in rows:
        key = row_key(row)
        threads = row["threads"]
        grid[key][threads] = row["time_s"]

    return problem, instance, unique_row_keys, row_labels, thread_values, grid


def plot_heatmap(
    problem: str,
    instance: str,
    row_keys,
    row_labels,
    thread_values,
    grid,
) -> None:
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch

    n_rows = len(row_keys)
    n_cols = len(thread_values)

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
    saw_timeout = False

    for row_idx in range(n_rows):
        for col_idx in range(n_cols):
            key = row_keys[row_idx]
            threads = thread_values[col_idx]
            has_result = threads in grid[key]
            value = grid[key].get(threads)

            label = None
            hatch = None

            if not has_result:
                color = "white"
            elif value is None:
                color = "#d9d9d9"
                hatch = "///"
                label = "TO"
                saw_timeout = True
            else:
                color = cmap(norm(value)) if norm is not None else "white"
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
    ax.set_xticklabels(thread_values)

    ax.set_yticks([i + 0.5 for i in range(n_rows)])
    ax.set_yticklabels(row_labels)

    ax.set_xlabel("Threads")
    ax.set_ylabel("Priority Queue / Parameters")
    ax.set_title(f"{problem} — {instance}")

    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if has_timing_data:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="Time (s)")

    if saw_timeout:
        ax.legend(
            handles=[Patch(facecolor="#d9d9d9", edgecolor="black", hatch="///", label="Timed out")],
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            borderaxespad=0.0,
        )

    plt.tight_layout()
    plt.show()


def main() -> None:
    rows = read_results(CSV_PATH)
    problem, instance, row_keys, row_labels, thread_values, grid = build_heatmap_data(rows)
    plot_heatmap(problem, instance, row_keys, row_labels, thread_values, grid)


if __name__ == "__main__":
    main()
