# `DS4_DBG_ARGS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DeepSeek V4.1 の埋め込み dispatch 後に診断用 Metal kernel を追加実行し、kernel が受け取った `dim` と `hc` を `stderr` に表示します。診断 kernel は表示用の値を埋め込み出力バッファ先頭にも書くため、設定すると通常の埋め込み結果を変更します。

## 値と判定

`std::getenv("DS4_DBG_ARGS")` の結果が null かどうかだけを判定します。値の文字列や数値への変換はありません。

| 状態 | 動作 |
|---|---|
| 未設定 | 引数 probe dispatch と `DBG args` ログを出さない |
| 設定あり（空文字を含む） | probe dispatch を行い、`DBG args: kernel sees dim=%g hc=%g` を `stderr` に出す |

したがって `0`、`false`、任意の文字列でも、環境変数が存在すれば有効です。明示的な空文字も有効です。既定値は無効（未設定）です。

## 有効になる条件

- Metal 用の `strata_ds4` ビルドで `STRATA_METAL` が定義されていること。通常の非 Metal 実装では `embed_addr()` 呼び出し自体がコンパイル条件から外れます。
- DeepSeek V4.1 の `embed()` が呼ばれ、`embed_addr()` が `shared_lib()` から有効な Metal library を得て、`ds4_embed_j` pipeline の作成に成功すること。
- `embed_addr()` が成功すると後続の Metal `embed()` と CUDA 形式の fallback は呼ばれません。library が無効、または `ds4_embed_j` pipeline 作成に失敗した場合は `false` を返し、呼び出し元は次の Metal `embed()`、さらに失敗時は通常の kernel へ進みます。この経路では `DS4_DBG_ARGS` の probe に到達しません。

OS や CLI 引数による追加の判定はありません。`DS4_DBG_ARGS` 以外の環境変数との優先関係もありません。

## 実行時の詳細

`embed()` は `STRATA_METAL` ビルドで `embed_addr()` を先に呼びます。`embed_addr()` は engine stream を同期し、共有 Metal context/library を取得して `ds4_embed_j` を実行・flush した後に、`DS4_DBG_ARGS` をその都度読みます。判定結果を static cache しないため、各埋め込み呼び出しで環境を再確認します。

変数が設定されている場合、`host_view(h)` の 16 KiB 境界に合わせた buffer を作り、`ds4_args_probe` に buffer、`dim`、`hc` を渡して 1 threadgroup を dispatch し、flush します。probe kernel は `h[0] = dim`、`h[1] = hc`、`h[2] = 1.0f` を書きます。ホスト側は `host_view(h)` から先頭 2 要素を読み、次の形式で `stderr` に記録します:

```text
DBG args: kernel sees dim=<値> hc=<値>
```

`h` は実際の埋め込み出力バッファで、この診断 dispatch 後も値を復元しません。従って変数を設定した場合、少なくともバッファの先頭 3 float は本来の埋め込み結果ではなく、上記の probe 値になります。probe の引数が表示される一方、モデル計算へ渡る出力も変更される診断用フックです。

## 根拠

- `metal/src/engine/ds4_host.cpp:195-223` — `embed_addr()` の stream 同期、共有 library/pipeline の取得、通常の埋め込み dispatch と flush。
- `metal/src/engine/ds4_host.cpp:236-250` — 設定有無の判定、probe 用引数、dispatch、出力読み取りと `stderr` ログ。
- `metal/src/engine/msl/ds4_init.metal:2600-2604` — `ds4_args_probe` が受け取った `dim` / `hc` を `out[0..2]` に書く実装。
- `src/dsv41/ds4_kernels.cu:2186-2193` — Metal ビルドで `embed_addr()` を優先し、失敗時に次の実装へ進む呼び出し順。
- `metal/src/engine/ds4_finish.cpp:2749-2752` — `shared_lib()` が `ensure()` 後に共有 library ID を返す。
- `metal/CMakeLists.txt:135-146,165-169` — `strata_ds4` の DeepSeek engine ソース構成と `STRATA_METAL=1` 定義。
