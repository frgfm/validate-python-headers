# Header-check benchmarks

The README reports native CLI wall-clock time on a reproducible synthetic fixture.
This measures header checks and diagnostics, including process startup and JSON output.

## Results

Measured on 2026-10-02 from source revision
[`74325965b1920514787d2a92b43789235a75ec12`](https://github.com/frgfm/lint-my-headers/commit/74325965b1920514787d2a92b43789235a75ec12),
using `cargo build --release --locked --bin lmh` and the pinned Rust 1.93 toolchain.

| Case | Median (ms) | Minimum (ms) | Maximum (ms) |
| --- | ---: | ---: | ---: |
| clean | 273.516 | 252.656 | 286.557 |
| stale | 542.864 | 493.884 | 565.319 |

- Environment: `Linux-6.18.44-x86_64-with-glibc2.41`; AMD EPYC 9V74 80-Core Processor. The runner is shared.
- Fixture: 1,000 UTF-8 files, 1,845,381 source bytes, all nine languages
  distributed as evenly as possible. Each file has a complete Apache-2.0 notice and
  48 small function declarations; Go files also declare their package.
- Policy: a declared example owner, an earliest year two years before the run, and
  a local Apache-2.0 `LICENSE`. All enabled source files are checked.
- Clean case: all end years are current; exit 0, no diagnostics.
- Stale case: every end year is one year behind; exit 1, exactly 1,000
  fixable `LMH004` findings. Source files are not repaired.
- Sampling: one discarded warm-up and seven measured runs per case. Each sample
  launches a new process. Filesystem pages are warm; there is no persistent LMH cache.
- Timing includes CLI startup, discovery, source reads, analysis, and JSON output
  captured through a pipe. Python fixture generation, Rust compilation, and validation
  of the captured JSON are outside the timed interval.
- Release binary SHA-256: `6098d5519b829b4e687461e15ee476585814dacdb64c224a0d01a717ab3ba894`.

This is a short-file fixture on one environment. Larger files, filesystem behavior,
language mix, and machine load affect timings.

## Reproduce

From a checkout with the pinned Rust toolchain, a C compiler, and Python 3.11+:

```shell
cargo build --release --locked --bin lmh
python scripts/benchmark_headers.py --files 1000 --runs 7
```

The driver creates its files in a temporary directory, verifies checked counts,
exit codes, and diagnostic eligibility, and removes the fixture afterward. It prints
individual samples and medians as JSON. Use `--binary` for a different native binary
or `--files` and `--runs` to vary the fixture and sample count.

<details>
<summary>Recorded samples</summary>

```json
{
  "clean": {
    "median_ms": 273.516,
    "samples_ms": [
      264.695,
      281.643,
      252.656,
      273.516,
      276.006,
      269.236,
      286.557
    ]
  },
  "stale": {
    "median_ms": 542.864,
    "samples_ms": [
      541.345,
      545.386,
      542.864,
      514.155,
      565.319,
      493.884,
      553.408
    ]
  }
}
```

</details>
