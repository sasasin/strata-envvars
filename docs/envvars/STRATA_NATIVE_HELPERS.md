# `STRATA_NATIVE_HELPERS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Terminal の Python コードから呼ぶネイティブ helper を、helper 名ごとに明示的に有効化する。確認できた呼び出し先は GGUF メタデータ事前検査の `gguf-preflight` だけである。環境変数が unset または該当 helper 名を含まない場合、helper は呼ばれず既存の Python 検査が使われる。候補名の実参照と値の判定は `terminal/strata_control/native_helpers.py:31,54-59`、唯一確認できた利用側は `terminal/strata_control/gguf_preflight.py:165-178`。

この変数は Strata engine の CUDA/HIP/SYCL 設定ではなく、Terminal の Python プロセスが helper 起動を選ぶ設定である。helper の所在は別変数 `STRATA_NATIVE_HELPER_DIR` で指定する。PATH や checkout の `target/release` / `target/debug` からは探索しない（`terminal/strata_control/native_helpers.py:6-9,62-75`）。

## 値と判定

`enabled(name)` は `os.environ.get("STRATA_NATIVE_HELPERS", "")` の値を文字列化し、前後の空白を除去して小文字化する。その文字列全体が `""`、`"0"`、`"off"`、`"none"`、`"no"`、`"false"` のいずれかなら無効。そうでなければカンマで分割し、各項目の前後空白を除去し、空項目を捨てた集合に `name` または `all` があると有効になる（`terminal/strata_control/native_helpers.py:54-59`）。

| 条件 | unset | 有効になる値（`gguf-preflight` の場合） | 無効になる値 |
|---|---|---|---|
| Terminal Python からの GGUF preflight | 無効（既定 `""`） | `gguf-preflight`、`all`、`other, gguf-preflight`、大文字を含む同等表記 | 空文字、空白だけ、`0`、`off`、`none`、`no`、`false`、`true`、`1`、`0anything`、`gguf-preflightx` |

全体比較の無効値以外は数値・真偽値として検証しない。例えば `00` や `0anything` は sentinel ではないが、`gguf-preflight` / `all` と一致しないのでこの利用先では無効。項目照合前に値全体を小文字化するため大文字小文字は区別しない。カンマ区切り項目の空白は無視する。`false,gguf-preflight` は全体が sentinel と一致せず、有効名を含むため有効である。範囲・境界値の数値変換はない（`terminal/strata_control/native_helpers.py:54-59`）。

## 有効になる条件

- 値のリストに `gguf-preflight` または `all` が含まれること。現在ソースで helper 名を渡す利用側は `gguf_preflight._native_inspect` の `gguf-preflight`（`terminal/strata_control/gguf_preflight.py:165-175`）。
- `STRATA_NATIVE_HELPER_DIR` が空白除去後に空でなく、そのディレクトリに OS に応じた `strata-gguf-preflight`（Windows では `strata-gguf-preflight.exe`）という通常ファイルがあること。満たさなければ利用可能な helper は返らない（`terminal/strata_control/native_helpers.py:62-75`）。
- 対象の処理が `gguf_preflight.inspect_metadata` を呼ぶこと。調査時点で本番コード上の呼び出しはモデル判定・projector 検査などにあり、例として `terminal/strata_control/models.py:522-530,673-685,967-979` および setup の `own_gguf_is_whole`（`terminal/setup.py:3739-3746`）。engine の推論実行そのものをこの変数が切り替えるコードは確認できなかった。

直接制御する CLI 引数、設定ファイル値、他環境変数との優先順位は実装されていない。値は呼び出し時点のプロセス環境から読み、`STRATA_NATIVE_HELPER_DIR` は helper の配置先を決める別条件である（`terminal/strata_control/native_helpers.py:54-75`）。

## 実行時の詳細

`inspect_metadata` は `_native_inspect` を先に呼ぶ。そこで `enabled("gguf-preflight")` が毎回環境を評価し、有効なら入力を通常ファイルへ解決した後、`native_helpers.call` が helper を探して起動する。有効判定の値をモジュール読み込み時や関数内 `static` に保存する cache はないため、同一プロセス内で `os.environ` が変更されれば次の呼び出しから再評価される（`terminal/strata_control/gguf_preflight.py:165-185`, `terminal/strata_control/native_helpers.py:54-75,99-109`）。

呼び出しは `strata-gguf-preflight --strata-protocol 1 inspect <path>`。標準入力は `/dev/null` 相当、既定 timeout は 10 秒で、超過時は子プロセスを timeout として終了させる。stdout は 1 MiB を超えると無効扱い。UTF-8 の JSON オブジェクトを厳格に parse し、protocol 1、戻り値の終了コード・キー・型・整合性を検査する（`terminal/strata_control/native_helpers.py:30-35,91-129`; 結果 schema は `terminal/strata_control/gguf_preflight.py:143-162`）。

helper が起動できない、timeout、異常終了、出力超過、JSON/protocol/schema 不一致などは `Unavailable` となり、呼び出し側が Python reader へ進む。契約どおりの `ok: false` は `Rejected` となり、`ProfileError` に変換されて拒否として扱われる（`terminal/strata_control/native_helpers.py:103-129`, `terminal/strata_control/gguf_preflight.py:173-178,181-198`）。正常な `ok: true` の結果は Python reader の代わりに返され、下流のモデル検査がそのメタデータを使う。ソースは両経路の同一性を契約として要求しているが、この調査では値や結果の実測・テストを行っていない。

## ログと測定値

この環境変数の未設定・無効・有効を知らせる専用ログ出力は確認できなかった。helper の失敗は `Unavailable` として Python 経路へ fallback するため、それ自体は利用側に伝播しない。helper の契約内拒否は `ProfileError` となり、呼び出し元によってモデル検査結果や setup 判定に反映される。速度・正確性の測定値は記載しない（`terminal/strata_control/native_helpers.py:103-129`, `terminal/strata_control/gguf_preflight.py:173-198`）。

## 根拠

- `terminal/strata_control/native_helpers.py:1-18,31-35,54-75,91-129` — helper の opt-in 方針、値の判定、配置条件、protocol、timeout と失敗分類。
- `terminal/strata_control/gguf_preflight.py:143-198` — 現在の唯一の利用名、結果 schema、拒否・fallback、および Python 検査の開始。
- `terminal/strata_control/models.py:504-533,673-695,950-980` — モデル候補・projector・import 時の preflight 呼び出し。
- `terminal/setup.py:3739-3746` — setup の GGUF 完全性判定からの呼び出し。
- `terminal/crates/strata-gguf-preflight/src/main.rs:1-25` — helper が protocol 引数を解釈して結果を出力する実装。対象環境変数を helper 自身が読む箇所ではない。
