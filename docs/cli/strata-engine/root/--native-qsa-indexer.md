# `strata generate --native-qsa-indexer`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--native-qsa-indexer` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると内部スイッチを `true` にする |

## 役割

QSA 層の indexer key append で、通常の `indexer_key_append` に代えて実験的な native indexer 実装を選びます。CUDA 実装では、raw key を F16 に丸めてから F32 に展開し、4 cell 単位の pooling、重み付き RMSNorm、RoPE を行って indexer の pooled key と tail 状態を更新します。単一 token の QSA 層処理で切替に使われ、verify window が利用可能かを判定する条件にも含まれます。CUDA parser と SYCL parser の両方がこのフラグを受け付けますが、実行時の詳細はビルド backend の実装に依存します。`--native SHARD1` を使う経路では、このスイッチも自動で有効になります。

## 使い方

```sh
# token ID を入力して generate を実行し、native QSA indexer を有効にする
strata generate --pack pack/full --tokens "1,2,3" --native-qsa-indexer
```

## 値と既定値

- 値は不要です。parser はフラグを見つけると `o.native_qsa_indexer = true` とし、値の型変換やフラグ固有の引数検証は行いません（`engine/src/program/generate.cpp:3919-3921`）。
- `Options` の初期値は `false` です（`engine/src/program/generate.cpp:785-787`）。同じフラグを複数回指定しても代入が繰り返されるだけです。
- 未知の引数は `unknown argument` を stderr に出し、usage を表示して終了コード 2 で戻ります（`engine/src/program/generate.cpp:4268-4273`）。

## 実行時の動作

- 起動時に内部スイッチの値を native kernel の設定へ渡します（`engine/src/program/generate.cpp:6118-6123`）。QSA 層ではスイッチが有効なら `native_qsa_indexer_append`、無効なら `indexer_key_append` を呼びます（`engine/src/core/layer.cpp:1250-1256`）。
- CUDA の native append は 128 要素の raw key を F16 丸めしてキャッシュし、4 cell block の pooling、RMSNorm と RoPE を計算して pooled key・tail・block position を更新します（`engine/src/kernels/cuda/native_qsa_indexer.cu:61-115`）。
- verify window の互換性判定は、このスイッチが無効なら「the native QSA indexer is off」として非互換にします（`engine/src/core/layer.cpp:537-546`）。
- `--native SHARD1` の処理では、他の native 経路とともに `native_qsa_indexer` も true にします（`engine/src/program/generate.cpp:5155-5164`）。
- prompt prefill の indexer append は `engine/src/prefill/prefill.cpp` から native append 関数を直接呼び、`--native-qsa-indexer` の enabled 状態で分岐していません（`engine/src/prefill/prefill.cpp:5323-5342`）。このため、この CLI フラグが prefill の batch/per-token 選択を行うとは確認できません。そこは `STRATA_INDEXER_PER_TOKEN` の有無で選ばれます。

## 適用条件と副作用

- 効果が現れるのは QSA 層の indexer append 経路です。QSA 層を持たないモデルでは、この分岐への到達をソースから確認できません。
- CUDA native append は固定 geometry（`idx_dim=128`、`idx_block=4`、`n_rot=64`）、正の容量と epsilon、位置範囲、RoPE scaling、stream、各 buffer の有効性・非重複を検査します。不適合なら `std::invalid_argument` を送出し、CUDA launch error も例外になります（`engine/src/kernels/cuda/native_qsa_indexer.cu:270-298`）。QSA 層側は例外を `native_indexer` を含むエラー文字列にして失敗を返します（`engine/src/core/layer.cpp:1250-1255`）。
- このフラグ専用のファイル出力やネットワークアクセスは、確認した parser と使用箇所にはありません。通常の generate に伴う処理への影響範囲を超える副作用は確認できませんでした。
- parser は実験的スイッチとして案内しています（`engine/src/program/generate.cpp:1250-1254`）。性能向上の有無はこの調査では測定していません。

## 根拠

- `engine/src/program/generate.cpp:785-787` — 内部 option の既定値と説明。
- `engine/src/program/generate.cpp:1250-1254`, `3919-3921` — help 表示と CUDA parser 登録。
- `engine/sycl/src/program/generate.cpp:1957-1961` — SYCL parser 登録。
- `engine/src/program/generate.cpp:5155-5164`, `6118-6123` — `--native` preset による有効化と kernel への設定。
- `engine/src/core/layer.cpp:537-546`, `1250-1256` — verify 適合条件と QSA 層での native/通常 append 分岐。
- `engine/src/kernels/cuda/native_qsa_indexer.cu:61-115`, `270-298` — CUDA native append の key 処理、検証、launch error。
- `engine/src/prefill/prefill.cpp:5323-5342` — prompt prefill の append と `STRATA_INDEXER_PER_TOKEN` による batching 分岐。

調査範囲は上記 revision の parser、QSA 層、CUDA indexer kernel、prompt prefill、および SYCL parser です。別 backend における kernel 内部の演算・性能差までは確認していません。
