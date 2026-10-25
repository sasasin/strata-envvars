# `STRATA_EXPDEC_DRB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の EXPDEC down kernel で、1 block が担当する出力行数 `rb` を指定します。EXPDEC は `native_expert_grouped` の down 計算を専用 kernel に切り替える機能です。この変数だけでは EXPDEC や down 経路を有効にしません。EXPDEC が有効で、down 用 EXPDEC と対象レイアウトの条件も満たすときにだけ使われます。

## 値と判定

値は `env_int_or()` が `std::getenv()` で読み、未設定または空文字列なら既定値 `0` を使います。それ以外は `std::atoi()` で整数に変換します。文字列全体の妥当性検査やエラー通知はなく、`atoi` が数値として読めない文字列は通常 `0` になり、自動設定になります。数値の後ろに続く文字列も検証されません。

| 変換後の値 | 行数 `rb` の決定 |
|---|---|
| 0 または負数 | 自動設定。初期値を rows-per-pass (`rpp`) とし、後述の条件を満たす間、倍増する |
| 正数 | `rpp` の倍数に切り上げる。結果が `n_embd` を超える場合は `n_embd` に制限する |

`rpp` は down の量子化型と `STRATA_EXPDEC_DR` の有効値で決まり、CUDA block の 256 threads を lane 数で割って `R` を掛けた値です。down type 20 では lane 数 8、type 42 では lane 数 16 です。`STRATA_EXPDEC_DR` は 1 または 2 のときその値、それ以外は 4 として扱われます。

自動設定では、`rb` を倍にしても `rb <= n_embd` であり、`ceil(n_embd / (2*rb)) * max(cap_groups, 1) >= g_expdec_minblk` である間、倍増を続けます。`g_expdec_minblk` の既定値は 800 です。従って 0 は固定の行数ではなく、その呼び出しの shape と group 数にも依存します。

## 有効になる条件

`STRATA_EXPDEC_DRB` が正数でも、次の条件に合わない down 計算には適用されず、呼び出し元の default down kernel が使われます。

- CUDA の `iq_kernels.cu` にある `native_expert_grouped` 経路を通る。
- `STRATA_EXPDEC` または `native_expert_set_expdec()` により EXPDEC が有効で、旧 multi kernels (`g_old_kernels`) が無効。
- `STRATA_EXPDEC_DOWN` が非ゼロ。
- down type が 42、または type 20 かつ `STRATA_EXPDEC_D20` が非ゼロ。
- `n_ff == 32 * ED_HB`（`ED_HB` は 20）、`n_embd` が正で 128 の倍数。

EXPDEC down の対象レイアウトでなければ、この変数を設定しても kernel 選択や行分割は変わりません。`docs/EXPERTDEC.md` では down の EXPDEC を `STRATA_EXPDEC_DOWN=1` で有効にする追加 opt-in とし、IQ4_NL down は `STRATA_EXPDEC_D20=1` も必要と説明しています。

## 実行時の詳細

値は `iq_kernels.cu` のグローバル変数 `g_expdec_drb` 初期化時に一度読み込まれ、down kernel の launch 時に `expdec_rows_per_block()` へ渡されます。設定後に `native_expert_set_expdec_params()` が `down_rows_per_block >= 0` の値を渡すと、プロセス内の `g_expdec_drb` はその値で上書きされます。リポジトリ内ではこの setter は `expdec_bench` から呼ばれます。CUDA graph に capture 済みの launch は capture 時に決まった kernel 構成を保持します。

正数指定では `rb` を使って grid の x 次元を `ceil(n_embd / rb)` とし、auto 指定では同じ計算で得た自動 `rb` を使います。EXPDEC down が実際に選ばれた最初の (down role, format) では stderr に `strata expdec: CUDA%d down type %d: expdec_down_kernel R %d, %d rows per block, grid %d x %lld (cap %lld groups)%s` の形式で選択結果を出します。対象外の場合は `not covered: the default kernel runs` の行を出す経路があります。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3933-3937,3948-3953`: `env_int_or()` の変換、`g_expdec_drb` の既定値、`STRATA_EXPDEC_DR` の値の丸め。
- `src/kernels/cuda/iq_kernels.cu:3959-3973`: down 対象条件と、正数・自動それぞれの `rb` 算出。
- `src/kernels/cuda/iq_kernels.cu:4045-4070`: down kernel の行数/grid と EXPDEC down の実行条件。
- `src/kernels/cuda/iq_kernels.cu:4015-4025`: stderr の選択ログと表示する行数。
- `src/kernels/cuda/iq_kernels.cu:5020-5042`: EXPDEC パラメーター API と `down_rows_per_block` による上書き。
- `include/strata/kernels/iq_kernels.hpp:100-117`: EXPDEC API とパラメーターの説明。
- `docs/EXPERTDEC.md:16-34,40-42`: EXPDEC 対象 down format、関連設定、環境設定値を読む旨と graph capture の説明。
