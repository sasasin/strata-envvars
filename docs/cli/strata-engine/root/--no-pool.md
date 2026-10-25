# `--no-pool`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--no-pool` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。指定すると有効 |

## 役割

CPU expert pool を推論経路から外すための診断・比較用フラグです。GPU 側の下限を測る目的で用意されています。通常のモデル推論では routed expert の計算を欠くため、通常設定で得るモデル出力との比較や品質評価に使うフラグではありません。parser は値なしで `no_pool` を true にします（`src/program/generate.cpp:507-508,2504-2505`）。

## 使い方

```text
strata [通常の生成引数] --no-pool
```

`[通常の生成引数]` は説明用プレースホルダーで、実行時にはモデルなど通常必要な引数を指定します。エンジンの usage はこのフラグを「CPU expert pool を飛ばす」と記載しています（`src/program/generate.cpp:967`）。

## 値と既定値

- 引数値は不要です。未指定時は `false`（pool を無効化しない）、指定時は `true` です（`src/program/generate.cpp:508,2505`）。
- 値の形式・範囲 validation や複数回指定時の専用処理はありません。parser は一致する引数を見つけるたびに true を設定します。
- SYCL 側 parser も同じフラグを値なしで受理し、既定値も false です（`sycl/src/program/generate.cpp:491,1846`）。

## 実行時の動作

- layer loop に渡す CPU pool callback と user pointer を null にし、GPU expert-cache hit callback も無効化します（`src/program/generate.cpp:6928-6933`）。したがって cache を指定していても、この条件では GPU cache hit 経路も走りません（hit 用 scratch の確保条件は `src/program/generate.cpp:6838-6848`）。
- プロンプト処理では CPU share を arm せず、単一 GPU 経路であっても prefill に CPU pool を設定しません（`src/program/generate.cpp:15702-15705,15781-15784`）。
- pool 自体の初期化・worker 数の取得はこの分岐より前に行われるため、フラグが pool worker thread の生成や初期化コストを必ずなくすとは限りません。ログにも worker 数が出て、フラグ指定時は ` (UNUSED: --no-pool)` が付加されます（`src/program/generate.cpp:6934-6936`）。
- 出力を「GPU-only floor」と呼ぶのはソース内の説明ですが、このフラグ単体が GPU 上の全処理を実行する／計測する保証ではありません。実装上は CPU expert pool と関連 hit hook を外す指定です。

## 適用条件と副作用

- `--expert-cache-remote` の CUDA0 側 slot 数が正の場合、expert profile、CUDA0 expert cache、expert pool が必要という検査にこのフラグも含まれ、stderr に理由を出して終了コード 2 で拒否します（`src/program/generate.cpp:6666-6670`）。
- `--dump-routing` と併用すると、routing ID が pool の doorbell 経由で host に届く前提を満たせないため、ファイルを開く前に stderr へエラーを出し、終了コード 2 で拒否します（`src/program/generate.cpp:6878-6880,6914-6920`）。
- `--no-capture` と併用する場合は `--no-pool` も必要です。`--no-capture` 単独では routed expert が欠落するため、逆にこのフラグがない組合せは stderr の説明とともに終了コード 2 になります（`src/program/generate.cpp:6968-6979`）。
- pool を外すため routed experts が通常どおり CPU で計算されず、GPU expert-cache hit callback も無効になります。したがって生成結果の意味が変わります。測定用途では「通常の生成結果」ではなく、pool 無効時の比較値として扱ってください（`src/program/generate.cpp:6928-6933,6970-6978`）。

## 出力とエラー

このフラグ単独に対する専用エラーや終了コード変更はありません。上記の `--expert-cache-remote`、`--dump-routing`、`--no-capture` との条件違反は stderr に診断を出して終了コード 2 になります（`src/program/generate.cpp:6667-6670,6916-6920,6974-6979`）。通常の進行時は expert-pool worker 数の stderr ログに未使用表示が付きます（`src/program/generate.cpp:6934-6936`）。

## 根拠

- 主 parser と既定値: `src/program/generate.cpp:507-508,2504-2505`。SYCL parser と既定値: `sycl/src/program/generate.cpp:491,1846`。
- 表示上の説明: `src/program/generate.cpp:967`。
- pool callback、hit callback、および未使用 worker ログ: `src/program/generate.cpp:6838-6848,6928-6936`。
- remote expert / routing dump / no-capture の制約: `src/program/generate.cpp:6666-6670,6878-6880,6914-6925,6968-6979`。
- prompt CPU pool の適用条件: `src/program/generate.cpp:15702-15705,15781-15784`。

調査範囲はこの checkout の CUDA 実装と対応する SYCL parser・主要な共通動作です。全 backend の実行結果や Release 配布物との照合は行っていません。CLI `--help` の実行、build、GPU 実行、性能測定、テストは行っていません。
