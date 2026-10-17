# `CHAIN_PAIR`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`CHAIN_PAIR` は、Metal の `metal/tests/token_chain.cpp` にある `token_chain` 診断プログラムで、共有 expert の gate・up GEMV と SwiGLU を一つの `gemv_pair` dispatch にまとめる経路を選ぶためのフックです。Strata の通常の実行エンジンには参照がなく、通常利用者向けの設定として確認できる実装ではありません。

このテストプログラムは GGUF の実重みを読み、合成 activation を使って Metal decode step の処理時間を測るものです。ファイル先頭の説明も「数値検査ではなく timing」としています（`metal/tests/token_chain.cpp:1-8`）。

## 値と判定

| 状態 | `pair` の結果 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む任意の設定値 | 有効。ただし `--fuse` も必要 |

判定は `std::getenv("CHAIN_PAIR")` が null かどうかだけです。文字列の内容、数値形式、大文字小文字は調べず、`CHAIN_PAIR=0` や空文字でも設定されていれば真になります。`fuse` は起動引数 `--fuse` でのみ有効になります。したがって `CHAIN_PAIR` だけを設定しても pair 経路には入りません（`metal/tests/token_chain.cpp:68-82,501`）。

## 有効になる条件

- 対象は Metal の `token_chain` テストプログラムです。Strata の通常実行ファイル側での参照は確認できません。
- `token_chain` 起動時に `--fuse` が指定されている必要があります。未指定なら環境変数が設定されていても `pair` は false です。
- `pair` が true の場合は、共有 expert の gate/up の通常 GEMV 2回を `gemv_pair_<gate tensor type>_<up tensor type>` という pipeline の1 dispatch に置き換えます。
- 無効の場合は gate と up をそれぞれ `gemv2` で処理します。

## 実行時の詳細

環境変数は `main` の decode 処理中、MoE の各 layer に達した箇所で読み直されます。値は `static` 変数に保存されていません。そこで `fuse && getenv(...)` を評価し、真なら pair kernel 用の pipeline を取得し、重みと activation 等を渡す dispatch を構成して `shared` 区分として投入します。偽なら gate と up を別々の `gemv2` 呼び出しで投入します（`metal/tests/token_chain.cpp:495-523`）。

この分岐自体による専用ログやエラー文は見つかりませんでした。ソースの同じ行には `measured slower (+0.11 ms)` というコメントがありますが、比較条件や測定環境はそこに記載されていないため、この文書では性能値を一般的な結果として扱いません（`metal/tests/token_chain.cpp:501`）。

## 根拠

- `metal/tests/token_chain.cpp:1-8`: `token_chain` の目的と timing 用である旨。
- `metal/tests/token_chain.cpp:68-82`: `fuse` の既定値と `--fuse` による設定。
- `metal/tests/token_chain.cpp:495-523`: `CHAIN_PAIR` 判定、pair dispatch と通常経路。
- 調査対象リポジトリ全体で `CHAIN_PAIR` の直接参照は上記1箇所のみでした。`docs/DETAILS.md` および `metal/` 外の通常実行コードに、この環境変数の説明・参照は見つかりませんでした。
