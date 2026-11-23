# `STRATA_GR_FUSED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

HIP の RDNA hyper-connection 読み取り経路で、down/up の2 kernel launchを、grid barrier を含む1個の fused kernel launch に切り替える要求フラグ。これだけでは RDNA 経路自体を有効にせず、通常の RDNA 読み取りとの計算差や速度・出力の同一性も、このコードだけからは断定できない。`rdna_gr_enabled()` が true のときに `rdna_gr_read_multi()` へ進み、対象引数がそろった場合にこのフラグが評価される（`engine/src/kernels/cuda/fused_gr.cu:4284-4300`、`engine/src/kernels/cuda/rdna_gr.cu:499-507,509-543,548-565`）。

## 値と判定

`launch_gr()` 内の関数ローカル `static const bool` 初期化で `std::getenv` を一度呼び、環境変数が存在し、かつ先頭文字が ASCII の `1` なら要求を true とする。文字列全体の解析や真偽値変換はしない（`engine/src/kernels/cuda/rdna_gr.cu:512-516`）。

| ビルド / 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP AMD、`STRATA_HIP_GFX906` 未定義、RDNA 読み取り内の `s_down` / `s_up` が両方非 null | 要求 false。2 kernel 経路 | `1`、`10`、`1anything` など、先頭文字が `1` の任意の文字列 | 空文字、`0`、`0anything`、`true`、`TRUE`、` 1`、`+1` など、先頭文字が `1` でない値 |
| 上記以外のビルド、または `s_down` / `s_up` のどちらかが null | 要求はこの経路で評価されない | 該当なし | 該当なし |

大文字小文字・後続文字・数値としての妥当性は判定しない。空文字は環境変数として「設定済み」だが要求値としては false（先頭文字が `\0`）である。一方、barrier 領域の確保は別の `getenv(...) != nullptr` 判定なので、空文字でも確保を試みる（`engine/src/kernels/cuda/rdna_gr.cu:514-516,575-578`）。

## 有効になる条件

- 実装本体は `__HIP_PLATFORM_AMD__` かつ `STRATA_HIP_GFX906` 未定義のときだけコンパイルされる。それ以外のビルドでは `rdna_gr_enabled()` は false を返し、読み取り関数は空実装（`engine/src/kernels/cuda/rdna_gr.cu:25-26,593-597`）。CMake は GPU engine の共有ソースとして `rdna_gr.cu` を含める（`engine/cmake/strata_gpu_engine.cmake:6-9,99`）。
- RDNA 経路自体には、別途 `STRATA_GR_RDNA` が先頭文字 `1` であるか、同変数が未設定で `STRATA_HIP_FAST_DEC` が先頭文字 `1` であることが必要。`STRATA_GR_RDNA` が設定済みで先頭が `1` 以外なら、`STRATA_HIP_FAST_DEC=1` でも無効になる。両方が未設定、または選ばれた値の先頭が `1` でなければ `rdna_gr_enabled()` は false（`engine/src/kernels/cuda/rdna_gr.cu:548-555`）。`STRATA_GR_FUSED` はこれらの代替ではない。
- RDNA 経路を選んだ後も、`q8_down` と `q8_up` が両方 non-null なら先に `launch_q8()` を実行して戻るため、この変数の分岐に到達しない（`engine/src/kernels/cuda/fused_gr.cu:4284-4291`）。
- `s_down` と `s_up` が両方 non-null でなければ `launch_gr()` は fused 要求を調べず、別の down/up kernel 経路を使う（`engine/src/kernels/cuda/rdna_gr.cu:512-516,540-543`）。
- fused launch には、先頭文字判定に加え、barrier 領域 `m.bar` が確保済みであること、プロファイル用 `sb` が null であること、device index が `0..63` であること、device ごとの persistent grid 安全性判定が成功していることが必要。条件が満たされなければ同関数内の2 kernel 経路へ進む（`engine/src/kernels/cuda/rdna_gr.cu:517-539`）。

## 実行時の詳細

`fused_gr_read_multi_slice()` の RDNA 分岐から `rdna_gr_read_multi()` が呼ばれ、現在 device 用の barrier が未確保かつ変数が設定済みなら64 byteを `cudaMalloc` し、成功時にゼロ初期化を試みる。確保領域は `g_gr_bar[dev]` に保持され、以後の呼び出しで再利用される（`engine/src/kernels/cuda/fused_gr.cu:4293-4295`、`engine/src/kernels/cuda/rdna_gr.cu:35-36,567-579`）。

実際の fused 可否判定は `launch_gr()` の初回該当呼び出しで `static const bool fused_req` に保存され、以後のプロセス実行中は環境変数の変更を再読込しない。RDNA 経路を許可する `STRATA_GR_RDNA` / `STRATA_HIP_FAST_DEC` も `rdna_gr_enabled()` の初回呼び出しで static 値に保存される。barrier 確保の有無判定は呼び出しごとに行うが、すでに確保された領域は保持される（`engine/src/kernels/cuda/rdna_gr.cu:512-516,548-553,575-578`）。device ごとの persistent-grid 判定も `g_gr_can_fuse[dev]` に保存する。

このフラグを上書きする CLI 引数は該当ソースで確認できない。RDNA 経路の選択には上記2変数が関わるが、fused 要求を有効にするのは `STRATA_GR_FUSED` の先頭文字判定と後続の device / stamp / grid 条件である（`engine/src/kernels/cuda/rdna_gr.cu:512-539,548-565`）。

fused 条件を満たすと `rdna_gr_fused` が down 計算、grid barrier、up 計算を一つの kernel で行い、呼び出し元へ戻る。満たさない場合は `rdna_gr_down_a8` と `rdna_gr_up` を別々に launch する。プロファイル用 `sb` がある呼び出しでは fused せず、通常の2 kernel 経路で stamp を記録する（`engine/src/kernels/cuda/rdna_gr.cu:499-507,509-543`）。

## ログと測定値

この環境変数の値判定、barrier 確保、または安全性判定の失敗を直接知らせる専用ログはない。RDNA kernel launch 後にエラーが返った場合は `fused_gr_read_multi rdna: %s\n` を stderr に出し `exit(1)` する（`engine/src/kernels/cuda/fused_gr.cu:4293-4299`）。barrier の `cudaMalloc` が失敗しても、その場ではログを出さず、null のままなら通常の2 kernel 経路を使う（`engine/src/kernels/cuda/rdna_gr.cu:575-578,518-539`）。

Strata の `docs/SETTINGS.md` は同変数を「on / off」「NVIDIA and AMD」と一覧化しているが、ここで確認した実装は HIP AMD の RDNA 経路に限られ、その他ビルドは stub である。したがって同一覧の NVIDIA 表記を現行ソースの適用範囲とは扱わない（`docs/SETTINGS.md:91`、`engine/src/kernels/cuda/rdna_gr.cu:25-26,593-597`）。`docs/DETAILS.md` にこの変数固有の実測値は見つからず、本調査でも測定していない。

## 根拠

- 変数の判定、launch 条件、fallback: `engine/src/kernels/cuda/rdna_gr.cu:509-543`
- barrier の確保と保持: `engine/src/kernels/cuda/rdna_gr.cu:35-36,567-579`
- RDNA 経路の有効化と非 HIP stub: `engine/src/kernels/cuda/rdna_gr.cu:25-26,548-565,593-597`
- 呼び出し順と Q8 経路の先行: `engine/src/kernels/cuda/fused_gr.cu:4284-4300`
- ビルド対象と資料記載: `engine/cmake/strata_gpu_engine.cmake:6-9,99`、`docs/SETTINGS.md:91`
