# `strata --prompt-cache-every`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（root parser） |
| 値 | `N`（prompt token 数） |
| 既定値 | `16384` |
| 主な実装 | `engine/src/program/generate.cpp`、`engine/sycl/src/program/generate.cpp` |

## 役割

`--serve` 中に、新規に読み込んだ prompt の途中状態を会話チェックポイントとして定期保存する間隔を指定します。チェックポイントがあれば、後続リクエストで会話履歴の一致する位置から再利用できます。値は「prompt を N token ごとの断片に分ける」指定ではなく、既存の batched prefill が到達した chunk 境界で状態を保存する cadence です。

## 使い方

```sh
# サーバーモードで、再開地点から新たに読んだ prompt を約 16384 token 間隔で保存する
strata --serve --pack <pack> --prompt-cache 6 --prompt-cache-every 16384

# 定期チェックポイントを無効にする（会話末尾など他のチェックポイント設定は別途適用）
strata --serve --pack <pack> --prompt-cache-every 0
```

## 値と既定値

- `N` は整数として `std::atoll` で変換され、負数は `std::max(0, ...)` により `0` に補正されます。明示的な上限値や厳密な文字列全体の検証はこの parser にありません。非数値文字列は `atoll` の変換結果に従い、通常 `0` として扱われます。
- 未指定時は `16384` です。`0` は周期チェックポイントを無効にします。
- 複数回指定した場合、parser は出現順に値を代入するため最後の指定が残ります。
- 値を省略すると `--prompt-cache-every needs a value` を stderr に出してプロセスを終了コード `2` で終了します。

## 実行時の動作

- この設定は `--serve` 向けです。各 parser は `prompt_cache_every` を `16384` で初期化し、serve の prompt 読み込み callback が `N > 0` かつ読み込み位置が次の目標以上になった場合に周期 checkpoint を試みます（CUDA/HIP: `engine/src/program/generate.cpp:1124-1125,14818-14827`、SYCL: `engine/sycl/src/program/generate.cpp:742-743,8645-8652`）。通常の非 serve 実行にはこの serve callback 経路がありません。
- 周期はリクエストが再開した位置（再利用した prefix の末尾）を起点にします。CUDA/HIP は `anchor + k*N` の格子点を計算し、その点以降で最初に到達した chunk 末尾に保存します。1 chunk が複数格子点をまたいでも、その境界で保存する checkpoint は1つです（`engine/include/strata/core/prompt_checkpoint_grid.hpp:11-23`）。SYCL 側も `resume + N` から開始し、実際の prefill chunk 境界で判定します（`engine/sycl/src/program/generate.cpp:11119-11126,8640-8652`）。したがって、実際の保存間隔や位置は chunk 境界に依存します。
- `--prompt-cache` が `0` 以下の場合は checkpoint 保存処理が何もせず戻るため、この値を正にしても途中 checkpoint は保存されません（`engine/src/program/generate.cpp:14595-14598`）。また serve request の `ckpt=0` 指定では `pp_next_check` が無効位置になり、その request は周期・tail checkpoint を作りません（`engine/src/program/generate.cpp:18841-18845,20212-20214`）。
- 保存に成功した checkpoint は `--prompt-cache` の件数上限に含まれ、上限超過時に既存 checkpoint が退避されます。退避の選択は `--prompt-cache-spread` の有無で変わります（`engine/src/program/generate.cpp:14723-14753`）。このため cadence を小さくすると保存候補が増えますが、保持件数自体は増えません。
- `--prompt-cache-tail` は別の追加 checkpoint です。`--prompt-cache > 0`、`--prompt-cache-every > 0`、単一 GPU などの条件を満たすと、既存の chunk 境界のうち prompt 末尾近くで追加保存を試みます。これは prefill の chunk 分割を変更せず、周期 checkpoint と同じ保存上限を共有します（`engine/src/program/generate.cpp:14820-14827,14712-14723`）。

## 適用条件と副作用

- 適用先は `strata-engine` の root parser です。CUDA/HIP 実装と SYCL 実装に同名引数があります（parser: `engine/src/program/generate.cpp:4113`、`engine/sycl/src/program/generate.cpp:2091`）。索引上の Qwen3.6 専用 `qwen36/` scope とは別です（`docs/cli/README.md:1038-1041,1183-1185,1240-1244`）。
- checkpoint 作成では各 GPU の状態同期と状態コピーが行われます。GPU が停止応答するなど保存を継続できない場合は request が失敗します。一方、状態のコピーだけが失敗し回復可能と判定された場合、その checkpoint を stderr に「skipped」と出して request を続行します（`engine/src/program/generate.cpp:14587-14592,14688-14699,14843-14853`）。
- checkpoint 保存は RAM を使い、チェックポイント上限を超えれば古い候補が退避されます。保存にかかる時間やメモリ量、適切な間隔はモデル・状態・実行環境依存であり、このソース調査だけでは定量化できません。

## 出力とエラー

- `--prompt-cache-every` 自体に成功時の専用出力はありません。保存に失敗して回復可能な場合は stderr に `strata serve: checkpoint at ... skipped: its state could not be copied out ...; the request goes on without it` が出ます（`engine/src/program/generate.cpp:14843-14853`）。回復不能な失敗は request のエラー経路へ進みます（`engine/src/program/generate.cpp:14843-14847,21593-21604`）。
- 引数欠落時の stderr と終了コードは「値と既定値」を参照してください。負数・非数値を拒否する専用 validation メッセージはありません。

## 根拠

- `engine/src/program/generate.cpp:1124-1126,1329-1331,4111-4114` — 既定値、help 記述、parser の変換と関連 option。
- `engine/src/program/generate.cpp:3842-3847,4113` — 値の取得、引数欠落時のエラーと終了。
- `engine/src/program/generate.cpp:14595-14607,14723-14753,14818-14853,20212-20214` — checkpoint の保存・上限・失敗処理、周期開始位置と `ckpt=0`。
- `engine/sycl/src/program/generate.cpp:742-744,909-911,2091,8645-8679,11119-11130` — SYCL parser、既定値、適用条件と失敗時の継続処理。
- `engine/include/strata/core/prompt_checkpoint_grid.hpp:11-23` — CUDA/HIP の再開位置起点の grid と chunk 境界規則。
