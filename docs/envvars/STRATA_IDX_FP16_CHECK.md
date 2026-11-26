# `STRATA_IDX_FP16_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA prefill の診断用スイッチ。設定すると、通常の FP32 pooled indexer keys と `dead` で行った cell 選択に加え、それらを FP16 に丸めて FP32 に戻した値でも選択を再計算し、両方の選択がどれだけ一致するかを stderr に累積表示する。元の選択 `m.sel_ids` は置き換えず、後続 attention は元の選択を使うため、これは KV/indexer の保存形式や生成結果を FP16 に切り替える設定ではない。CUDA/HIP 側は `engine/src/prefill/prefill.cpp`、SYCL 側は `engine/sycl/src/prefill/prefill.cpp` の QSA chunk prefill に実装されている。比較用の FP16 丸めは FP16 へ変換して FP32 に戻す処理である（CUDA/HIP: `engine/src/prefill/kernels.cu:2649-2652`、SYCL: `engine/sycl/src/prefill/kernels.dp.cpp:2180-2192`）。

## 値と判定

両実装とも `static const bool f16chk = std::getenv("STRATA_IDX_FP16_CHECK") != nullptr` で設定有無だけを判定し、数値・文字列の parse はしない（CUDA/HIP: `engine/src/prefill/prefill.cpp:5464`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3753`）。

| 条件（build / backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP QSA chunk prefill | 診断を実行しない | 空文字列、`0`、`1`、`true`、`false`、空白や任意の文字列を含む、設定済みのすべての値 | なし（環境変数が存在する限り有効） |
| SYCL QSA prefill | 診断を実行しない | 空文字列、`0`、`1`、`true`、`false`、空白や任意の文字列を含む、設定済みのすべての値 | なし（環境変数が存在する限り有効） |
| Metal / CPU の経路 | この診断コードを通らない | なし | 値にかかわらずこの実装では動かない |

`0`、`false`、空文字列も「設定済み」なので有効であり、無効文字列や範囲外値という概念はない。CLI 引数、設定ファイル、他の環境変数による値の上書き・優先順位は実装されていない（同上）。

## 有効になる条件

- QSA 層を含むモデルの prefill が実行され、この診断ブロックを含む QSA chunk 処理まで到達する必要がある。ブロックは `st.idx_pooled` と `st.idx_dead` を使って通常選択を行った直後に置かれている（CUDA/HIP: `engine/src/prefill/prefill.cpp:5325-5348,5387-5392,5460-5465`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3647-3660,3713-3719,3749-3753`）。
- CUDA/HIP では `Prefill::run` が layer-major 経路を選ぶと `run_layer_major` を呼んで戻るため、この `run_impl` 内の診断を通らない（`engine/src/prefill/prefill.cpp:9657-9692`）。同ファイルの multi-prompt layer-major 処理にも診断ブロックはない（`engine/src/prefill/prefill.cpp:8413-8432,8435`）。
- Metal は `Prefill::run` から `strata::metal_engine::prompt_run` に委譲して戻るため、この診断ブロックを通らない（`engine/src/prefill/prefill.cpp:9633-9650`）。この環境変数を読む箇所は CPU 実装には見つからなかった。
- SYCL は `Prefill::run` から `run_impl` を呼ぶ構成であり、QSA prefill で条件に到達すれば診断を実行する（`engine/sycl/src/prefill/prefill.cpp:5959-5972`）。
- このスイッチを有効化するための GPU 世代、モデル量子化、CLI 引数、別の環境変数の条件分岐は診断ブロックにない。実行には該当 backend の prefill 実装が build に含まれている必要がある。

## 実行時の詳細

