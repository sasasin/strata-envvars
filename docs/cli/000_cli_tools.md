# CLI ツール一覧

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（`2026-11-07` 時点）。

`docs/cli/<tool-id>/` を切る単位の一覧。各 tool-id のコマンドとオプションは [`README.md`](README.md)、調査と配置の規約は [`001_investigation.md`](001_investigation.md) にある。

## tool-id

| tool-id | 入口 | parser の所在 | scope |
| --- | --- | --- | --- |
| `strata-terminal` | `strata`（`bin/strata` / `strata.cmd` / `strata.ps1` → `strata.py`） | `strata_cli/cli.py` の root parser と、そこから登録される `strata_cli/launch/cmd.py`・`update_cmd.py`・`tune_commands.py`・`drafting_cmd.py`・`monitor_commands.py`・`split_cmd.py` の parser | `root/` とコマンド階層 |
| `strata-engine` | 推論エンジン `strata` / `strata.exe` | `src/program/generate.cpp`。Qwen3.6 family へ振り分けた後は `src/qwen35` 側の parser | `root/`、`qwen36/` |
| `strata-engine-dsv41` | `strata-dsv41`（macOS は CMake target `strata_ds4`） | `src/dsv41/ds4_main.cpp` | `root/` |
| `strata-split` | `strata-split-<N>`（N = 2/3/4） | `src/split/tools/sfnx.cpp` | `root/` |
| `strata-vision` | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` | `tools/vision/strata_vision.cpp`（program 名が違っても parser は同じ） | `root/` |
| `source-setup` | `setup.sh` / `START-HERE.bat` / `SETUP.bat` / `update.sh` / `UPDATE.bat` → `setup.py` | `setup.py`。Apple Silicon で委譲される `metal/setup_mac.py` | `root/`、`mac/` |
| `quick-benchmark` | `bench.sh` / `BENCH.bat` | `tools/strata_bench.py` | `root/` |
| `strata-plan` | CMake 単体 CLI（診断・開発用） | `src/plan/plan_main.cpp` | `root/` |
| `strata-device` | CMake 単体 CLI（診断・開発用） | `src/core/device_main.cpp` | `root/` |
| `strata-load` | CMake 単体 CLI（診断・開発用） | `src/core/load_main.cpp` | `root/` |
| `strata-concurrent` | CMake 単体 CLI（診断・開発用） | `src/core/concurrent_main.cpp` | `root/` |
| `strata-overlap` | CMake 単体 CLI（診断・開発用） | `src/core/overlap_main.cpp` | `root/` |
| `strata-gguf` | CMake 単体 CLI（診断・開発用） | `src/artifact/gguf_reader.cpp` | `root/` |
| `strata-dequant` | CMake 単体 CLI（診断・開発用） | `src/artifact/dequant.cpp` | `root/` |
| `strata-q36ref` | CMake 単体 CLI（診断・開発用） | `src/qwen35/q36ref.cu` | `root/` |

## 対象外

- Release installer `install.sh` / `install.ps1`: CLI 引数を解釈しない（設定は環境変数）。
- CMake の `*_test` / `*_parity` / `*_bench`、probe・harness、`src/split/` の `split_fnx_run` / `split_convert_dump` / `split_*_test`: 開発・検証用。
- `packaging/*.py`、`docker/*.sh` など配布物を作る helper: 利用者向け CLI ではない。
