# CLI ツール一覧

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## tool-id

| tool-id | 入口 | parser の所在 | scope |
| --- | --- | --- | --- |
| `strata-terminal` | `strata`（`terminal/bin/strata` / `strata.cmd` / `strata-direct.ps1` → `terminal/strata.py`） | `terminal/strata_cli/cli.py` の root parser と、そこから登録される `strata_cli/launch/cmd.py`・`update_cmd.py`・`tune_commands.py`・`drafting_cmd.py`・`monitor_commands.py`・`split_cmd.py` の parser | `root/` とコマンド階層 |
| `strata-engine` | 推論エンジン `strata` / `strata.exe` | `engine/src/program/generate.cpp`。Qwen3.6 family へ振り分けた後は `engine/src/qwen35` 側の parser | `root/`、`qwen36/` |
| `strata-hy4` | `strata-hy4` / `strata-hy4-metal` / `strata-hy4-sycl`（Tencent Hy4-Flash の `.strata` エンジン。setup.py が component として入れる） | `engine/src/hy4flash/run/hy4_main.hip.cpp`（CUDA/HIP）、`engine/src/hy4flash/metal/hy4_metal_main.cpp`（Metal）、`engine/src/hy4flash/sycl/sy_main.cpp`（SYCL） | `root/`、`metal/`、`sycl/` |
| `strata-inkling` | `strata-inkling` / `strata-inkling-metal` / `strata-inkling-sycl`（Inkling-2-Mini の `.strata` v1.1 エンジン。setup.py が component として入れる） | `engine/src/inkling2/ink_main.cpp`（CUDA/HIP）、`engine/src/inkling2/metal/ink_metal_main.cpp`（Metal）、`engine/src/inkling2/sycl/ink_sy_main.cpp`（SYCL） | `root/`、`metal/`、`sycl/` |
| `strata-split` | `strata-split-<N>`（N = 2/3/4） | `engine/src/split/tools/sfnx.cpp` | `root/` |
| `strata-vision` | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` | `terminal/tools/vision/strata_vision.cpp`（program 名が違っても parser は同じ） | `root/` |
| `source-setup` | `setup.sh` / `START-HERE.bat` / `UPDATE.bat` → `terminal/setup.py` | `terminal/setup.py`。Apple Silicon で委譲される `engine/metal/setup_mac.py` | `root/`、`mac/` |
| `quick-benchmark` | `tools/bench.sh` / `tools/BENCH.bat` | `terminal/tools/strata_bench.py` | `root/` |
| `strata-plan` | CMake 単体 CLI（診断・開発用） | `engine/src/plan/plan_main.cpp` | `root/` |
| `strata-gguf` | CMake 単体 CLI（診断・開発用） | `engine/src/artifact/gguf_reader.cpp` | `root/` |
| `strata-dequant` | CMake 単体 CLI（診断・開発用） | `engine/src/artifact/dequant.cpp` | `root/` |

## 対象外

- Release installer `install.sh` / `install.ps1`（`tools/packaging/`）: CLI 引数を解釈しない（設定は環境変数）。
- CMake の `*_test` / `*_parity` / `*_bench`、probe・harness、`engine/src/split/` の `split_fnx_run` / `split_convert_dump` / `split_qdot_golden` / `split_*_test`、`engine/cmake/strata_gpu_engine.cmake` の `strata-device` / `strata-load` / `strata-concurrent` / `strata-overlap` / `strata-q36` / `strata-q36ref`、`terminal/tools/vision/` の `strata-vision-own` / `strata-vision-own-compare` / `strata-vision-prep-oracle`、`pool_determinism` / `cpu_dispatch_dump` / `pool_stress` / `tune_hipblaslt` / `tune_rocblas`: 開発・検証用。
- `tools/packaging/*.py`、`tools/docker/*.sh` など配布物を作る helper: 利用者向け CLI ではない。
