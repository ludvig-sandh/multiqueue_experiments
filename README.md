This repository contains experiments to compare the [multiqueue](https://github.com/marvinwilliams/multiqueue) to other state-of-the-art (relaxed) concurrent priority queues.

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
cmake --build build --target mdkp_mq_random -j
```
---

### 3. Locate the Compiled Binary

After a successful build, the executable will be placed in:

```text
build/benchmarks/
```

---

To see available targets, you can run:

```bash
cmake --build build --target help
```
