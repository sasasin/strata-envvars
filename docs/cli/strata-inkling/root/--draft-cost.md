# `strata-inkling --draft-cost`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--draft-cost` |
| 別名 | なし |
| 値 | 数値文字列。正数のみ CUDA backend の係数として採用 |

## 役割

CUDA backend の DSpark speculative beam tree が検証窓のサイズを選ぶときに使う、検証ステップに対する MoE コスト比を指定します。推定コストを変えることで、期待生成トークン数と窓のコストから選ばれる tree のノード数に影響します。共通 parser は CUDA/HIP の実行ファイルにありますが、現行ソースでこの値を読み取るのは CUDA backend です。

## 使い方

```sh
# CUDA backend でserveし、コスト比を 6.0 に指定する
strata-inkling --serve --native ./model.strata --draft-cost 6.0
```

## 値と既定値

- 値は必須です。値を省略すると parser の `next()` が `missing value after --draft-cost` を stderr に出して終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:847-849,900-901`）。
- parser は値を `std::atof` で変換し、数値形式・有限性・範囲の検証やエラー処理をしません。数値化できない文字列は `atof` の結果 `0` になります。オプションを複数回指定すると `spec_cost` は順に代入され、最後の値が残ります（`engine/src/inkling2/ink_main.cpp:845-849,900-901`）。
- CUDA backend の既定係数は `4.2` です。CLI の値は `spec_cost > 0` のときだけ採用されるため、0 以下や数値化できず 0 となる値では CLI 値が採用されません（`engine/src/inkling2/ink_backend.h:38`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:120-124,1205-1206`）。

## 実行時の動作

CUDA backend 初期化時、まず `STRATA_INK_SPEC_COST` が設定されていればその値を `atof` で読みます。その後、CLI の `--draft-cost` が正数なら環境変数値を上書きします。したがって CLI の値が 0 以下、または `atof` により 0 となる値の場合、設定されている環境変数値（なければ既定値 `4.2`）が残ります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-124,1205-1206`）。環境変数 `STRATA_INK_SPEC_COST` 自体の個別文書は、この調査時点で見つかりませんでした。

CUDA backend はこの係数を `draft_beam_tree()` に渡します。係数が正数の場合、候補ノード数の各 bucket について、期待出力数を `1 + 係数 × (1 - (15/16)^M)` で割った値を比較して tree サイズを選びます。係数が正数でない場合、この動的な選択分岐に入らず、通常の上限内の候補数が使われます（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1076`; `engine/src/inkling2/cuda/ink_dspark.cuh:1696-1699,1754-1778`）。

この処理は、serve loop が DSpark を利用可能と判断し、単一 slot の speculative fast path に入り、greedy・penalty なし等の条件を満たしたときの CUDA beam tree 経路で呼ばれます（`engine/src/inkling2/ink_serve.h:507,876-890`）。

## 適用条件と副作用

- CUDA backend では、モデルに DSpark drafter があり、backend 初期化に成功した場合に drafter を作成します。GPU メモリ不足なら DSpark を無効にして warning を stderr に出す経路があります。その場合、本オプションによる tree 選択は行われません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:343-352`）。
- `strata-inkling` の共通 parser は HIP 実行ファイルでも本オプションを受理しますが、HIP 側に `spec_cost` の参照はなく、その tree 選択では係数 `4.2` が固定されています（`engine/src/inkling2/ink_main.cpp:900-901`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2384-2401`）。そのため HIP では本オプションの値は使われません。
- 調査した parser と利用箇所には、本オプション専用の警告・エラー出力、ファイル書き込み、ネットワーク操作はありません。誤った形式の値も parser では失敗しませんが、正数でなければ CUDA 側で係数として採用されません。

## 出力とエラー

値の省略による parser エラーは stderr と終了コード `2` です。未知のオプションは `unknown option: <値>` を stderr に出して終了コード `2` になります（`engine/src/inkling2/ink_main.cpp:847-849,974-987`）。数値として不正な値について、本オプション固有のエラーや警告は確認できません。

## 根拠

- `engine/src/inkling2/ink_main.cpp:845-849,898-902` — 共通 parser の値取得、`atof` 変換、引数省略時の失敗。
- `engine/src/inkling2/ink_backend.h:36-40` — backend option の初期値と `spec_cost` の役割。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-125,343-352,1064-1076,1205-1206` — 環境変数と CLI 値の優先、DSpark 初期化条件、beam tree への係数転送、既定値。
- `engine/src/inkling2/cuda/ink_dspark.cuh:1696-1699,1754-1778` — 正の係数を使った候補 tree サイズの選択式。
- `engine/src/inkling2/ink_serve.h:507,876-890` — DSpark/speculative fast path の適用条件。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2384-2401` — HIP の tree 選択が固定係数 `4.2` を使う箇所。
