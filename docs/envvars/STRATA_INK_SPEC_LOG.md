# `STRATA_INK_SPEC_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA Ink backend の融合型 greedy speculative step が進んだ回数・木のサイズ・予測 token 数・実際に出力した token 数を、200 回ごとに stderr へ集計表示する診断スイッチ。設定値は統計表示の有無だけを変え、beam や生成処理の選択・結果を変える分岐には使われない。値を読む実装は `InkCudaBackend::init` のみで、統計表示は `InkCudaBackend::dspark_spec_step_greedy` 内にある（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-126,1057-1079,1103-1120`）。

## 値と判定

`std::getenv("STRATA_INK_SPEC_LOG") != nullptr` の真偽だけを保存する。未設定なら無効、環境変数が存在すれば値の内容にかかわらず有効。空文字も有効であり、文字列・数値への変換や範囲検査はない。大文字小文字、空白、数値としての妥当性も判定しない。たとえば `1`、`0`、`false`、`anything`、空文字はいずれも有効（`engine/src/inkling2/cuda/ink_cuda_backend.cu:125`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `InkCudaBackend::init` を実行 | 無効 (`false`) | 存在する値すべて。例: `1`, `0`, `false`, 空文字 | なし |

## 有効になる条件

- `INKLING_ENABLE_CUDA` を含む構成で CUDA backend が選ばれ、`InkCudaBackend::init` が呼ばれる必要がある。既定 backend の選択は非 CPU 時に CUDA 構成を優先する（`engine/src/inkling2/ink_backend.h:198-210`）。ソース内の直接参照は CUDA backend に限られ、CPU・HIP・Metal・SYCL 実装にはこの名前の読み取りがない。
- 統計表示まで進むには `dspark_spec_step_greedy` の早期 return 条件を通る必要がある。backend が初期化済みであること、モデルの `ls_active` が偽であること、DSpark が存在して ready であること、slot と `dspark_slot_` がともに `0` であること、anchor/context の余裕と出力引数が有効であることが必要（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1065-1067`）。
- serve では DSpark が有効（`--draft` が `off` 以外、モデルに DSpark があり backend が ready）、単一の有効 request、prefill 完了、残り生成数・context の余裕が必要。さらに fused tree 経路は greedy、penalty なし、`STRATA_INK_SPEC` が `block` でないこと、`cur_pos + 12 < eff_max_ctx` が条件。`STRATA_INK_SPEC=block` は線形 block drafter 側に切り替えるため、この tree 統計の経路には入らない。適応制御が有効で一時停止中の場合も fast-path を通らない（`engine/src/inkling2/ink_serve.h:507-514,876-890`）。
- ベンチマーク経路でも `use_dspark`、単一 slot、残り 2 token 以上、context の余裕があれば同じ backend 関数が呼ばれる（`engine/src/inkling2/ink_main.cpp:198-207`）。条件に届かず通常 decode や block drafter に fallback した回は、この統計カウンターに含まれない。
- `STRATA_INK_SPEC_LOG` 自体に CLI 引数や他環境変数による上書きはない。`--draft-beam`、`--draft-cost`、`--draft-plain` と対応する環境変数は別の設定値で、ログ有効判定とは独立している（`engine/src/inkling2/cuda/ink_cuda_backend.cu:118-125`; CLI parsing: `engine/src/inkling2/ink_main.cpp:895-905`）。

## 実行時の詳細

backend の `init` ごとに環境から読み、`spec_cfg_.log` メンバーへ保存する。関数内 static cache ではないが、各 speculative step で環境を再読もしないため、初期化後の環境変更はその backend インスタンスの値に反映されない。子プロセスへの転送・上書き処理はこの変数について見つからない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:117-126,1201-1207`）。

融合型 greedy step は beam tree の生成、verify、accepted path の commit を行った後、`spec_cfg_.log` が真なら static カウンターを更新する。200 回目と以降 200 回ごとに、累積 `steps`、平均 `tr.M`、平均予測 token 数、平均実出力 token 数、および `tr.M == 1` の回数を出力する。カウンターは関数内 static でプロセス内に保持され、`init` の再実行ではリセットされない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1073-1119`）。

## ログと測定値

有効で、上記の処理を少なくとも 200 回通過すると stderr に次の形式で出る（文字列は実装どおり）。200 回未満では出力しない。

```text
[SPEC-STATS] steps=%ld mean_M=%.2f mean_pred_tokens=%.2f mean_actual_tokens=%.2f plain_steps=%ld
```

`steps` は統計更新された呼び出しの累計、`mean_M` は speculative tree の `tr.M` の平均、`mean_pred_tokens` は `dspark_->last_pred_etok` の平均、`mean_actual_tokens` は `n_emit` の平均、`plain_steps` は `tr.M == 1` だった累計。これは Strata の実行時統計であり、性能測定値そのものではない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1115-1119`）。

## 根拠

- 全ソース参照と読み取り: `engine/src/inkling2/cuda/ink_cuda_backend.cu:125`。候補一覧の機械生成メタデータにも同じ読み取り位置が記録されているが、挙動の根拠にはソースを用いた（`terminal/data/settings-register.json:17453-17463`）。
- 値の保存と初期化時期: `engine/src/inkling2/cuda/ink_cuda_backend.cu:117-126,1201-1207`。
- 統計対象の処理・出力: `engine/src/inkling2/cuda/ink_cuda_backend.cu:1057-1119`。
- serve 側の経路条件: `engine/src/inkling2/ink_serve.h:507-514,876-890`。
- CLI / backend 選択: `engine/src/inkling2/ink_main.cpp:198-207,895-905`; `engine/src/inkling2/ink_backend.h:198-210`。
- `docs/DETAILS.md` を含む Strata の docs に、この環境変数名または `[SPEC-STATS]` の説明は見つからなかった。
