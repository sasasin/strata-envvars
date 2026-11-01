# `STRATA_GR_R2`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを調査。作業開始時の Strata 作業ツリーは `main...origin/main` で変更なし。

## 役割

CUDA 系の fused hyper-connection multi-token read が `STRATA_GR_V3` の二段 kernel 経路を使う場合に、5〜8 token の down kernel で warp あたりに処理する行数（1 / 2 / 4）を選びます。複数行をまとめる kernel は同じ活性値を少ない block で処理します。これは kernel dispatch の選択であり、環境変数自体が GPU 計算を有効にするものではありません。

単一 token の `fused_gr_read()` や、通常の `launch_multi()` 経路にはこの設定の読み取りがありません。SYCL / Metal の実装にも参照はありません。

## 値と判定

`gr_r2()` の初回呼び出し時に `std::getenv()` で読み、設定値は `std::atoi()` で整数化します。unset の既定値は `2`。変換後に `1`, `2`, `4` のみを値として返し、それ以外は `0` にします。文字列全体の妥当性検査はなく、`atoi` が読める先頭の整数で判定されます。

| 環境値 | `atoi` 後 | `gr_r2()` の値 | down kernel の選択（V3 split が有効な場合） |
|---|---:|---:|---|
| unset | 既定値 2 | 2 | 5〜8 token で exact-T / 2 行-per-warp |
| 空文字 | 0 | 0 | 5〜6 token は exact-T / 1 行-per-warp、7〜8 token は汎用 down kernel |
| `1`, `+1`, `01`, `1tail` | 1 | 1 | 7〜8 token は exact-T / 1 行-per-warp。5〜6 は exact-T / 1 行-per-warp |
| `2`, `2tail`, ` 2` | 2 | 2 | 5〜8 token は exact-T / 2 行-per-warp |
| `4`, `4tail` | 4 | 4 | 7〜8 token は exact-T / 4 行-per-warp。5〜6 は exact-T / 1 行-per-warp |
| `0`, `3`, `-1`, `true`, 数字で始まらない文字列 | atoi 結果（例: 0） | 0 | 5〜6 token は exact-T / 1 行-per-warp、7〜8 token は汎用 down kernel |

5〜6 token の dispatch には R2=2 専用分岐だけがあり、それ以外の値（0 を含む）では exact-T R2=1 kernel が選ばれます。7〜8 token では R2=1 / 2 / 4 の各 exact-T kernel を選べ、0 なら汎用 down kernel に fallback します。R2=0 の場合、7〜8 token の up kernel も汎用版になります。1〜4 token では `STRATA_GR_R2` による down/up の選択分岐に入りません。

## 有効になる条件

この変数の効果が現れるには、次の条件がすべて必要です。

- `src/kernels/cuda/fused_gr.cu` の CUDA 系 fused kernel がビルドされている。
- 呼び出しが複数 token の `fused_gr_read_multi()` に到達し、その slice が 5〜8 token である。8 token 超の入力は最大 8 token の slice に分割されます。
- Q8 down/up 重みの経路ではない。`fused_gr_read_multi_slice()` は Q8 重みを検出すると `launch_q8()` を実行して戻るため、V3 と `STRATA_GR_R2` を通りません。
- `STRATA_GR_V3` が有効で、当該 device の shared-memory 条件から V3 split が使用可能である。
- V3 path 内で `a[0].s_down` と `a[0].s_up` が null であり、`split > 0` である。

`STRATA_GR_V3` が明示設定される場合は `atoi(value) != 0` が有効、`0` が無効です。unset 時は CUDA で device ごとの既定判定に従い、HIP では既定無効です。V3 が無効、または split が利用できない場合は通常の read 経路へ進み、この変数は効果を持ちません。`--no-fused-gr` などにより fused read 自体が使われない場合も同様です。

## 実行時の詳細

値はプロセス起動時ではなく、V3 split 内で 5〜8 token の分岐が初めて `gr_r2()` を呼んだ時点で読み込まれ、関数ローカル `static const int` に保存されます。以後プロセス内で環境変数を変更しても再評価されません。`STRATA_GR_V3` の判定も別の関数ローカル static で初回 read 時に cache されます。CLI 引数による `STRATA_GR_R2` の上書きはありません。

R2=1 / 2 / 4 の exact-T down kernel は 5〜8 token 専用のテンプレート実体で、R2 が増えると各 warp が処理する down 行を増やし block 数を減らします。5〜6 token では R2=2 以外が exact-T R2=1 を使います。7〜8 token で R2=0 または未対応値なら `gr_down_v3_kernel<1, kFusedGrMaxT, false>` に fallback します。R2=0 の 7〜8 token では up 側も exact-T 条件を満たさず、汎用 up kernel を使います。V3 経路は down / up の起動後に `cudaGetLastError()` を確認し、失敗時は stderr に `fused_gr_read_multi v3: <CUDA error>` を出して `exit(1)` します。`STRATA_GR_R2` の無効値に対する専用警告やログはありません。

## 根拠

- `src/kernels/cuda/fused_gr.cu:1377-1382` — `atoi`、unset 既定値 2、許容値の絞り込み、static cache。
- `src/kernels/cuda/fused_gr.cu:734-748,788-817` — V3 down kernel の R2 template parameter と、warp が R2 行を担当する実装。
- `src/kernels/cuda/fused_gr.cu:2410-2425,2466-2487` — Q8 早期 return、V3 有効判定、split 条件、および 5〜8 token の down dispatch。
- `src/kernels/cuda/fused_gr.cu:2488-2504` — up dispatch と V3 kernel error の stderr / 終了経路。
- `src/kernels/cuda/fused_gr.cu:2494-2498` — 5〜8 token の up dispatch。7〜8 token は `gr_r2() > 0` で exact-T 版を選ぶ。
- `src/kernels/cuda/fused_gr.cu:2531-2537,2547-2560` — V3 を使わない場合の fallback と、8 token 超の slice 処理。
- `src/kernels/cuda/fused_gr.cu:2356-2379` — V3 の明示設定、device ごとの既定値、および HIP 既定無効。
- `src/kernels/cuda/fused_gr.cu:1383-1412` — `launch_multi()` は別経路であり `STRATA_GR_R2` を参照しないこと。
- `src/program/generate.cpp:3369,4610-4611` と `src/core/layer.cpp:1477-1478` — CLI の `--no-fused-gr` と、fused GR 呼び出しの前提条件。
- `CMakeLists.txt:80-93,456-493` — CUDA / HIP 構成と CUDA fused kernel source のビルド対象。
- `docs/DETAILS.md:1062` — `STRATA_GR_V3` の説明。`STRATA_GR_R2` の説明・測定値は同資料で確認できず、性能向上率は本書では主張しない。
