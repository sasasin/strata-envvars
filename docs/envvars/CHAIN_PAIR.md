# `CHAIN_PAIR`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この変数は、Metal の開発・計測用プログラム `metal/tests/token_chain.cpp` で、共有 expert の gate と up の GEMV、および SwiGLU を一つの `gemv_pair` dispatch にまとめる分岐を選びます。Strata の通常の Metal engine (`metal/src/engine/`) が読む設定ではなく、通常利用者向けの engine 設定ではありません。

## 値と判定

コードは `std::getenv("CHAIN_PAIR")` の結果をポインタとして判定します。文字列や数値への変換はありません。

| 状態 | `--fuse` 指定時 | `--fuse` なし |
|---|---|---|
| 未設定 | pair 分岐を使わない | pair 分岐を使わない |
| 空文字を含む任意の設定値 | pair 分岐を使う | pair 分岐を使わない |

設定値の内容、大文字小文字、数値としての妥当性は検査されません。`0` や `false` も、変数が設定されていれば真として扱われます。環境変数を読むのはモデルの各 layer を組み立てるループ内であり、結果を static cache するコードはありません。

## 有効になる条件

- `token_chain` を実行すること。参照箇所は `metal/tests/token_chain.cpp` に限られ、通常の Metal engine の実装ではありません。
- コマンドラインに `--fuse` を指定すること。この引数がないと `CHAIN_PAIR` が設定されていても分岐は無効です。
- pair 分岐は各 layer の共有 expert 部分にあります。`--only` や `--skip` などでその処理を通らない実行では効果がありません。

CLI 側で `CHAIN_PAIR` を上書きする処理は見つかりません。ソースから確認できる範囲では、親プロセスから渡された環境値がそのまま参照されます。

## 実行時の詳細

pair 分岐では `ffn_gate_shexp.weight` と `ffn_up_shexp.weight` の tensor type から `gemv_pair_<gate type>_<up type>` という pipeline 名を作り、両 tensor と対応する activation を一つの dispatch に渡します。kernel は gate と up の内積を計算し、`silu(gate) * up` の raw activation を出力します。通常分岐では同じ二つの重みについて `gemv2()` を別々に呼びます。その後の `ffn_gate_inp_shexp.weight` などの処理は両分岐に共通です。

コードコメントには pair 方式が `+0.11 ms` 遅かったため opt-in とあります。ただし、このコメントは測定機器・GPU・モデル・設定などの条件を示していないため、ここでは特定条件の確認済み測定値として扱いません。調査では build、実行、性能測定をしていません。

## 根拠

- `metal/tests/token_chain.cpp:66-82` — 他の harness 設定の読み取りと、`--fuse` 引数の処理。
- `metal/tests/token_chain.cpp:395-397,495-523` — layer ループ内での環境変数判定、pair pipeline の選択、通常時の二つの GEMV。
- `metal/kernels/gemv.metal:103-105,107-152,155-158` — pair kernel の計算と、pipeline 名を公開する型の組み合わせ。
- `metal/tests/token_chain.cpp:646-658` — harness が組み立てた dispatch 列を実行して decode-step 時間を表示する箇所。

全リポジトリの `CHAIN_PAIR` 完全一致検索では読み取りは上記一箇所だけでした。`metal/tests/token_chain.cpp` のヘッダー（`metal/tests/token_chain.cpp:1-8`）も、このプログラムを実 GGUF 上で Metal kernel 群を通して計測する harness と説明しています。
