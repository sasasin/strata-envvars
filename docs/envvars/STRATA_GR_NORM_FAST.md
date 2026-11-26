# `STRATA_GR_NORM_FAST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

ハイパーコネクションの複数 token 読み取りで、stream ごとに正規化する split/staged variant が選ばれたとき、通常の `gr_norm_split_kernel` の代わりに register-split 実装 `gr_norm_split_fast_kernel` を起動するかを制御する。後者は各 thread が load した値を register に保持し、正規化結果を書き戻す経路を使う。実装コメントは同じ要素を同じ演算順で処理すると説明している（`engine/src/kernels/cuda/fused_gr.cu:1219-1224, 1252-1263`）。

この変数だけでは fused hyper-connection read や split/staged variant 自体を有効化しない。fused read は native MMVF が有効で `--no-fused-gr`、GPU stages、layer/half dump、stage timing の各条件で除外されない場合に設定され、対応するモデル geometry の layer で使われる（`engine/src/program/generate.cpp:6104-6113`; `engine/src/core/layer.cpp:1500-1502`）。

## 値と判定

読み取りは `norm_fast_on()` 内の関数ローカル `static` 初期化子で一度行う。設定値は `std::atoi` の結果が 0 かどうかで判定される。文字列全体の妥当性検査や `true` / `false` の解釈はない。`atoi` が数値として読める先頭部分を変換するため、例では `1tail` や ` 1tail` は有効、`0tail`、`true`、空文字は無効になる。負の非ゼロ値も有効。

| build / backend | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA（`__HIPCC__` ではない build） | OFF | `1`、`-1`、`1tail` | `0`、`0tail`、`true`、空文字 |
| HIP build | 対象 device の arch 名が gfx12 なら ON、それ以外は OFF | CUDA と同じ。明示値は arch 既定を上書き | CUDA と同じ |

HIP の unset 時は device 番号取得または properties 取得に失敗した場合も OFF。明示値があれば device 判定は行わない。`engine/src/kernels/cuda/fused_gr.cu:1534-1550`。

CUDA の Volta (`sm_70`) では起動時の NVIDIA 既定値注入が追加の既定値になる。単一 GPU または全可視 GPU が同じ compute capability の CUDA 実行で、`STRATA_SM70_PERF=0` と `STRATA_DEFAULTS=026` による抑止がない場合、`apply_nv_defaults` が未設定のこの変数を `1` にする。値が何であっても既に環境にあればユーザー設定を維持し、空文字も「設定済み」として優先される（`engine/src/core/nv_defaults.cpp:136-148, 222-234`; `engine/src/program/generate.cpp:4421-4449`）。

## 有効になる条件

- fused hyper-connection read が選ばれ、`fused_gr_variant()` が split または staged (`variant >= kHcSplit`) を返すこと。未チェック時の `STRATA_HC_SPLIT` は unset/空/`2` 系で staged、先頭 `0` で plain、先頭 `1` で split を指定し、通常の verifier 初期化では `fused_gr_check()` が variant を検査して決める（`engine/src/kernels/cuda/fused_gr.cu:1933-1940, 4732-4739, 4755-4796`）。plain variant ではこの変数を参照しない。
- CUDA は `STRATA_GR_NORM_FAST` が非ゼロであること。CUDA の unset は単独では OFF だが、前述の `sm_70` 既定値注入が適用される場合は `1` になる（`engine/src/kernels/cuda/fused_gr.cu:1532-1550`; `engine/src/core/nv_defaults.cpp:136-148`）。
- HIP の unset は、現在の device が `gfx_arch_is_gfx12` に該当する場合だけ ON。明示値はこの arch 条件を置き換える（`engine/src/kernels/cuda/fused_gr.cu:1534-1545`）。
- `fused_gr_read_multi_slice()` の先行分岐で処理が終わらないこと。Q8 weight 経路は `launch_q8()` から戻り、RDNA 経路は `rdna_gr_read_multi()` から戻るため、どちらもこの norm 判定に到達しない（`engine/src/kernels/cuda/fused_gr.cu:4285-4303`）。
- HIP で `rdna_gr_enabled()` が true のときも RDNA 読み取りが先に使われる。これは `STRATA_GR_RDNA`、または未設定時の `STRATA_HIP_FAST_DEC` と arch により決まる（`engine/src/kernels/cuda/fused_gr.cu:4295-4302`; `engine/src/kernels/cuda/rdna_gr.cu:555-571`）。
- CUDA の `STRATA_GR_SPLIT=1` 経路は `launch_multi()` より前に別の norm kernel を起動して return するため、この変数の選択対象ではない（`engine/src/kernels/cuda/fused_gr.cu:4400-4425`）。

