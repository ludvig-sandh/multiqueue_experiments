from __future__ import annotations

import csv
from pathlib import Path


PQ_TYPE_ORDER = [
    "locked_stack",    # Globally locked Stack
    "treiber_stack",   # Treiber stack
    "multilifo",       # MultiLIFO
    "2d_stack",        # 2D-stack
    "work_stealing",   # Simple work stealing
    "locked_pq",       # Globally locked PQ
    "pr",              # Linden
    "mq_stick_swap",   # MultiQueue (stick swap)
    "pmc",             # PMC
    "pbs",             # PBS
    "ciaranm",         # McCreesh
]


def main() -> None:
    csv_path = Path(__file__).with_name("comparison_dimacs.csv")

    with csv_path.open(newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        if not fieldnames or "pq_type" not in fieldnames:
            raise ValueError("comparison_dimacs.csv must contain a 'pq_type' column")
        rows = list(reader)

    order_index = {pq_type: index for index, pq_type in enumerate(PQ_TYPE_ORDER)}
    default_index = len(PQ_TYPE_ORDER)
    rows.sort(key=lambda row: (order_index.get(row["pq_type"], default_index), row["pq_type"]))

    with csv_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
