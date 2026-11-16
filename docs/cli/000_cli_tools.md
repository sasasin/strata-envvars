# CLI ツール一覧

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。


## tool-id

| tool-id | 入口 | parser の所在 | scope |
| --- | --- | --- | --- |
| `strata-terminal` | `strata`（`bin/strata` / `strata.cmd` / `strata.ps1` → `strata.py`） | `strata_cli/cli.py` の root parser と、そこから登録される `strata_cli/launch/cmd.py`・`update_cmd.py`・`tune_commands.py`・`drafting_cmd.py`・`monitor_commands.py`・`split_cmd.py` の parser | `root/` とコマンド階層 |
| `strata-engine` | 推論エンジン `strata` / `strata.exe` | `src/program/generate.cpp`。Qwen3.6 family へ振り分けた後は `src/qwen35` 側の parser | `root/`、`qwen36/` |
| `strata-split` | `strata-split-<N>`（N = 2/3/4） | `src/split/tools/sfnx.cpp` | `root/` |
| `strata-vision` | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` | `tools/vision/strata_vision.cpp`（program 名が違っても parser は同じ） | `root/` |
| `source-setup` | `setup.sh` / `START-HERE.bat` / `SETUP.bat` / `update.sh` / `UPDATE.bat` → `setup.py` | `setup.py`。Apple Silicon で委譲される `metal/setup_mac.py` | `root/`、`mac/` |
| `quick-benchmark` | `bench.sh` / `BENCH.bat` | `tools/strata_bench.py` | `root/` |
| `strata-plan` | CMake 単体 CLI（診断・開発用） | `src/plan/plan_main.cpp` | `root/` |
| `strata-gguf` | CMake 単体 CLI（診断・開発用） | `src/artifact/gguf_reader.cpp` | `root/` |
| `strata-dequant` | CMake 単体 CLI（診断・開発用） | `src/artifact/dequant.cpp` | `root/` |

## 対象外

- Release installer `install.sh` / `install.ps1`: CLI 引数を解釈しない（設定は環境変数）。
- CMake の `*_test` / `*_parity` / `*_bench`、probe・harness、`src/split/` の `split_fnx_run` / `split_convert_dump` / `split_*_test`: 開発・検証用。
- `packaging/*.py`、`docker/*.sh` など配布物を作る helper: 利用者向け CLI ではない。
