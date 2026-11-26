# `STRATA_DF2_WAITCOMMIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CLI の speculative decode で DFlash2 が次の draft を作る前に、直前の verify window の非同期 commit を待つための測定用スイッチです。未設定なら commit と DFlash2 draft の重なりを許し、設定されていれば draft の開始前に commit 完了を待ちます。変数の値は parse せず、設定の有無だけを使います。読み取り箇所は `engine/src/program/generate.cpp` の `draft_next` lambda です（`generate.cpp:24949-24963`）。

この分岐は DFlash2 対応コード内にあり、CUDA/HIP の共通 GPU engine が `STRATA_HAVE_DFLASH2` を定義します（`engine/src/program/generate.cpp:24950-24951`、`engine/cmake/strata_gpu_engine.cmake:6-13`）。サーバー側には別の `draft_df2` lambda があり、この変数を読まず `wait_commit` も呼びません（`engine/src/program/generate.cpp:22637-22643`）。

全参照のもう一つは `terminal/data/settings-register.json:6953-6983` のカタログ項目です。そこには読み取り元として同じ `generate.cpp:24959` が記録されていますが、実行時の読み取りは上記 C++ の `std::getenv` です。

## 値と判定

`std::getenv(...) != nullptr` の結果を関数内 `static const bool` に保存します。文字列の数値・真偽値変換や範囲検査はありません（`engine/src/program/generate.cpp:24959-24960`）。

| 条件 | 未設定 | 設定ありの値 | 無効になる値 |
|---|---|---|---|
| DFlash2 対応の CLI 生成経路で `draft_next` が DFlash2 分岐に入る | 待たない（`false`） | 空文字、`0`、`1`、`true`、`false`、`0anything` を含む、環境に存在する任意の文字列で待つ（`true`） | なし。値内容を検査しない |

境界値はありません。大文字小文字、空白、数値としての妥当性も判定しません。CLI 引数や別の環境変数による値の上書きは実装されていません。CLI 引数は DFlash2 がその経路で使われるかどうかを決めますが、この変数の真偽は環境変数の存在だけで決まります（`engine/src/program/generate.cpp:8266-8275`、`24959-24960`）。

## 有効になる条件

- `STRATA_HAVE_DFLASH2` を定義したビルドであること。共有 GPU engine は CUDA/HIP ビルドでこの macro を定義します（`engine/cmake/strata_gpu_engine.cmake:6-13`）。
- CLI の speculative decode ループで DFlash2 が実際に使われ、次の draft が必要なこと。初期化時に `--draft dflash2` が選ばれ、native pack、`--draft-model`、`--spec 2` 以上などの条件を満たして DFlash2 が開始できた場合に `use_df2` が有効になります。条件不足や初期化失敗で MTP に fallback した場合、この待機分岐には入りません（`engine/src/program/generate.cpp:8266-8326`、`24512-24532`、`24837-24845`、`24949-24963`）。
- DFlash2 の suffix lookup が長い一致により draft を次の round へ延期した場合、その時点では待たず、延期先で実際に DFlash2 draft を行うときに判定します（`engine/src/program/generate.cpp:24952-24960`、`24998-25012`）。
- サーバーの request loop は別経路で、この変数を読みません。サーバーで DFlash2 を使う設定でもこの待機制御は適用されません（`engine/src/program/generate.cpp:22637-22643`）。

## 実行時の詳細

各 speculative window は `ver.commit(a + 1, err)` で commit を開始した後、次の draft を `draft_next` から作ります（`engine/src/program/generate.cpp:25193-25199`、`25218-25225`）。変数が設定されている場合、DFlash2 の `df2.draft(...)` より先に `ver.wait_commit(err)` を呼ぶため、その commit と次の draft が重ならない順序になります。未設定ならこの追加待機を行わず、既定の重なりを許します（`engine/src/program/generate.cpp:24959-24964`）。

値は `static` ローカルに一度だけ評価・保存されます。初回の DFlash2 draft 分岐に到達した時点で読み、同じプロセスで後から環境を変えても再評価されません。DFlash2 分岐に到達しない実行では読み取りません（`engine/src/program/generate.cpp:24949-24960`）。生成ループ終了後の最後の commit は、この変数に関係なく `wait_commit` で待ちます（`engine/src/program/generate.cpp:25250-25253`）。

`wait_commit` は pending commit があれば完了イベントを同期し、同期エラー時は `verify: commit: <CUDA error>` を `err` に設定して失敗を返します。`draft_next` の失敗は呼び出し元が `strata generate: <err>` を stderr に出して `1` で終了します（`engine/src/core/verify.cpp:4597-4608`、`engine/src/program/generate.cpp:24959-24960`、`25220-25225`）。

## ログと測定値

この変数を設定したこと自体を示すログはありません。読み取り行のコメントは「async commit と重ねない測定」としていますが、同じコード位置や `docs/DETAILS.md` に本変数の条件付き測定値は確認できません。待機が失敗した場合は前節の `strata generate: <err>` が出ます（`engine/src/program/generate.cpp:24959-24960`、`25220-25225`）。

## 根拠

- `engine/src/program/generate.cpp:24949-24964` — CLI の DFlash2 draft 分岐、環境変数の存在判定、待機後の draft 呼び出し。
- `engine/src/program/generate.cpp:25193-25199,25218-25225,25250-25253` — commit の開始、draft の呼び出しと失敗時の終了、最後の commit の無条件待機。
- `engine/src/core/verify.cpp:4597-4608` — commit 完了待ちとエラー処理。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — `STRATA_HAVE_DFLASH2` の CUDA/HIP 共通 engine での定義。
- `engine/src/program/generate.cpp:22637-22643` — サーバー側の別 DFlash2 draft 経路。
