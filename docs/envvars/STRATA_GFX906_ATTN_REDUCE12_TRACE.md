# `STRATA_GFX906_ATTN_REDUCE12_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

HIP gfx906 向けの QSA batched attention で、`STRATA_GFX906_ATTN_REDUCE12` が選んだ reduce12 カーネルの選択を `stderr` に一度記録する診断フラグです。この変数自体はカーネル選択や計算を変えず、ログを有効にするだけです。reduce12 の有効化条件を満たさない場合、この変数は読み取られません（`engine/src/kernels/cuda/qsa_decode_attn.cu:1065-1087`）。

## 値と判定

値は `std::getenv` で取得し、文字列全体がちょうど ASCII の `1`（`v[0] == '1' && v[1] == '\0'`）の場合だけ有効です。数値変換や空白除去、大文字小文字変換はありません（`engine/src/kernels/cuda/qsa_decode_attn.cu:1079-1082`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `STRATA_HIP_GFX906` ビルドで reduce12 分岐に到達 | ログなし | `1` のみ | 空文字、`0`、`true`、`01`、`1anything`、` 1` など |
| 上記以外、または reduce12 分岐に未到達 | 対象変数を読まない | 該当なし | 設定してもこの診断ログには影響しない |

`trace` は関数内 `static const` なので、最初に reduce12 分岐へ到達したときの値をプロセス内でキャッシュします。その後の環境変更は反映されません。ログ済みフラグ `said` は `static thread_local` で、reduce12 分岐へ到達したホストスレッドごとに一度だけ出力します（同 `:1079-1087`）。

## 有効になる条件

対象変数を読み、ログを出すには、すべて次の条件が必要です。

- `STRATA_HIP_GFX906` を有効にした HIP gfx906 compat build であること。同ビルドは gfx906 用に CUDA targets を HIP 経由で構成するオプションです（`engine/CMakeLists.txt:91-103`）。
- `launch_chunks_batch` が通常の環境選択経路（`kernel < 0`）で呼ばれること。reduce12 の呼び出し元は `qsa_decode_attn_batch` で、parity 用 `qsa_decode_attn_chunks_only` は `kernel` に `0` または `1` を渡すため、この環境選択分岐には入りません（`engine/src/kernels/cuda/qsa_decode_attn.cu:1023-1027,1065-1078,1132-1142,1360-1368`）。
- `STRATA_GFX906_ATTN_QUERY_SWIZZLE` が設定され、その先頭文字が `1` であり、`STRATA_ATTN_LANECELL` による lane-cell 経路が選ばれていないこと（同 `:1041-1048`）。query-swizzle 値は関数内 `static` にキャッシュされます（同 `:1043-1046`）。
- 呼び出しスレッドの現在の GPU が `gfx906` かつ wave size 64 であること。デバイス照会に失敗した場合は不適合として扱われます（同 `:868-893,1047-1048`）。
- K/V pool が INT8（`kv_mode == 1`）であること（同 `:1026-1029,1047-1048`）。
- `STRATA_GFX906_ATTN_REDUCE12` が文字列全体で `1` であること（同 `:1072-1076`）。

条件を満たさず `use_query_swizzle` が false の場合、標準の別カーネル経路へ進み、reduce12 と trace の判定は行われません。batch rows API は gfx906 build では各 row を `qsa_decode_attn_batch` に委譲します（同 `:1259-1270`）。単発の `qsa_decode_attn_step` は別経路で、この環境変数を参照しません（同 `:1309-1349`）。

## 実行時の詳細

`qsa_decode_attn_batch` は chunk pass と merge pass を実行します。chunk pass の gfx906 経路で query-swizzle が使われ、さらに `STRATA_GFX906_ATTN_REDUCE12=1` の場合、reduce12 テンプレート引数を有効にした `attn_chunk_kernel<1, false, true, true>` を launch し、その直後に trace 値を評価します（`engine/src/kernels/cuda/qsa_decode_attn.cu:1065-1087,1132-1142`）。reduce12 カーネルは score の部分和に `reduce12_gfx906` を使います（同 `:255-272,331-340`）。

trace が有効なら、当該スレッドで最初の該当 dispatch 時に次の行を `stderr` に出します。`nq` はその呼び出しの query 数、`cap` は attention の容量です（同 `:1083-1087`）。

```text
strata attn-reduce12: selected=1 query_swizzle=1 kv_mode=1 nq=<値> cap=<値>
```

既定値（未設定）や無効値では、この trace 行を出しません。カーネル launch 後にログするため、後続の `cudaGetLastError` が失敗すれば、通常の attention エラー行も続けて `stderr` に出し、`exit(1)` します（同 `:1140-1146`）。この変数はその失敗判定を変えません。

## 根拠

- 候補名の実読み取りと値判定、キャッシュ、出力: `engine/src/kernels/cuda/qsa_decode_attn.cu:1072-1087`
- query-swizzle、pool mode、device 条件と通常 fallback: `engine/src/kernels/cuda/qsa_decode_attn.cu:868-893,1026-1078,1089-1116`
- reduce12 kernel の score 計算: `engine/src/kernels/cuda/qsa_decode_attn.cu:133-160,255-272,331-340`
- `qsa_decode_attn_batch` と parity helper の呼び分け: `engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1146,1360-1372`
- gfx906 build option: `engine/CMakeLists.txt:91-103`
