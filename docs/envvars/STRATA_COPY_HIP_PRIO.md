# `STRATA_COPY_HIP_PRIO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP 用 `Verifier` の初期化で、欠落 expert の DMA に使う copy stream を高優先度で作成する opt-in です。優先度付き stream を作成できた場合は `copy_` に保存され、欠落 expert のデータ転送と、その完了を知らせる順序付き host function がこの stream に投入されます（`engine/src/core/verify.cpp:1335-1348,4391-4412`）。Strata のコメントは、window graph と同じ優先度の queue に copy や host function が並んで flag 待ちが起きる場合への対処として説明しています（同 `1337-1339`）。

## 値と判定

`std::getenv` の戻り値を `std::atoi(v) != 0` で判定します。値全体の形式検証や範囲検査はありません。未設定は無効、空文字や数値に変換できない文字列も `atoi` が 0 を返すため無効です。数値として読める先頭部分が 0 以外なら有効で、後続文字は判定に使われません（`engine/src/core/verify.cpp:1341`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_USE_HIP` 定義、`STRATA_HIP_GFX906` 未定義 | 無効 | `1`, `-1`, `1suffix`, ` 1` | 空文字, `0`, `0anything`, `true`, `false`, ` 0` |
| それ以外の build | この箇所では読まれない | 該当なし | 該当なし |

大文字小文字は数値変換の対象にならず、`true` / `false` は有効値ではありません。`atoi` の数値変換に失敗する値は無効扱いです。別の CLI 引数や環境変数による値の上書き、clamp はありません。

## 有効になる条件

- `engine/src/core/verify.cpp` が `STRATA_USE_HIP` 定義かつ `STRATA_HIP_GFX906` 未定義でコンパイルされていること。同ファイル先頭の guard は Windows HIP または CUDA 系実装を選び、GFX906 互換 build はこの読み取り分岐から除きます（`engine/src/core/verify.cpp:1-5,1335-1347`）。
- `Verifier::init` が実行されること。serve/generate は verifier を初期化し、`--pipeline-windows` や layer split の経路でも追加 verifier を初期化します（`engine/src/program/generate.cpp:13393-13420,13431-13465,13481-13501`）。この設定の判定そのものは `--spec` の値を参照しません。
- `atoi` の結果が 0 以外で、HIP の stream priority range 取得と優先度付き stream 作成の両方が成功すること（`engine/src/core/verify.cpp:1341-1345`）。条件を満たさない場合、通常優先度の non-blocking stream を作成します（同 `1348`）。

## 実行時の詳細

値は `Verifier::init` 内の関数ローカル `static const bool` により、最初にこの HIP 分岐を通る初期化時に一度だけ読み取られます。その値は同プロセス内の後続初期化でも共有されるため、最初の評価後に環境を変更しても反映されません（`engine/src/core/verify.cpp:956,1335-1345`）。

有効値の場合、Strata は `hipDeviceGetStreamPriorityRange` で範囲を得て、その `hi` を渡して non-blocking `copy_` を作成します。優先度 range 取得または優先度付き作成が失敗すると `copy_made` は false のままなので、`make_stream(&copy_)` による通常 stream 作成へ進みます。通常 stream も失敗した場合は `err` に `verify: copy stream create failed` を設定して `false` を返します（`engine/src/core/verify.cpp:1341-1350`）。成功時、欠落 expert の upload (`cudaMemcpyAsync` または `copy_expert_blobs`) と、それらの後に flag を上げる処理が `copy_` 上で行われます（同 `4391-4412`）。

## ログと測定値

この変数の値や優先度付き stream の選択を知らせる専用ログはありません。優先度付き stream と通常 stream の両方の作成に失敗すると `Verifier::init` は `verify: copy stream create failed` を返します。メインの serve 初期化側では `strata serve: <err>` を stderr に出し、終了コード 1 を返します（`engine/src/core/verify.cpp:1348-1350`; `engine/src/program/generate.cpp:13496-13501`）。高優先度設定の性能測定値は、この設定を条件付きで評価できる資料内に確認できません。

## 根拠

- `engine/src/core/verify.cpp:1-5` — verifier 実装の compile guard。
- `engine/src/core/verify.cpp:956-957,1335-1355` — `Verifier::init` と値の読み取り、stream 作成・fallback・失敗。
- `engine/src/core/verify.cpp:4391-4412` — `copy_` を使った欠落 expert の転送と順序制御。
- `engine/src/program/generate.cpp:13393-13420,13431-13465,13481-13501` — serve/generate の verifier 初期化と失敗報告。