## 実行時の詳細

環境値はプロセスで最初に `norm_fast_on()` が呼ばれた時に static cache され、実行中に環境を変更しても再評価されない。HIP では gfx12 かどうかの判定も device ごとの `per_dev[64]` に初回取得結果を cache する。CUDA 側の値は process-wide の単一 bool である（`engine/src/kernels/cuda/fused_gr.cu:1534-1550`）。

split/staged variant では `norm_fast_on()` が true なら grid `(n_tok, HC)` で `gr_norm_split_fast_kernel`、false なら同じ grid で `gr_norm_split_kernel` を起動する。`STRATA_GR_FAST_BUILD` が false の build でも split/staged 分岐はこの判定を行う。macro は CUDA build すべてと HIP の `STRATA_HIP_GFX906` build で true、それ以外の HIP build で false（`engine/src/kernels/cuda/fused_gr.cu:48-53, 1782-1795`）。

CUDA build の既定値テーブルは `generate` 起動処理で engine が環境値を読む前に適用される。`apply_nv_defaults()` は既存環境値を保持して、未設定項目だけ `setenv` / `_putenv_s` する（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:222-234`）。CLI 引数がこの環境変数自体を上書きする経路は確認できないが、fused read の CLI 条件が満たされない場合は変数の値にかかわらず対象 kernel に到達しない。

## ログと測定値

この変数自体を有効・無効と表示するログはない。Volta 既定値テーブルが一つ以上の switch を注入すると、共通の `strata: sm_70 (Volta): ...` 起動行が適用 switch 名を列挙する（`engine/src/core/nv_defaults.cpp:240-255`）。読み取り後の kernel launch error は `fused_gr_read_multi: <CUDA error>` を stderr に出して `exit(1)` するが、このエラーは本変数固有の検査や fallback ではない（`engine/src/kernels/cuda/fused_gr.cu:4424-4429`）。

`docs/NVIDIA_V100.md:135` は V100 で `STRATA_GR_NORM_FAST=1` の decode が `+0.5-0.6%` と記載する。実装コメントの測定対象も sm_70 のみとしているが、当該資料のこの行にはモデル、quantization、試行回数などの条件がないため、他環境へ一般化できない（`engine/src/kernels/cuda/fused_gr.cu:1532-1548`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:48-53, 1219-1263, 1532-1550, 1782-1795` — build guard、kernel、値判定と dispatch。
- `engine/src/kernels/cuda/fused_gr.cu:1933-1940, 4285-4303, 4400-4429, 4732-4811` — variant、先行経路、エラーと初期化時の選択。
- `engine/src/core/nv_defaults.cpp:136-163, 222-255`; `engine/src/program/generate.cpp:4421-4449` — Volta の既定値、ユーザー設定優先、適用時期とログ。
- `engine/src/program/generate.cpp:6104-6113`; `engine/src/core/layer.cpp:1500-1502` — fused read の CLI / geometry 条件。
- `engine/src/kernels/cuda/rdna_gr.cu:555-571` — HIP の RDNA 経路が先行する条件。
- `docs/NVIDIA_V100.md:135`; `docs/DETAILS.md:1480-1495` — 資料の測定記載と既定値表。

`docs/DETAILS.md:1487` は sm_70 既定値の一覧に本変数を含める一方、同ファイル `1494-1495` は「全セットから除外」と記載しており、資料内に矛盾がある。現行コードの `nv_default_env()` は sm_70 の既定値一覧に `STRATA_GR_NORM_FAST=1` を含めるため、実装上は注入対象である。
