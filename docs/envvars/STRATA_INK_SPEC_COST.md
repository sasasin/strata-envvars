# `STRATA_INK_SPEC_COST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 `strata-inkling` の DSpark speculative beam tree で、検証ステップの MoE コスト比を指定する。値が正の場合、DSpark が予測確率とこのコスト比から tree のノード数を選ぶ。変更するのは提案する tree の幅・長さであり、tree 内の候補を target model で greedy argmax 検証する処理自体は同じである。読み取りは `InkCudaBackend::init`、利用は `dspark_spec_step_greedy` から `InkDSpark::draft_beam_tree` への呼び出しである（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1057-1079`; `engine/src/inkling2/cuda/ink_dspark.cuh:1696-1701,1754-1779`）。

## 値と判定

環境変数は `std::getenv` で存在を判定し、設定されていれば `std::atof` で float に変換する。環境変数の値を全体として検証する処理や範囲制限はない。空文字や数値として始まらない文字列は通常 `atof` により `0` となり、数値の後ろに文字があっても数値部分が変換される。空白や符号を含む入力も `atof` の変換規則に委ねられる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-123`）。

| 条件 | unset | 設定時にコスト判定へ使われる値 | 設定されるがコスト判定に使われない値 |
|---|---|---|---|
| CUDA backend | `SpecCfg::cost` の初期値 `4.2` | `atof` の結果を float 化した値が `> 0`。例: `0.1`, `4.2`, `10`, `1tail`（`1` として変換） | `0`, `-1`, 空文字、`nope` は `0` 以下となり、適応ノード数選択を行わない。beam tree のノード数は `max_nodes` と候補数の範囲内で選ぶ |
| CPU / HIP / Metal / SYCL backend | この変数を読むコードなし | 該当なし | この Strata ソース内では効果なし |

`--draft-cost R` が指定され、その変換値が `> 0` なら環境変数の値を上書きする。CLI の値が `0`、負値、または `atof` で `0` となる文字列の場合は上書き条件を満たさず、環境変数由来の値（または既定値）が残る。`--draft-cost` の既定値は `-1.0` である（`engine/src/inkling2/ink_backend.h:37-39`; `engine/src/inkling2/ink_main.cpp:898-902`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:118-124`）。

## 有効になる条件

- `INKLING_ENABLE_CUDA` が選ばれ、`make_default_backend` が CUDA backend を生成すること。CPU 強制時や HIP / Metal / SYCL backend ではこの変数を読む実装に入らない（`engine/src/inkling2/ink_backend.h:198-215`）。
- CUDA backend の `init` 時に変数を読む。値を読むこと自体は DSpark が無効でも行うが、実際に使うには `--draft` が `off` でなく、モデルに DSpark があり、backend の DSpark 初期化が成功することが必要（`engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352`; `engine/src/inkling2/ink_serve.h:507`）。
- 係数による適応ノード数選択は値が `> 0` のときだけ有効。`0` 以下では `draft_beam_tree` の適応選択分岐を通らない（`engine/src/inkling2/cuda/ink_dspark.cuh:1754-1779`）。
- サーバーでは単一ストリームの greedy 要求で、罰則なし、生成残量と context headroom が十分で、`STRATA_INK_SPEC=block` による block drafter 選択などに該当しない場合に beam tree 経路を呼ぶ。複数要求、非 greedy、penalty あり、context 余裕不足などではこの経路を使わない（`engine/src/inkling2/ink_serve.h:507-514,876-890`）。
- `--bench` は DSpark が有効な場合、`--spec-check` は指定時に DSpark を有効化して speculative step を実行する。通常の直接 CLI 生成ループには `dspark_spec_step_greedy` の呼び出しがない（`engine/src/inkling2/ink_main.cpp:131-145,599-609,1062-1071,1111-1145`）。
- `--draft-cost` の正値は環境変数より優先される（`engine/src/inkling2/cuda/ink_cuda_backend.cu:119-123`）。

## 実行時の詳細

値の読み取りは `InkCudaBackend::init` 中に行われ、生成リクエストごとの読み直しや環境値の static cache はない。得た値は `spec_cfg_.cost` に保持され、tree speculative step から DSpark の `draft_beam_tree` に渡される。CUDA backend の初期化をやり直せば再評価されるが、初期化後にプロセス環境を変えても保持済みの値には反映されない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1073-1079,1201-1206`）。

`draft_beam_tree` は候補の累積確率から期待 token 数を計算し、`1 + cost * (1 - (15/16)^M)` をコスト項として候補 tree サイズを比較する。正の係数のとき候補サイズのうち最も高い期待 token 数 / コストのものを選択し、選択したサイズまで親子関係を保って tree を組む。CUDA 側はその tree を target model で検証し、target の greedy argmax に合う経路だけを採用する。したがってこの変数が直接変えるのは提案 tree のサイズであり、target 側の検証基準ではない（`engine/src/inkling2/cuda/ink_dspark.cuh:1760-1779,1781-1807`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1108`）。

## ログと測定値

この変数の読取り・値・適用結果を直接表示するログはない。別変数 `STRATA_INK_SPEC_LOG` が設定されている場合は、200 回ごとに stderr へ `[SPEC-STATS] steps=... mean_M=... mean_pred_tokens=... mean_actual_tokens=... plain_steps=...` を出すが、コスト係数そのものは出力しない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:125,1115-1119`）。`STRATA_INK_SPEC_COST` 固有の測定値は Strata の `docs/DETAILS.md` に見当たらない。

## 根拠

- 読取り、CLI 上書き、beam 上限: `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125`。
- 値の既定値: `engine/src/inkling2/cuda/ink_cuda_backend.cu:1205-1206`。
- backend 選択: `engine/src/inkling2/ink_backend.h:198-215`。
- 適応コスト式と node 選択: `engine/src/inkling2/cuda/ink_dspark.cuh:1696-1701,1754-1807`。
- speculative tree の呼び出し・target 検証: `engine/src/inkling2/cuda/ink_cuda_backend.cu:1057-1108`。
- サーバーでの利用条件: `engine/src/inkling2/ink_serve.h:507-514,876-890`。
- `--bench` / `--spec-check` と通常 CLI の経路: `engine/src/inkling2/ink_main.cpp:131-145,599-609,1062-1071,1111-1145`。
- DSpark の初期化条件・メモリ不足時の停止ログ: `engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352`。
