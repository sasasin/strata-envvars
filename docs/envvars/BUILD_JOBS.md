# `BUILD_JOBS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows 用 CUDA エンジンのパッケージ作成時に、エンジン本体と `strata-vision` の CMake build に渡す並列 job 数を指定する。Strata の実行ファイルが起動時に読む設定ではなく、`tools/packaging/build_cuda_windows.py` と、それが起動する `build_vision_windows.bat` のビルド用設定である。Python スクリプトは Windows 以外では処理を中断するため、この経路は Windows 上の `cuda12` / `cuda13` variant に限られる（`tools/packaging/build_cuda_windows.py:151-158`）。

## 値と判定

| 経路 | 未設定・空文字 | 設定時に使われる値 | 変換・検証 |
|---|---|---|---|
| `build_cuda_windows.py` から起動 | `os.environ.get("BUILD_JOBS") or "6"` により文字列 `6` | 空でない文字列をそのまま使用。例: `1`, `8`, `0`, `-1`, `abc` | 整数への変換、正数チェック、範囲制限はない。`-j` の引数としてそのまま CMake に渡す。空白だけの文字列も truthy なので既定値にならない（`tools/packaging/build_cuda_windows.py:165,177`）。 |
| `build_vision_windows.bat` を直接起動 | `if not defined BUILD_JOBS` により `4` を設定 | 定義済みの値をそのまま `%BUILD_JOBS%` で展開 | 数値への変換や値域チェックはない（`tools/packaging/build_vision_windows.bat:36,58`）。 |

Python 経路では unset と空文字が同じく `6` になり、通常のパッケージ作成ではその値が `BUILD_JOBS` として vision バッチの子プロセス環境にも明示的に渡る。そのため Python 経由の vision build も既定値 `6` を使い、バッチ単体起動時の既定値 `4` とは異なる（`tools/packaging/build_cuda_windows.py:165,189-190`）。`0`、負数、非数値文字列などはスクリプト側で拒否されず CMake build に引き渡される。受理可能な job 数の範囲や、それらの値に対する CMake の挙動は Strata のコードでは定めていない。

## 有効になる条件

- Python ラッパー経由では、引数がちょうど一つで `cuda12` または `cuda13`、かつ OS が Windows である必要がある。Linux では `build_cuda_windows.py:156-158` の `fail(...)` に進む。
- `BUILD_JOBS` は configure ではなく、engine targets の build と vision reader の build に適用される。エンジン build は `cmake --build <build> -j <値> --target ...`、vision build は `cmake --build ... --target strata-vision -j <値>` で実行される（`build_cuda_windows.py:174-177,189-190`; `build_vision_windows.bat:54-58`）。
- 直接起動したバッチでは値の設定後も CUDA toolkit の `nvcc.exe` と `cl.exe` などの前提確認があり、それらが満たされなければ build に到達しない（`build_vision_windows.bat:33-46`）。
- `cuda12` / `cuda13` の選択は対象 toolkit や architecture を決めるが、`BUILD_JOBS` の値自体に variant 別の変換・上書きはない（`build_cuda_windows.py:37-42,165-177`）。CLI 引数や設定ファイルによる `BUILD_JOBS` の優先上書きもない。

## 実行時の詳細

ここでの「実行」はパッケージ作成スクリプトの実行を指す。`main()` が `BUILD_JOBS` を一度読み、同じ文字列を engine build の argv に使い、`venv` に設定して vision バッチへ渡す。プロセス内で再読込する処理や cache はなく、スクリプト稼働中に親プロセスの環境変数を変えて値を更新する仕組みもない（`build_cuda_windows.py:151-177,189-190`）。

バッチ単体実行時は、`setlocal` のスコープ内で未定義の変数に `4` を設定し、vision build の `-j` 引数に展開する（`build_vision_windows.bat:20,36,58`）。いずれの経路も job 数を Strata の生成・推論処理へ渡さない。

## ログと測定値

Python ラッパーは実行する各コマンドを `+ ` に続けて表示する。engine build が非 0 で終了した場合、`run()` は `build_cuda_windows.py:48-49` の `fail()` を通じて `build_cuda_windows.py:148` の形式 `build_cuda_windows.py: failed: <command>` で終了する。vision build の各主要コマンドも失敗時にバッチを非 0 で終了し（`build_vision_windows.bat:54-60`）、Python ラッパーはその失敗を `failed: cmd /d /c` として報告する（`build_cuda_windows.py:145-148,190`）。job 数による測定値や Strata 固有の成功・警告ログは該当ソースにない。

## 根拠

- `tools/packaging/build_cuda_windows.py:151-177` — 対応 variant / OS 条件、`BUILD_JOBS` の読み取り、engine build への引き渡し。
- `tools/packaging/build_cuda_windows.py:145-149,179-203` — コマンド出力、失敗時の終了、vision バッチへの引き渡しと後続処理。
- `tools/packaging/build_vision_windows.bat:20-37,48-61` — バッチ単体の既定値、vision build への引き渡し、失敗経路。
- `tools/packaging/ENGINE-COMPONENT.md:104-110` — Windows CUDA package と vision reader の位置づけ。job 数や測定値の説明はない。
