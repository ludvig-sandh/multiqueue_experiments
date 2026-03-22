import pandas as pd
import matplotlib.pyplot as plt
import argparse


def plot_csv(file_path):
    df = pd.read_csv(file_path)

    required_columns = {"queue_type", "num_threads", "exec_time"}
    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"CSV must contain columns: {required_columns}\n"
            f"Found: {list(df.columns)}"
        )

    # Aggregate in case of duplicates
    df = df.groupby(["queue_type", "num_threads"], as_index=False)["exec_time"].mean()
    df = df.sort_values(by="num_threads")

    # Plot actual data
    for queue_type in df["queue_type"].unique():
        subset = df[df["queue_type"] == queue_type]
        plt.plot(
            subset["num_threads"],
            subset["exec_time"],
            marker="o",
            label=queue_type
        )

    # ---- SINGLE IDEAL LINE (based on seq) ----
    seq = df[(df["queue_type"] == "seq") & (df["num_threads"] == 1)]
    if not seq.empty:
        t1 = seq["exec_time"].values[0]

        threads = sorted(df["num_threads"].unique())
        ideal = [t1 / t for t in threads]

        plt.plot(
            threads,
            ideal,
            linestyle="--",
            linewidth=2,
            label="ideal linear scaling"
        )
    else:
        print("Warning: No seq baseline found for ideal scaling line")

    # Labels
    plt.xlabel("Number of threads")
    plt.ylabel("Execution time")
    plt.title("Execution time vs threads (with ideal scaling reference)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file")
    args = parser.parse_args()

    plot_csv(args.csv_file)