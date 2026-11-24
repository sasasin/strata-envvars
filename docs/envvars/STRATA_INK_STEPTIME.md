# `STRATA_INK_STEPTIME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 の CUDA backend において、`forward_batch_impl` の処理をホスト側の step 間時間・step 呼び出し wall time・一部経路の GPU event 時間として集計し、100 回ごとに stderr へ出す診断スイッチです。モデル計算や CUDA Graph の選択を切り替える分岐はこの変数の処理にはありません。実装は `InkCudaBackend::forward_batch_impl` 内のローカル `StepTimeGuard` です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:697-749`）。このファイルは `strata_inkling_cuda` CUDA plugin のソースとして登録されています（`engine/src/inkling2/cuda/CMakeLists.txt:56-65`）。

## 値と判定

`std::getenv` の戻り値が null でなく、かつ先頭 1 byte が ASCII `'1'` の場合だけ ON です。文字列全体の parse や数値変換はしません。したがって `1`、`10`、`1anything` は ON、未設定・空文字・`0`・`true`・` 1` は OFF です。大文字小文字や空白を正規化しません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:712-714`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA Inkling backend の `forward_batch_impl` | OFF | `1`, `10`, `1anything` | 空文字、`0`, `true`, ` 1` |

CLI 引数、設定値、別環境変数との優先順位や上書きは実装されていません。このフックは対象環境変数だけで有効判定します（同:713-719）。

## 有効になる条件

- 実行バイナリに Inkling-2 CUDA plugin が含まれ、その `forward_batch_impl` が呼ばれること。HIP・SYCL・Metal・CPU の同名読み取りは見つかりません（`engine/src/inkling2/cuda/CMakeLists.txt:56-65`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:697-719`）。
- `N == 1` の呼び出しであること。`N <= 0` は計測ガード生成前に正常 return し、`N > 1` は環境変数が ON でも guard が非作動です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:707-720`）。
- 実行中の値変更は反映されません。初めて `StepTimeGuard::on()` が評価されたときの結果を関数内 `static const bool` に保持します。同関数では `N <= 0` の早期 return 後に評価するため、最初の `N > 0` の呼び出しで固定されます（同:707-719）。
- `forward_batch_impl` は通常の `forward_batch` と候補行用 `forward_batch_cand` の双方から呼ばれます。サーバーでは候補行を使えない場合や要求 slot が penalty を使う場合に通常経路へ切り替わります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:673-695`; `engine/src/inkling2/ink_serve.h:1063-1081`）。GPU span の終点 event は候補行経路で `nw == 1` のときだけ記録されるため、通常の logits 経路では wall/host 集計が進んでも GPU 集計 `n` は増えません（`engine/src/inkling2/cuda/ink_cuda_backend.cu:807-812`）。

## 実行時の詳細

`forward_batch_impl` の先頭で、`N > 0` のときに static `steptime_e1` を必要に応じて作成し、guard を構築します。作成時に host clock を取り、同じ CUDA stream に開始 event を記録します。guard が作動するのは `on() && N_ == 1` です。関数終了時に、前回の計測完了から現在の開始までを「host between steps」、開始から終了までを「step call wall」として累積します。100 回ごとに stderr に平均値を出し、3 つの累積値と step 数をゼロに戻します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:712-749`）。

GPU span は開始 event から終点 event までを `cudaEventElapsedTime` で取得できた場合だけ累積します。終点は候補行の top-K 処理後、stream 同期の直前です。よってこの値は全 `N == 1` 呼び出しの GPU 全処理を常に表すものではなく、終点 event が記録された候補行ケースの値です。出力の `n` は成功した GPU event 経過時間のサンプル数です（同:734-743, 807-812）。

ガードは測定と stderr 出力だけを行い、入力・logits・サンプリング結果を変更しません。変数専用の timeout、終了処理、失敗 fallback はありません。`cudaEventCreate` と `cudaEventRecord` の戻り値はこの診断コード内で検査されず、`cudaEventElapsedTime` が `cudaSuccess` でない場合は GPU サンプルを加算しません（同:721-726, 734-737, 747-749）。

## ログと測定値

作動した one-token 呼び出しを 100 回数えるごとに stderr に次の形式で出力します（実装の文字列は `engine/src/inkling2/cuda/ink_cuda_backend.cu:740-743`）。

```text
[InkCUDA STEPTIME] %ld one-token steps: host between steps %.3f ms, step call wall %.3f ms, GPU span of the call %.3f ms (n=%ld)
```

これは実行時の集計ログで、Strata 文書に記載された固定の性能測定値ではありません。未設定または先頭文字が `'1'` でない値では診断ログを出しません。`N != 1` の呼び出しも回数に含まれません。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:697-749` — 判定、cache、guard、計測集計、stderr 出力
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:807-812` — GPU event 終点を記録する候補行経路
- `engine/src/inkling2/cuda/CMakeLists.txt:56-65` — CUDA backend plugin のソースと target
- `engine/src/inkling2/ink_serve.h:1063-1081` — サーバーでの候補行／全 logits 経路選択
