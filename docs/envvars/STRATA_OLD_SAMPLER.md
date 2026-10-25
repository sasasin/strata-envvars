# `STRATA_OLD_SAMPLER`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA と SYCL の sampler で、非 greedy の通常サンプリングに使うカーネル経路を選びます。有効なら旧 `sampler_kernel` を使います。無効なら `STRATA_SAMPLER_ONE_BLOCK` が有効な場合に one-block 経路を選び、それ以外は split top-k 経路を選びます。split が実行条件を満たさない場合は one-block カーネルへ fallback します。

## 値と判定

CUDA と SYCL の各実装にある `env_flag()` が `std::getenv()` で値を読み、同じ条件を使います。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 文字列がちょうど `0` | 無効 |
| それ以外の設定値 | 有効 |

数値変換や大文字小文字の変換はありません。したがって `00`、`0 `、`false`、`TRUE` は有効です。`STRATA_OLD_SAMPLER` が有効な場合は `STRATA_SAMPLER_ONE_BLOCK` より優先されます。

選択結果 `SampledPath` は関数内の `static const` に一度だけ保存されます。最初の `sampled_path()` 評価後にプロセス環境を変更しても選択は変わりません。

## 有効になる条件

- CUDA ビルドでは `src/kernels/cuda/sampler.cu`、SYCL ビルドでは `sycl/src/kernels/cuda/sampler.dp.cpp` の sampler 実装で参照されます。
- `sample_tokens()` の greedy（`p.greedy` または `temperature <= 0`）分岐ではこの設定を見ず、greedy カーネルを使います。
- 設定が有効でも、coupled draft sampling など別の関数が常に split カーネルを直接起動する経路には適用されません。
- fused speculative verification の `sample_tokens_spec()` は sampled path が `Split` でなければ `false` を返します。呼び出し元の verifier は `false` の場合、通常の `sample_tokens()` に戻るため、この設定を有効にするとその fused 経路は使われません。

## 実行時の詳細

通常の非 greedy サンプリングで `SampledPath::Old` が選ばれると、各 token row を処理する `sampler_kernel` を起動します。無効の場合の既定 `Split` は、block 数と row 数が上限内で、stream capture 中ではなく、scratch buffer を確保できた場合に split part/merge カーネルを使います。どれかを満たさない場合は one-block カーネルに fallback します。`STRATA_SAMPLER_ONE_BLOCK` は split を明示的に選ばないための別設定で、旧経路の指定が優先されます。

実装コメントでは、旧カーネルは参照用に保持され、後続の one-block/split カーネルは同じ候補リストを同じ順序で選ぶと説明されています。この環境変数はその旧実装を選ぶものであり、ログ出力や子プロセスへの転送を行うコードは確認できません。

## 根拠

- `src/kernels/cuda/sampler.cu:1102-1121` — 経路の優先順位、env parse、static cache。
- `src/kernels/cuda/sampler.cu:278-296` — 旧カーネルの位置付けと新経路との関係。
- `src/kernels/cuda/sampler.cu:1239-1298` — greedy 分岐と旧/split/one-block の実行選択、split fallback。
- `src/kernels/cuda/sampler.cu:1347-1370` — fused speculative sampling が split のみを受け付ける条件。
- `sycl/src/kernels/cuda/sampler.dp.cpp:1289-1303,1490-1651` — SYCL 側の同等の判定と起動分岐。
- `src/core/verify.cpp:3009-3037` — speculative sampling が利用不可の場合に通常 sampler へ戻る呼び出し元。
- `docs/DETAILS.md` にこの環境変数固有の説明は見当たりませんでした。
