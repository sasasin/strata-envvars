# `--draft-beam`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--draft-beam` |
| 別名 | なし |
| 値 | 整数。CUDA の DSpark speculative beam tree の幅に使われる |

## 役割

CUDA backend で DSpark の推測木を作る際の beam 幅を指定します。`1` は線形の1経路、既定値の `4` は beam tree です。幅を変えることでドラフターが各段階で展開する候補数を変えます。推測木の後に本体モデルで検証して受理経路を選びます（`engine/src/inkling2/ink_backend.h:36-41`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1081`、`engine/src/inkling2/cuda/ink_dspark.cuh:1603-1619`）。

## 使い方

```sh
# サーバーで CUDA DSpark の beam 幅を1にする
strata-inkling --serve --native model.strata --draft dspark --draft-beam 1
```

## 値と既定値

- 値は次の引数1個として読み取られ、`std::atoi` で整数化されます。引数を省略すると `missing value after --draft-beam` を標準エラーに出して終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:845-850,898-900`）。
- CLI 値は正数の場合だけ設定に反映されます。未指定時の内部既定値は `4` です。`STRATA_INK_SPEC_BEAM` が設定されていればまずその値を読み、正の CLI 値があれば上書きします（`engine/src/inkling2/ink_backend.h:37`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1205-1206`）。
- `0`、負数、または整数として読めない文字列は `atoi` の結果が正数でないため、CLI 値としては採用されません。その場合は `STRATA_INK_SPEC_BEAM` または内部既定値が使われます。環境変数の値も CUDA backend で補正され、専用の範囲エラーはありません（`engine/src/inkling2/ink_main.cpp:898-900`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:118-124`）。
- CUDA backend の初期化では設定を1〜8に収めますが、実際の `draft_beam_tree` はさらに幅を `kInkMaxBeam`（4）以下に制限します。したがって実効値は1〜4です。1は線形経路、4は最大 beam 幅です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:124`、`engine/src/inkling2/cuda/ink_dspark.cuh:721-722,1696-1701`）。

## 実行時の動作

parser は値を `BackendOpts::spec_beam` に保存します（`engine/src/inkling2/ink_main.cpp:898-900`）。CUDA backend 初期化時に `STRATA_INK_SPEC_BEAM` を読み、正の CLI 値があれば環境変数より優先して beam 設定に反映します。既定値は4です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1205-1206`）。推測ステップではその設定を `draft_beam_tree` に渡し、beam 候補を展開します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1064-1076`、`engine/src/inkling2/cuda/ink_dspark.cuh:1617-1645,1696-1701`）。

この設定が推測処理に現れるのは `--serve` と `--bench` の経路です。serve は DSpark が利用可能で、アクティブ要求が1件、greedy sampling で penalty がなく、コンテキストに余裕がある場合に speculative tree step を呼びます。`STRATA_INK_SPEC=block` は serve の tree 経路を線形 block drafter に切り替えます（`engine/src/inkling2/ink_serve.h:507-514,876-890`）。bench では DSpark が有効で並列数が1のとき、生成中に同じ speculative step を呼びます（`engine/src/inkling2/ink_main.cpp:131-145,198-214`）。通常の直接生成ループは `dspark_spec_step_greedy` を呼ばないため、この値はそのループの生成方法を変えません（`engine/src/inkling2/ink_main.cpp:1097-1144`）。

## 適用条件と副作用

- CUDA backend の DSpark speculative tree に適用されます。DSpark がモデルに存在しない、無効化されている、backend が利用可能状態でない場合などは speculative step が呼ばれず、beam 幅は使われません（`engine/src/inkling2/ink_serve.h:507,876-890`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:1065-1067`）。
- parser は CUDA/HIP 共通の `ink_main.cpp` にありますが、確認した HIP の speculative tree 実装では `BackendOpts::spec_beam` を参照していません。HIP でこのオプション値が実際の幅を変えるかは、この値の参照経路からは確認できません（`engine/src/inkling2/ink_main.cpp:898-900`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2120-2148`）。
- このオプション自体はファイルやネットワーク設定を変更しません。実行時には speculative drafting と tree verification の計算経路で使われます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1064-1081`）。

## 出力とエラー

正数値の範囲外を指定しても専用エラーは出ず、最終的に1〜4へ補正されます。欠落値は終了コード `2`、未知のオプションも終了コード `2` です（`engine/src/inkling2/ink_main.cpp:847-850,898-900,985-987`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:124`、`engine/src/inkling2/cuda/ink_dspark.cuh:1698-1701`）。このオプション固有の出力メッセージは確認できませんでした。

## 根拠

- `engine/src/inkling2/ink_main.cpp:847-850,898-900` — 値の取得、整数変換、欠落値エラー。
- `engine/src/inkling2/ink_backend.h:36-41` — backend option の既定値と beam 値の説明。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,1205-1206` — 環境変数・CLI の優先順位と CUDA 側既定値・補正。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:1064-1076`、`engine/src/inkling2/cuda/ink_dspark.cuh:721-722,1603-1645,1696-1701` — speculative step から beam 幅が木の展開に渡る経路と最終上限。
- `engine/src/inkling2/ink_serve.h:507-514,876-890`、`engine/src/inkling2/ink_main.cpp:131-145,198-214,1097-1144` — serve/bench/direct generation の適用条件。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2120-2148` — HIP 側 speculative step の入口と初期条件。確認範囲では beam option の参照なし。
