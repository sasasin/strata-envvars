# `STRATA_SYCL_BIN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Intel SYCL 用のラッパー `sycl/serve/strata-sycl.sh` が、リポジトリ内で実行する engine バイナリの相対パスを指定します。通常の設定ファイルでは `exe` はこのラッパーを指し、ラッパーが Docker コンテナ内で `$STRATA_SYCL_BIN` を実行します。Strata の engine C++ がこの変数を読む箇所はありません。

## 値と判定

| 読み取り箇所 | unset / 空文字 | 設定値 |
|---|---|---|
| `sycl/serve/strata-sycl.sh` | `build-sycl-aot/strata` を使用（Bash の `${VAR:-default}`） | 値をリポジトリ相対の実行ファイルパスとして使用 |
| `serve/server.py` の `engine_binary()` | 設定ファイル `env` に truthy な値がなければ、サーバープロセスの環境変数、次に `build-sycl-aot/strata` | 設定ファイル `env` の値をサーバー環境変数より優先。空文字は false 扱いで次の候補へ進む |
| `sycl/setup_intel.py` の `to_sycl()` | 選択した engine が `build-sycl-aot/strata` なら設定項目を作らない | 選択した engine が同パスと異なる場合、設定ファイルの `env` に相対パスを記録 |

文字列や数値としての parse、前後空白の除去、パス検証はラッパー側では行いません。パスはリポジトリからの相対パスを前提とします。サーバーの `engine_binary()` は候補ファイルが存在する場合にだけそのパスを返し、存在しなければ `exe`（ラッパー）を返します。

根拠: `sycl/serve/strata-sycl.sh:8,42`, `serve/server.py:2318-2329`, `sycl/setup_intel.py:203-204`。

## 有効になる条件

- `sycl/serve/strata-sycl.sh` を engine の `exe` として使う Intel SYCL サーバー経路で、実行する engine の選択に使われます。CUDA/HIP の通常の engine 起動経路には適用されません。
- セットアップは Linux 向けです。`sycl_engine()` は `build-sycl-aot/strata` を先に探し、なければ `build-sycl/strata` を探します。後者を選んだ場合、`to_sycl()` が `STRATA_SYCL_BIN=build-sycl/strata` を設定ファイルへ書きます。AOT 版を選ぶ場合は既定値と一致するため書きません。
- ラッパーは指定パスを `docker run` 内で実行します。Docker とイメージが使えること、指定先がコンテナから見えるリポジトリ内にあることが実行条件です。

`docs/INTEL_ARC.md` も、`setup_intel.py` が `build-sycl-aot/strata` または `build-sycl/strata` を探し、トップレベル CMake オプションでは `build-sycl/sycl/strata` になるため `-S sycl` を使うか `STRATA_SYCL_BIN` を設定する、と説明しています。これは上記のパス選択と整合します（`docs/INTEL_ARC.md:120-121`）。

## 実行時の詳細

サーバーは起動時に `child_env(cfg)` で親プロセスの環境を複製し、設定ファイルの `env` 項目を文字列化して上書きします。その環境を `StrataEngine` がラッパープロセスへ渡します。ラッパーは `STRATA_SYCL_BIN` をコンテナに渡す環境変数の一括対象から除外します（`STRATA_SYCL_*` はスクリプト自身の設定）。その後、ホスト側スクリプトが値をコマンド文字列へ展開し、コンテナ内で `cd /work/<リポジトリ名>` してそのバイナリを `exec` します。未設定または空文字なら `build-sycl-aot/strata` です。存在しない、実行できないパスを指定した場合の専用 fallback はなく、コンテナ内のコマンド実行に失敗します。

別の用途として、サーバーの `effort_position: "end"` 機能は engine バイナリ内に `--tail-role-token` があるか調べます。`exe` の basename が `strata-sycl.sh` の場合、検索先を `STRATA_SYCL_BIN` から組み立てます。優先順位は設定ファイル `env` の truthy な値、サーバープロセス環境の値、`build-sycl-aot/strata` の順です。ファイルが読めない、またはオプション文字列が見つからない場合、標準出力に engine 0.1.39 以降が必要である旨を出し、この機能用の引数を追加しません。このチェックは起動時に行われます。

設定ファイルの空文字は少し特殊です。`child_env()` は空文字でサーバー環境を上書きしますから、ラッパーは既定の AOT パスを実行します。一方、`engine_binary()` の選択では空文字は false 扱いになり、サーバー親環境に同名変数があればその値で機能検査をします。親環境の値と実際のラッパー実行先が異なる可能性があります。

根拠: `serve/server.py:2622-2639,2318-2329,2342-2350,6406-6426`, `sycl/serve/strata-sycl.sh:26-42`。

## 根拠

- `sycl/setup_intel.py:89-96` — セットアップが探す engine の順序と未ビルド時の扱い。
- `sycl/setup_intel.py:191-208` — サーバー設定と、既定 AOT パスと異なる場合の環境変数記録。
- `serve/server.py:2622-2639` — 親環境の複製後、設定ファイル `env` が上書きされる処理。
- `serve/server.py:2318-2329,2342-2350` — SYCL ラッパー使用時の機能検査バイナリ選択と結果。
- `serve/server.py:6406-6426` — 設定の `exe` 解決、engine 起動への環境引き渡し。
- `sycl/serve/strata-sycl.sh:15-17,26-42` — リポジトリ位置、SYCL 設定の環境転送除外、Docker 内での実行。
- `docs/INTEL_ARC.md:120-121` — SYCL engine の配置に関する利用者向け説明。
