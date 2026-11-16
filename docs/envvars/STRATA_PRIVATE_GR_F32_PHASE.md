# `STRATA_PRIVATE_GR_F32_PHASE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の private fused-GR FP32 実験で、専用カーネルを使う段階を選びます。`down` は down 段階、`up` は up 段階、`both` または未設定は両段階を許可します。通常の fused-GR 経路を切り替えるスイッチではなく、専用経路の選択を `gf_enabled` と組み合わせて絞る変数です（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2693,3365-3370,3388-3391,3465-3470`）。

## 値と判定

`gf_phase(phase)` は呼び出しごとに `std::getenv` で値を取得し、未設定なら `true`、設定済みなら文字列全体が厳密に `both` または引数の `down` / `up` と一致するときだけ `true` を返します。数値変換、空白除去、大文字小文字変換はありません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693`）。

| `STRATA_PRIVATE_GR_F32_PHASE` | down 判定 | up 判定 | 例 |
|---|---:|---:|---|
| 未設定 | true | true | 両段階を許可 |
| `both` | true | true | 両段階を許可 |
| `down` | true | false | down のみ許可 |
| `up` | false | true | up のみ許可 |
| 空文字、`1`、`0`、`DOWN`、`down ` など | false | false | 専用段階を許可しない |

## 有効になる条件

- SYCL エンジンの fused-GR 実装でのみ読み取られます。SYCL のビルド定義は `fused_gr.dp.cpp` を `strata_kernels` に含め、CUDA 側の通常実装はこの変数を参照しません（`sycl/CMakeLists.txt:240-253`。ソース全体の同名検索では、この実装以外に読み取り箇所はありません）。
- `STRATA_PRIVATE_GR_F32_REG` が有効である必要があります。この別変数は初回 `gf_enabled` 呼び出し時に `atoi` で判定され、未設定・空文字・数値 0 は無効、`atoi` の結果が非 0 なら有効です（例: `1`, `-1`, `1tail` は有効、`0`, `0tail`, 空文字は無効。`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`）。
- `gf_enabled` はさらに、トークン数 1〜4、`gr_down_sliced()` 有効、`gr_more_groups()` と `gr_large_grf()` が無効、`gr_norm_split()` 有効、`gr_up_cols()==16`、`gr_up_ilp()` 無効、Intel GPU 世代が Battlemage であることを要求します（同 `2685-2689`）。`STRATA_GR_DOWN_SLICED` と `STRATA_GR_NORM_SPLIT` は未設定なら有効、設定時は `atoi` が 0 以外なら有効です（同 `574-576,834-836`）。`STRATA_GR_MORE_GROUPS` と `STRATA_GR_LARGE_GRF` は未設定時に Alchemist だけ既定有効で、設定時は `atoi` が 0 以外なら有効です（同 `808-832`）。`STRATA_GR_UP_COLS` は未設定時 `UPM_COLS`（16）で、4/8/32/64 以外の設定値も 16 に戻ります。`STRATA_GR_UP_ILP` は値の先頭が `1` の場合に有効です（同 `1200-1210`）。
- `STRATA_PRIVATE_GR_F32_REG` のほかに CLI 引数や設定ファイルによる優先順位は、この分岐にはありません。これらの条件が満たされない場合、この phase 値にかかわらず `gf_enabled` が false となり、標準側の処理へ進みます。
- `STRATA_PRIVATE_GR_SOA_CACHE=1` が main actor 上で有効な場合、1・2・4 トークンの読み取りは `gf_enabled` が true で、かつ phase が down のみを許可すること（down 判定 true、up 判定 false）も要求します。条件を外すと `std::logic_error("B60 GR cache requires the measured GR control combination")` が投げられます（同 `3160-3167`; フラグ判定は同 `2969`）。
- 1 トークンの `q8_mixed` 経路では `STRATA_PRIVATE_GR_Q8_UP32`、down のみの phase、`STRATA_PRIVATE_GR_SILU_FROM_LO` などが揃うと別の Q8 up32 経路が選ばれます（同 `3465-3470`; helper は同 `2386,2529-2532`）。

## 実行時の詳細

`gf_phase` 自体は値を static に保存せず、down/up の分岐で呼ばれるたびに環境を読み直します。そのため、同一プロセス内で環境が変更されれば、後続の判定には反映されます。対して、専用実装全体の有効条件 `STRATA_PRIVATE_GR_F32_REG` は `gf_enabled` 内の関数 static で初回に一度だけ判定されます（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2693`）。

有効条件を満たすと、down 判定が true のとき `gf_dispatch_down` を使い、false なら通常の sliced down kernel に進みます。reduce 段階では up 判定または `STRATA_PRIVATE_GR_SILU_FROM_LO` が有効なら `gf_reduce_silu` を使います。up 判定が true なら `gf_dispatch_up`、false でも `STRATA_PRIVATE_GR_SILU_FROM_LO` が有効なら `launch_gr_up_from_lo`、それ以外は通常の up 経路を使います（同 `3365-3370,3385-3410,3465-3493`）。つまり `down` は必ずしも up 段階を省略する値ではなく、専用 up カーネルを標準または low-rank SiLU 経路に置き換えます。

## ログと測定値

この変数を読む箇所は値に応じたログを出しません。無効な文字列もそれ自体では警告・終了を起こさず、専用 down/up 判定を false にします。ただし `STRATA_PRIVATE_GR_SOA_CACHE` との組み合わせが上記条件を満たさない場合は例外になります（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2690-2693,3160-3167`）。この変数の効果を示す Strata 資料上の測定値は確認できません。

## 根拠

- 読み取りと厳密な値比較、有効条件: `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2693`
- down/reduce/up の選択と fallback: `sycl/src/kernels/cuda/fused_gr.dp.cpp:3365-3410,3465-3493`
- SYCL ビルドへの組み込み: `sycl/CMakeLists.txt:240-253`
- キャッシュ経路の追加条件と例外: `sycl/src/kernels/cuda/fused_gr.dp.cpp:3160-3167`
