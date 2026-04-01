This repository contains experiments to compare the [multiqueue](https://github.com/marvinwilliams/multiqueue) to other state-of-the-art (relaxed) concurrent priority queues.

## Importing datasets
The DIMACS maximum clique dataset must be imported via the following command
```bash
wget http://iridia.ulb.ac.be/~fmascia/files/DIMACS_all_ascii.tar.bz2
tar -xvf DIMACS_all_ascii.tar.bz2
rm DIMACS_all_ascii.tar.bz2
```

## Building the Project

This project uses **CMake presets** for configuration. The steps below describe how to configure the build and compile a specific benchmark target.

### 1. Configure the Build

Run the following command from the project root:

```bash
cmake --preset default
```

This configures the project using the `default` preset and generates the build system in the `build/` directory.

---

### 2. Build a Specific Benchmark

To compile a particular benchmark (for example, the MultiQueue MDKP benchmark `mdkp_mq_random`), run:

```bash
cmake --build build --target knapsack_mq_stick_swap -j
```

Benchmark targets are named as:

```text
<benchmark>_<target>
```

Examples:

```text
knapsack_mq_stick_swap
mdkp_mq_random
max_clique_mq_stick_mark
```
---

To see available targets, you can run:

```bash
cmake --build build --target help
```

---

### 3. Locate the Compiled Binary

After a successful build, the executable will be placed in:

```text
build/benchmarks/
```

Run with

```bash
./build/benchmarks/knapsack_mq_stick_swap --instance data/kplib/04AlmostStronglyCorrelated/n00500/R01000/s069.kp
```

### 4. Runtime Options

Branch-and-bound benchmarks support:

```text
  -j, --threads NUMBER        Number of worker threads
  -b, --batch NUMBER          Size of a node batch
      --instance FILE         Input instance file
```

MultiQueue targets additionally support:

```text
  -c, --queue-factor NUMBER   Number of queues per thread
      --mq-seed NUMBER        Seed for the multiqueue
  -k, --stickiness NUMBER     Stickiness period
```

The `--stickiness` option is only available for stick-based multiqueue modes such as:

```text
mq_stick_random
mq_stick_swap
mq_stick_mark
```

Example:

```bash
./build/benchmarks/knapsack_mq_stick_swap --instance data/kplib/04AlmostStronglyCorrelated/n00500/R01000/s069.kp -j 8 -b 4 --queue-factor 2 --stickiness 32
```
