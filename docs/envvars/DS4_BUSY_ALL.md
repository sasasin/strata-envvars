# `DS4_BUSY_ALL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 engine の Metal backend で、各 `forward()` 全体を `ds4_busy_begin()` / `ds4_busy_end()` で囲みます。通常の `ds4_busy_begin/end` 呼び出しは CPU lane が動いている区間だけですが、この変数を設定すると、forward 中の GPU 処理やホスト側の区間を含む step 全体を囲う呼び出しになります。CUDA/HIP backend にはこの環境変数の読み取りはありません。

## 値と判定

| 値 | `DS4_BUSY_ALL` の判定 |
|---|---|
| 未設定 | OFF。begin/end を呼ばない |
| 空文字 | ON。`getenv()` が null でないため |
| その他の設定値 | ON。値の内容は比較・数値変換しない |

文字列 `0`、`false` も設定されていれば ON です。`forward()` の呼び出しごとに `getenv()` で判定し、結果を cache しません。

## 有効になる条件

- `src/dsv41/ds4_model.cu` が `STRATA_METAL` 定義下でコンパイルされること。読み取りと RAII ガード自体がこの compile-time 条件内にあります。
- DeepSeek-V4.1 engine (`strata-dsv41`) の Metal 実行経路で `forward()` が呼ばれること。対象の `step()` と prompt の forward loop から同関数が呼ばれます。
- `DS4_BUSY_ALL` が設定されていること。
- さらに `ds4_busy_begin()` 内の別変数 `DS4_BUSY` が、最初の begin 呼び出し時点で文字列全体として正確に `0` ではないこと。`DS4_BUSY=0` の場合、外側の `DS4_BUSY_ALL` 判定は ON のままでも busy kernel の開始を抑止します。この `DS4_BUSY` 判定は `static const` なので初回 begin 後の環境変更は反映されません。

## 実行時の詳細

RAII オブジェクトは `forward()` の先頭で作られ、スコープを抜けると `ds4_busy_end()` を呼びます。そのため、window 長、context 上限、token 範囲のチェックで早期 return する場合も end が呼ばれます。Metal runtime は専用の command queue に busy kernel を dispatch し、共有 flag が解除されるまで実行する形です。end はその flag を立て、実行中状態を解除します。CPU lane の個別 begin/end と重なった場合も runtime の `running` 状態で多重開始を抑止します。

`DS4_BUSY_ALL` が未設定でも、CPU lane に GPU 上の expert がある経路では `ds4_busy_begin/end()` が別途呼ばれます。従って未設定は通常の CPU lane 用処理まで無効にする指定ではありません。

begin 側は初回に Metal device、kernel、queue、buffer を準備します。準備が成功しない場合や既に running の場合は黙って return し、Strata のログやエラーにはなりません。forward が他の検査や GPU 処理で失敗した場合は、通常の `false` と `err` を呼び出し元へ返します。`DS4_BUSY_ALL` 固有のログ、警告、終了経路はありません。

runtime の開始制御には他にも `DS4_BUSY_CAP`（各 begin で `atoi`、未設定時 20000）と `DS4_BUSY_W`（初回に `atoi`、未設定時 1、設定時は最低 1 に clamp）が使われます。これらは `DS4_BUSY_ALL` の値判定とは別です。Strata ソース以外の Metal driver の挙動はここでは扱いません。

## 根拠

- `src/dsv41/ds4_model.cu:41-46,9693-9700` — Metal 条件、環境変数の有無判定、forward スコープの RAII begin/end。
- `src/dsv41/ds4_model.cu:9701-9712,9737-9739` — ガード後の早期失敗と forward 計算経路。
- `src/dsv41/ds4_model.cu:7959-7961,8071,9164` — step、prompt 経路から forward への呼び出し。
- `src/dsv41/ds4_model.cu:10555-10566` — CPU lane の区間だけで行う別個の busy begin/end。
- `metal/src/mtl_rt.mm:220-222,235-289` — begin/end の実装、`DS4_BUSY` 抑止、無効時の return、kernel の dispatch と停止 flag、cap/width の処理。
- `CMakeLists.txt:906-920` — DeepSeek engine が独立 target `strata-dsv41` として構成されること。`docs/DEEPSEEK_MAC.md:3-5,91-98` は Metal engine が Apple Silicon 向けの別 engine であることを説明しています。
