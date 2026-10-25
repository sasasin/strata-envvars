# `STRATA_REPO`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。Strata 所有ソースを対象とし、外部依存とベンチマーク結果ディレクトリ内の記録用コードは挙動の根拠から除外した。

## 役割

同梱の Python テストスクリプト3本が、Strata のルートディレクトリを指定して import path を組み立てるために使う。通常の `strata` 実行ファイルやサーバー設定を切り替える環境変数ではない。

対象スクリプトは `tools/session_pressure_test.py`、`tools/batch_groups_cache_test.py`、`tools/cancel_park_test.py`。各スクリプトは `STRATA_REPO` から `tools` とリポジトリルートを `sys.path` に追加し、`strata_tokenizer` や `serve.server` を import する。したがって、別 checkout を指定すると、その checkout から Python モジュールを読み込める。

## 値と判定

| 状態 | `REPO` の値 |
|---|---|
| 未設定 | 実行中スクリプトのファイル位置から求めたリポジトリルート。`Path(__file__).resolve().parent.parent` による絶対パス |
| 設定あり | 値をそのまま `Path(...)` に渡す。空文字も設定ありとして扱われる |

文字列比較、数値変換、値域検証、空文字の fallback はない。設定値が相対パスならプロセスの現在ディレクトリを基準に使われる。空文字の場合は `Path("")` が `.` となり、現在ディレクトリがルート候補になる。存在確認や絶対パス化は override 値には行わないため、誤ったパスは import の失敗などとして現れる。

## 有効になる条件

製品機能での読み取りは確認できず、調査対象に含めた同梱ツールでは上記3本のテストスクリプトが読み取る。各スクリプト起動時の Python モジュール初期化時に評価され、値を後から変更しても、そのプロセス内で確定した `REPO` と `sys.path` は更新されない。除外したベンチマーク結果ディレクトリ内の別スクリプトにも参照がある（根拠節を参照）。

通常の `serve/server.py` 自身は `STRATA_REPO` を読み取らず、自身の `__file__` から `ROOT` を決めて import path を設定する。テストスクリプトが `serve.server` を import するときに `STRATA_REPO` が効くのは、どの checkout のモジュールを import 解決に使うかを決める段階である。

## 実行時の詳細

3本とも、最初に `sys.path.insert(0, str(REPO / "tools"))`、続けて `sys.path.insert(0, str(REPO))` を実行する。そのため最終的にはリポジトリルートが先頭、同じルートの `tools` がその次に来る。続く import は各スクリプトで異なるが、`strata_tokenizer` と `serve` パッケージをこの import path から解決する。

この設定はテストスクリプトの Python import に作用する。スクリプトが `StrataEngine` を起動する際の実行ファイル、作業ディレクトリ、子プロセス環境は別の設定 (`STRATA_EXE`、設定 JSON、`child_env(cfg)` など) から構成される。`child_env` は現在の環境をコピーして GPU や config の値を反映するが、`STRATA_REPO` を特別扱いしない。

## 根拠

- `tools/session_pressure_test.py:11-18,29-30`: `STRATA_REPO` を読み、import path に追加して `strata_tokenizer` と `serve.server` を import。
- `tools/batch_groups_cache_test.py:13-19,33`: 同じ既定値・path 設定を行い、`serve.server` から `StrataEngine` を import。
- `tools/cancel_park_test.py:14-20,30-31`: 同じ既定値・path 設定を行い、`serve.server` から `StrataEngine` を import。
- `serve/server.py:57-66,2858-2875`: サーバーモジュール自身は `__file__` から `ROOT` を求める。`child_env` は環境コピーと config 値を使い、この変数専用の処理はない。
- `bench/results/2026-10-06-community-rtx4090-opt-ins/conc_bench.py:33-35` にも同名の参照があるが、これはベンチマーク結果ディレクトリ内の記録・再現用スクリプトであり、調査手順の除外対象として上記3本の製品同梱ツールの説明には含めていない。

`docs/DETAILS.md` とその他の Strata 文書から、この変数の追加動作や利用者向け仕様は確認できなかった。
