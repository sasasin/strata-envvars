# `STRATA_OLD_SAMPLER`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

確率的サンプリングで使用する GPU sampler の実装を、旧 `sampler_kernel` に切り替えます。CUDA と SYCL の実装にあり、どちらも通常の sampled path でこの変数を優先して判定します。旧 kernel は engine 0.1.20 の参照実装として残されており、未設定時の通常経路は split top-k sampler です。

greedy（`p.greedy` または `temperature <= 0`）では sampled path の判定より先に greedy kernel を実行するため、この変数は影響しません。GPU backend の sampler 内の選択であり、サーバー設定や CLI の設定値を変更する変数ではありません。

## 値と判定

値は `getenv()` で読み、共通の `env_flag()` は次の条件で真偽を決めます。文字列全体を数値として parse する処理ではありません。

| 環境変数の状態 | 判定 | sampler path |
|---|---:|---|
| 未設定 | false | `STRATA_SAMPLER_ONE_BLOCK` の判定へ進む。そちらも false なら Split |
| 空文字 | false | 同上 |
| 値がちょうど `0` | false | 同上 |
| その他（例: `1`, `00`, `0x`, `false`, 空白） | true | Old (`sampler_kernel`) |

大文字小文字や空白の trim は行いません。たとえば `false` は文字列として false と解釈されず、Old を選びます。一方 `00` は `0` との完全一致ではないため Old です。

## 有効になる条件

- 確率的サンプリング経路であること。greedy 経路はこの変数を参照せず、従来の greedy kernel を使います。
- CUDA build では `src/kernels/cuda/sampler.cu`、SYCL build では `sycl/src/kernels/cuda/sampler.dp.cpp` に同じ判定と Old path があります。
- `STRATA_OLD_SAMPLER` が真なら `STRATA_SAMPLER_ONE_BLOCK` より優先されます。Old が選ばれた場合、split scratch の利用可否や stream capture を調べる split/one-block 分岐には入りません。
- `sample_tokens_spec()` は Split 以外の path で `false` を返します。その呼び出し元の verifier は `judged == false` の場合に通常の `sample_tokens()` を呼び、そこで Old path が使われます。

## 実行時の詳細

`sampled_path()` 内の function-local `static const SampledPath` として判定結果を一度だけ保存します。したがって最初に sampled path を評価した後でプロセスの環境を書き換えても、そのプロセス内では再評価されません。greedy のみを実行する間は `sampled_path()` が呼ばれないため、初回評価は後の sampled request まで遅れることがあります。

Old path は各 token row に対して `sampler_kernel` を起動します。kernel は penalty を適用しながら top-k 候補を選び、その候補に top-p、min-p、temperature、乱数による pick を適用します。新しい split / one-block 実装に比べ、旧 kernel には候補選択の `taken` sweep と全 1,024 thread で行う double precision の tail 処理が残る、とソースコメントは説明しています。コメントは実装上の差の説明であり、ここでは条件一般での性能値を示しません。

## 根拠

- 環境値の判定と優先順位、static cache: `src/kernels/cuda/sampler.cu:1102-1120`。SYCL 側にも同じ実装: `sycl/src/kernels/cuda/sampler.dp.cpp:1289-1303`。
- greedy では別経路、Old path では旧 kernel を起動: `src/kernels/cuda/sampler.cu:1239-1298`。SYCL 側の分岐: `sycl/src/kernels/cuda/sampler.dp.cpp:1471-1575`。
- 旧 kernel の候補選択、top-p/min-p/temperature/pick 処理とコメント上の実装差: `src/kernels/cuda/sampler.cu:292-435`。
- spec sampling が Split 以外で拒否される: `src/kernels/cuda/sampler.cu:1347-1357`。拒否後に通常 sampler へ進む verifier: `src/core/verify.cpp:2329-2337`。
- `docs/DETAILS.md` にはこの環境変数の利用者向け説明は見当たりません。ここでの説明は対象 HEAD の sampler 実装と呼び出し元に基づきます。
