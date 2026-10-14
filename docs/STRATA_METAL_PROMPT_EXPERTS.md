# `STRATA_METAL_PROMPT_EXPERTS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal のストリーミング用 prompt GEMM 経路で、routed expert の gate/up と down に使う kernel 世代を選びます。`v3` は `mm_gu3` / `mm_down3`、それ以外は `mm_gu2` / `mm_down2` を選びます。この変数は prompt の行列演算全般や decode の経路を選ぶものではありません。

## 値と判定

`prompt_gemm_init()` の初期化時に環境変数を一度読みます。設定値は文字列全体を大文字小文字を区別して比較し、完全一致する `v3` だけが v3 になります。未設定なら `COOP_K4` による指定または実行時のレイアウト判定 `p.k4` が既定値になります。空文字、`v2`、`V3`、`3` など `v3` 以外の設定値は v2 を選びます。

| `STRATA_METAL_PROMPT_EXPERTS` | 選択結果 |
|---|---|
| 未設定 | `p.k4 == true` なら v3、false なら v2 |
| `v3` | v3 |
| 空文字、`v2`、その他の文字列 | v2 |

未設定時の `p.k4` は `COOP_K4` が設定されていれば `atoi(value) != 0` で決まり、未設定なら Metal kernel の出力を調べるレイアウト probe の結果です。したがって `COOP_K4=0` は未設定時の v3 既定を無効にし、`COOP_K4=1` は有効にします。ここでの `atoi` は文字列全体の妥当性を検査せず、数値変換結果が 0 かどうかで判定します。

## 有効になる条件

- Metal engine の prompt 処理で `prompt_gemm_init()` が呼ばれる必要があります。確認できた呼び出し箇所は streaming arena の初期化と、`STRATA_METAL_PROMPT_GEMM` が無効でなく prompt 長が閾値以上の streaming prompt 経路です。
- resident（非 streaming）で通常選ばれる prompt chain は `prompt_chain.inc` の `pc_setup()` が `COOP_K4` を使って初期化し、この変数は読みません。そのため `STRATA_METAL_PROMPT_EXPERTS` はその経路の expert kernel 世代を変更しません。
- prompt GEMM 自体が使われない場合、この設定も適用されません。streaming prompt では `STRATA_METAL_PROMPT_GEMM=0` または prompt 長が `STRATA_METAL_PROMPT_GEMM_MIN` 未満の場合、通常の decode window 経路に進みます。

## 実行時の詳細

初期化で選択結果は `PromptGemm::gu_v3` と `dn_v3` に同じ値として保存されます。各 prompt chunk の routed expert 計算では、gate/up が v3 の場合 `mm_gu3_<type>_16_32_32_4`、v2 の場合は quant type ごとの `mm_gu2_<type><tile>` を dispatch します。down も v3 なら `mm_down3_<type>_16_64_32_2`、v2 なら quant type ごとの `mm_down2_<type><tile>` を dispatch します。選択結果と `p.k4` のレイアウト情報は初期化時に stderr の `strata metal: prompts on the matrix units ... (experts v2|v3, ... matmul2d layout K4|other; ...)` 行に表示されます。

環境変数は `prompt_gemm_init()` が初めて成功して `pg_` を作る際に読み込まれます。後続 chunk では保存済みの選択値を使い、プロセス実行中に環境を変えても初期化済みの `PromptGemm` には反映されません。

## 根拠

- 変数の読み取り、既定値、同時に保存するフラグ: `metal/src/engine/window.cpp:2019-2044`。
- 選択した gate/up・down kernel と dispatch: `metal/src/engine/window.cpp:2333-2369`。
- `p.k4` の環境変数優先順位と未設定時のレイアウト probe: `metal/src/engine/prompt_chain.inc:26-47`。
- resident 用 prompt chain が独自の `coop_k4()` 判定を使う箇所: `metal/src/engine/prompt_chain.inc:49-60`。
- streaming prompt で GEMM 初期化へ進む条件、および fallback: `metal/src/engine/window.cpp:2555-2585`。
- 選択内容の stderr 表示: `metal/src/engine/window.cpp:2099-2104`。
- `docs/MAC.md` は Metal prompt GEMM と M5 layout に言及しますが、この環境変数の許容値や個別 variant の性能比較は記載していません。性能差はこの調査では確認していません。
