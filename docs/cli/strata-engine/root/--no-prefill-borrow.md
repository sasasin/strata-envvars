# `strata --no-prefill-borrow`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数） |
| オプション | `--no-prefill-borrow` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

prompt の prefill 用バッファを expert cache のスロットから一時的に借りず、独立したバッファとして確保するよう指定します。通常、借用方式では prompt 処理中に cache の一部をバッファとして使い、処理後にスロットを戻します。このフラグを有効にすると、その借用経路を選ばず、cache の容量見積りでも prefill バッファ用の VRAM を別枠として扱います（`engine/src/program/generate.cpp:1000-1002,6817-6832,23990-23994`; `engine/sycl/src/program/generate.cpp:648-650,3847-3860,13312-13316`）。

## 使い方

```sh
# ローカルの pack と token 列で推論し、prefill 用 cache slot の借用を無効にする
strata --pack ./pack --tokens "1,2,3" --no-prefill-borrow
```

`--pack` と `--tokens` は例の入力を成立させるための引数です。フラグ自体に値は付けません（`engine/src/program/generate.cpp:3842-3847,3850-3855,4033-4036`）。

## 値と既定値

フラグなので値の形式や数値範囲はありません。CUDA/HIP 側 parser では `Options::no_prefill_borrow` の初期値は `false` で、指定時に `true` になります。同じフラグを複数回書いても、毎回 `true` を代入するだけです（`engine/src/program/generate.cpp:1001-1002,4035`）。

SYCL parser も初期値は `false` ですが、`--no-prefill-borrow` と `--prefill-borrow` はどちらも `borrow_explicit` を立て、引数を処理した順に値を設定します。そのため同じ起動引数内で両方を指定した場合は後に現れた方が残ります（`engine/sycl/src/program/generate.cpp:648-650,1879,2030-2031`）。

## 実行時の動作

prefill chunk が有効で prompt が複数 token のとき、借用フラグが無効で、さらに host residency と device residency がある場合に限って借用計画を作ります。このフラグを指定するとその条件が偽になり、cache slot の借用を開始しません。借用しないときは prefill バッファを独立して確保し、実際にその経路へ入った場合は標準エラーに `prompt path allocates its own buffers (no cache slots to borrow)` と出ます（`engine/src/program/generate.cpp:23990-23994,24115-24121`; `engine/sycl/src/program/generate.cpp:13312-13316,13331-13333,13352-13358`）。

独立バッファの容量は VRAM 予算に影響します。自動 expert-cache サイズ決定では、借用しない場合の prefill 用容量を cache の外に見積もります。通常の概算式は `160 + chunk * 680 / 1024` MiB で、`STRATA_OWNED_PRICE=exact` の場合は実バッファ量を見積もって余裕分を加えます（`engine/src/program/generate.cpp:9063-9070`; `engine/sycl/src/program/generate.cpp:4842-4849`）。

`--prefill auto` と併用した場合、借用なし（または expert profile なし）の一般経路では auto を解除して chunk を 2048 にします。CUDA/HIP の Windows gfx1151 用規則が既に選んだ chunk を保持する例外があります。数値を明示する `--prefill N` はこの auto 縮小規則の対象ではありません（`engine/src/program/generate.cpp:4990-4995`; `engine/sycl/src/program/generate.cpp:2500-2503`）。

## 適用条件と副作用

- CUDA/HIP parser では、通常の既定値は借用可能な状態（`false`）です。ただし Windows の gfx1151 では `STRATA_PREFILL_BORROW=1` でない限り、実行時の機種別規則が `no_prefill_borrow` を有効にします（`engine/src/program/generate.cpp:4400-4405`）。
- SYCL では、明示的な借用指定がない場合に限り、通常は context が 32K 以下なら独立バッファ、32K を超えるなら借用を選びます。十分な global memory を持つ Intel Alchemist では、単一 GPU の自動選択は独立バッファにし、auto chunk も最大 2048 に抑えます。明示した `--no-prefill-borrow` はこれらの自動選択に優先します（`engine/sycl/src/program/generate.cpp:2459-2483`）。
- layer split 時の `STRATA_SPLIT_OWN` による自動的な独立バッファ選択は、このフラグが未指定相当の場合だけ評価されます。指定時はその環境変数の自動選択分岐に入りません（`engine/src/program/generate.cpp:4921-4948`; `engine/sycl/src/program/generate.cpp:2380-2414`）。
- 借用方式が利用可能な条件を外すため、prefill バッファ分の VRAM を cache と別に必要とします。実際に確保できる量や起動可否は GPU と実行時の空き容量に依存します。

`STRATA_PREFILL_ALWAYS_BORROW` は、通常の借用候補が成立した後に借用を維持するための環境変数です。このフラグ指定時は候補計算側で借用しないため、その環境変数だけで本フラグを打ち消すことはできません（[STRATA_PREFILL_ALWAYS_BORROW](../../../envvars/STRATA_PREFILL_ALWAYS_BORROW.md)、`engine/src/program/generate.cpp:4035,23993`; envvar 文書の現行コード参照は同 `generate.cpp:23884-23890,23970-23989`）。

## 出力とエラー

このオプション自体に値検証や専用の拒否経路はありません。独立バッファ経路で `prefill.init` が失敗すると、エラー文字列を標準エラーに出し、終了コード `1` で戻ります。失敗内容は実行時の割当・初期化条件に依存し、このオプション単独が必ず失敗を起こすとはソースから言えません（`engine/src/program/generate.cpp:24115-24122`; `engine/sycl/src/program/generate.cpp:13352-13359`）。

## 根拠

- `engine/src/program/generate.cpp:1000-1002,4033-4036` — CUDA/HIP 側のフラグ状態と parser。
- `engine/src/program/generate.cpp:4921-4948,4990-4995,6817-6832` — split 時の環境変数条件、auto chunk の調整、cache 予算上の扱い。
- `engine/src/program/generate.cpp:23990-23994,24115-24122` — 通常 prompt 経路の借用条件、独立バッファのログと初期化失敗経路。
- `engine/sycl/src/program/generate.cpp:1879,2029-2032,2459-2503` — SYCL の明示指定、両フラグの順序、機種・context による既定値。
- `engine/sycl/src/program/generate.cpp:3847-3860,13312-13316,13352-13359` — SYCL の cache 予算、借用条件と独立バッファ初期化。
