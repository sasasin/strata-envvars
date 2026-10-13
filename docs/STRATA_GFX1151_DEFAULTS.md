# `STRATA_GFX1151_DEFAULTS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP 版 `strata generate` が GPU 0 を確認し、その GPU が gfx1151（Strix Halo）なら、gfx1151 で出力がビット単位で一致するとしている複数の最適化用環境変数を、ユーザーが設定していない場合に限ってプロセス環境へ追加します。この変数は一括して既定値を適用するかどうかを決めます。各最適化の値を個別に指定する変数ではありません。

## 値と判定

`src/core/arch_defaults.cpp` は `std::getenv("STRATA_GFX1151_DEFAULTS")` の結果を確認します。

| 値 | 結果 |
|---|---|
| 未設定 | gfx1151 では既定値テーブルを適用 |
| 空文字 | 先頭文字は `\0` であり `'0'` ではないため、テーブルを適用 |
| 先頭文字が `0` | テーブル全体を適用しない。`0`, `0anything` が該当 |
| その他 | テーブルを適用。文字列全体や数値としては解釈しない |

大文字小文字、空白、文字列の後半は検査しません。たとえば `false` や ` 0` はテーブルを止めず、`0x` は止めます。

## 有効になる条件

- `STRATA_USE_HIP` でビルドした `strata generate` の経路で実行されること。CUDA ビルドにはこの適用処理がありません。
- GPU 0 の `cudaGetDeviceProperties` が成功し、`gcnArchName` が gfx1151 と一致すること。アーキテクチャ判定は `gfx1151` の完全一致、またはその後ろが `:` の場合に成立します（例: `gfx1151:sramecc-:xnack-`）。
- `STRATA_GFX1151_DEFAULTS` の先頭文字が `0` ではないこと。

この変数は gfx12 には適用されません。gfx12 は別の `STRATA_GFX12_DEFAULTS` テーブルで処理され、その他の GPU アーキテクチャでは gfx1151 のテーブルが空になります。GPU 情報の取得に失敗すると既定値適用を呼ばず、エラー状態を消去します。

## 実行時の詳細

コマンドライン引数の解析後、エンジンが各スイッチを初回読み取りする前に GPU 0 を調べ、`apply_arch_defaults()` を呼びます。テーブルの各変数について `getenv()` が非 `nullptr` なら、値が空文字でもユーザー設定として保持し、上書きしません。未設定なら POSIX では `setenv(..., 0)`、Windows では `_putenv_s()` で設定します。この設定は同じプロセスの環境に入り、後続の遅延読み取りに使われます。子プロセスへの転送処理はこのコードにはありません。

gfx1151 で適用される既定値は次のとおりです。

| 設定する変数 | 設定値 | ソース注釈上の対象 |
|---|---:|---|
| `STRATA_GDN_HEAD` | `1` | GDN recurrence のカーネル構成 |
| `STRATA_GDN_PP` | `2` | GDN prompt recurrence の列処理 |
| `STRATA_GDN_CONVL2` | `1` | GDN convolution と q/k L2 norm の融合 |
| `STRATA_GDN_NOY` | `1` | 読まれない FP32 norm 出力の store を省略 |
| `STRATA_CVEC_FUSE` | `1` | steered layer の write、control vector、次の norm の融合 |
| `STRATA_HCD_EXACT` | `1` | HC down projection の exact-order WMMA 経路 |
| `STRATA_PF_PAD` | `1` | GEMM の padded row stride |
| `STRATA_Q8_PACKED` | `1` | Q8_0 decode 用 packed weight layout |
| `STRATA_Q6_PACKED` | `1` | Q6_K head 用 packed layout |
| `STRATA_MMVF_ROWS` | `1` | BF16 multi-row GEMV（4 rows/block） |
| `STRATA_ATTN_LANECELL` | `1` | decode attention score の one-cell-per-thread 経路 |
| `STRATA_EXPERT_V2` | `1` | IQ3_S gate/up と IQ4_NL down の grouped decode experts |
| `STRATA_TSUM` | `1` | warp sum の transposed butterfly 経路 |
| `STRATA_LFUSE` | `1` | shared expert と KV append 周辺の launch 融合 |
| `STRATA_GDN_SPLIT` | `1` | GDN step を head あたり 4 blocks に分割 |
| `STRATA_QFUSE` | `1` | producer 側で activation q8_1 image を書き込む経路 |
| `STRATA_PLE_BATCH` | `1` | verify window の PLE key/value projection の一括処理 |
| `STRATA_SH_STREAM` | `1` | shared expert を routed experts と別 stream で実行 |

各スイッチの詳細な適用形状や追加条件はそれぞれの実装に従います。この環境変数が `1`（または上記以外の有効値）でも、個別スイッチが既に設定済みなら、その個別値が優先されます。また、個別スイッチの条件に合わない処理では該当最適化は使われません。

適用したスイッチが1つ以上あれば stderr に `strata: gfx1151 (Strix Halo): 18 exact speed switches on by default (STRATA_GFX1151_DEFAULTS=0 turns them off; a switch you set is kept): ...` の形式で、実際に設定した名前を出します。全スイッチがすでにユーザー設定済みの場合や一括無効の場合は、`apply_arch_defaults()` によるこの行は出ません。

Strix Halo の説明書は、この一覧がメンテナー環境で同一 token ID（4K/32K/64K、4モデル）と kernel ごとの bitwise harness により byte-identical だったと記載しています。これは文書の報告内容であり、本調査では測定や GPU 実行を行っていません。`STRATA_GFX1151_DEFAULTS` 自体の性能値は確認できません。

## 根拠

- `src/program/generate.cpp:2152-2158` — HIP 限定、GPU 0 の情報取得と適用時期。
- `src/core/arch_defaults.cpp:12-35` — gfx12/gfx1151/その他の判定と一括無効値の判定。
- `src/core/arch_defaults.cpp:36-58` — gfx1151 の既定値テーブル。
- `src/core/arch_defaults.cpp:61-81` — 個別設定の保持、プロセス環境への設定、stderr ログ。
- `include/strata/kernels/gfx_arch.hpp:15-19,32-36` — GPU 名の照合規則。
- `include/strata/core/arch_defaults.hpp:19-26` — 関数の契約と、スイッチ初回読み取り前に呼ぶこと。
- `docs/STRIX_HALO.md:83-98` — 適用対象、個別スイッチの説明、同一出力についての文書上の報告。