`f16chk` は関数内 `static` で、プロセス内で最初にこの宣言へ到達したとき一度だけ環境を読み、その後は値を cache する。したがって起動後に環境を変更しても、この判定は変わらない。unset のまま最初に到達すれば、そのプロセスでは以後も無効である（CUDA/HIP: `engine/src/prefill/prefill.cpp:5464`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3753`）。

有効時は、最初の診断実行で pooled keys、`dead`、再選択 ID 用の device buffer を確保する。確保失敗時は `err` に `STRATA_IDX_FP16_CHECK: no room for its buffers` を設定して `false` を返す（CUDA/HIP: `engine/src/prefill/prefill.cpp:5465-5475`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3754-3773`）。これらのポインターと集計カウンターも `static` であり、後続の chunk で共有・再利用される。コードは buffer を再確保・拡張せず、プロセス中に解放する処理もこのブロックにはない（同上）。

各 QSA 層で pooled keys と `dead` を FP16 丸めしてから FP32 に戻し、同じ indexer query、step、score/top-k 処理で別の ID 配列を作る。通常選択と再選択の ID を host にコピーして stream/queue を同期し、各 query の選択幅 `w` に対する共通 ID 数 `c` を二ポインター走査で数える。`c == w` の query 数と全 query 数は累積し、`p0 + t + 1 > m.cap` の query だけについて共有 cell 数と選択 cell 数も累積する。現在の chunk の最終 QSA 層で累積値を出力する（CUDA/HIP: `engine/src/prefill/prefill.cpp:5477-5505`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3775-3818`）。

## ログと測定値

有効時、各 chunk の最終 QSA 層で stderr に次の書式を出す。値はプロセス内でリセットされない累積値である。

```text
strata prefill: FP16 indexer keys: %lld of %lld selections identical; where the selection is sparse, %.4f%% of cells shared (%lld queries)
```

「selections identical」は query ごとに共通 ID 数がその選択幅 `w` と等しい件数。「where the selection is sparse」の割合は `p0 + t + 1 > m.cap` の query 群における、共通 ID 数の合計 / 選択 cell 数の合計である。該当する query の選択 cell が一つもなければ表示上は `100.0000%` になる（CUDA/HIP: `engine/src/prefill/prefill.cpp:5491-5505`、SYCL: `engine/sycl/src/prefill/prefill.cpp:3803-3818`）。

CUDA/HIP は比較の host copy 後に `cudaStreamSynchronize`、SYCL は copy 後に queue の `wait` を呼ぶため、診断有効時は各 QSA 層の比較で同期が入る（`engine/src/prefill/prefill.cpp:5487-5490`、`engine/sycl/src/prefill/prefill.cpp:3793-3802`）。この文書化された出力は診断統計であり、性能測定値や通常選択を変更した結果ではない。明示的な buffer 確保エラーは `err` 経由で返り、`Prefill::run` は `run_impl` の失敗を `false` として返す（CUDA/HIP: `engine/src/prefill/prefill.cpp:9705-9713`、SYCL: `engine/sycl/src/prefill/prefill.cpp:5962-5972`）。診断箇所自体はこのエラーを stderr に印字しない。

## 根拠

- 候補名の実参照は上記 CUDA/HIP および SYCL の `std::getenv` 2 箇所。リポジトリ全体の完全一致検索では、その他のソース参照はコメントと `terminal/data/settings-register.json` の設定登録だけで、別の env helper 経由の読み取りは確認されなかった。
- CUDA/HIP の値判定・比較・統計: `engine/src/prefill/prefill.cpp:5460-5505`。
- SYCL の値判定・比較・統計: `engine/sycl/src/prefill/prefill.cpp:3749-3818`。
- FP16 丸め: `engine/src/prefill/kernels.cu:2649-2652`、`engine/sycl/src/prefill/kernels.dp.cpp:2180-2192`。
- CUDA/HIP の経路選択と失敗伝播: `engine/src/prefill/prefill.cpp:9633-9650,9657-9692,9705-9713`。
- SYCL の呼び出しと失敗伝播: `engine/sycl/src/prefill/prefill.cpp:5959-5972`。
- 関連資料 `docs/DETAILS.md:253` は `--kv-streaming` を説明しているが、この診断スイッチや FP16 indexer 比較の結果・測定値は記載していない。
