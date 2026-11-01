# `HIP_RUNTIME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリ・driver の環境変数動作は対象外。

## 役割

この commit の Strata 実行時コードには `HIP_RUNTIME` の読み取り箇所がありません。Strata の `setup.py` は HIP engine をソースからビルドするとき、子プロセス用環境に `HIP_RUNTIME=rocclr` を設定します。Linux 向け HIP packaging script も同じ値を export します。したがって、Strata が利用者の `HIP_RUNTIME` 値を設定として解釈して engine の実行動作を変える環境変数ではありません。

## 値と判定

Strata は利用者から渡された値を parse、検証しません。`setup.py` の HIP engine ビルド経路では `os.environ.update(...)` により、元の値が未設定・空文字・別の文字列のいずれでも `rocclr` で上書きします。Linux packaging script も `export ... HIP_RUNTIME=rocclr ...` と設定します。

## 有効になる条件

- `setup.py` の `build_engine_hip()` が既存 engine を再利用せず HIP engine のコンパイルへ進む場合、HIP/ROCm 用の環境変数群を設定してから CMake を実行します。既存 engine と vision reader がともに利用可能なら早期 return し、この設定処理は実行されません。
- HIP vision reader のみをビルドする `build_vision_hip()` 経路では、`vision == "gpu"` かつ `hipconfig` が見つからず、かつ `ROCM_PATH` も未設定の場合に、ROCm 環境を設定し直します。この分岐でも `HIP_RUNTIME` は `rocclr` になります。条件を満たさない場合、この関数自身は `HIP_RUNTIME` を設定しません。
- `packaging/build_hip_linux.sh` はスクリプト実行中に常に `HIP_RUNTIME=rocclr` を export してから engine と vision reader の CMake configure/build を実行します。

この値を受け取った CMake、compiler、ROCm 側の解釈や影響は Strata の挙動としては記述しません。

## 実行時の詳細

`setup.py` の `build_engine_hip()` は HIP ビルドの前に `HIP_PLATFORM=amd`、`HIP_COMPILER=clang`、`HIP_RUNTIME=rocclr` などを Python プロセスの `os.environ` に設定します。その後の `cmake_build()` は `run()` を呼び、`run()` は `env` を省略された場合に `os.environ` のコピーを `subprocess.run()` に渡します。従って、この設定は CMake の configure/build 子プロセスへ継承されます。外から起動済みの Strata engine へ `HIP_RUNTIME` を設定した場合の処理は、Strata ソース中にありません。

Strata 独自の `HIP_RUNTIME` 値に対するログ、警告、終了・失敗経路はありません。ビルド自体の失敗処理は一般的な `run()` / CMake ビルド経路にありますが、`HIP_RUNTIME` の値に応じた分岐ではありません。

## 根拠

- `setup.py:4784-4827` — `build_engine_hip()` の再利用時 return、環境変数設定、HIP engine の CMake build 呼び出し。
- `setup.py:959-978` — `run()` が `os.environ` をコピーして子プロセスへ渡す処理。
- `setup.py:5800-5824` — `cmake_build()` が configure/build を `run()` 経由で実行する処理。
- `setup.py:4876-4900` — HIP vision reader build の条件と、条件成立時の `HIP_RUNTIME=rocclr` 設定。
- `packaging/build_hip_linux.sh:52-89` — packaging script が値を export して HIP engine と vision reader を configure/build する処理。
- `setup.py:4474,4483` — `HIP_RUNTIME_DLLS` は Windows の DLL glob 用定数とその利用であり、環境変数の読み取りではありません。
