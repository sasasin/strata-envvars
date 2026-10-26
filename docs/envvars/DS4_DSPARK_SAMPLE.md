# `DS4_DSPARK_SAMPLE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSV4.1 エンジンの DSpark speculative drafter が提案 draft を greedy な argmax ではなく、drafter の出力分布からサンプリングするかを制御します。通常の token sampler の結果を変更する設定ではありません。DSpark がロードされ、speculative decoding が実行される要求で、要求の温度が正の場合にだけ有効です。

これは `strata-dsv41` のソース経路にある環境変数です。CMake では同エンジンのビルドが `STRATA_BUILD_DSV41` で選択され、CUDA または HIP のビルド領域で `src/dsv41/ds4_model.cu` が実行ファイルに含まれます。通常の共通エンジンにこの変数の読み取りはありません。

## 値と判定

`Model::Impl` のメンバー初期化で `getenv()` を調べ、設定されていれば `atoi()` の結果が 0 以外かを判定します。文字列全体との比較ではなく、C の `atoi` による整数変換です。

| 値 | `sample_drafts` |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（`atoi("")` は 0） |
| 数値変換結果が 0 | 無効（例: `0`, `0abc`, 数字で始まらない文字列） |
| 数値変換結果が 0 以外 | 有効（例: `1`, `-1`, `2abc`） |

先頭の空白や符号は `atoi` の変換規則に従い、数字列の後ろにある文字は判定に使われません。変数の判定結果は `Model::Impl` の生成時にメンバーへ保存されます。環境変数を後から変更しても、既存のモデルでは再評価されません。`Model` の公開コンストラクターはその時点で `Impl` を生成します。

## 有効になる条件

値を有効と判定しても、次の条件がそろわなければサンプリングdraftは使われません。

- DSpark の drafter が利用可能であること（`draft_block() > 0`、内部では `g.n_mtp > 0`）。ロード経路では `--dspark` の設定やモデル内の MTP/DSpark ブロックが関係します。
- decode round が speculative 経路を選ぶこと（`spec` が真で、残り生成枠 `room > 1`）。
- `draft()` に渡された要求温度が `temperature > 0.0f` であること。

温度が 0 以下なら drafter は従来どおり greedy draft を作ります。`DS4_DSPARK_SAMPLE` 自体が speculative decoding や DSpark のロードを有効にすることはありません。要求の `top_p`、`top_k`、`min_p`、seed、counter は draft sampler に渡されます。別変数 `DS4_DSPARK_QTEMP` が設定されている場合、正の倍率は要求温度に掛けられ、0 以下の倍率は 1 倍として扱われます。

## 実行時の詳細

`round()` は `spec && room > 1 && m.draft_block() > 0` のとき `Model::draft()` を呼びます。`draft()` は `drafts_q = temperature > 0.0f && sample_drafts` を設定し、真なら drafter の各位置で `sample_draft()` を使い、その位置に対応する q 分布リストも保持します。偽なら既定どおり `sample_tokens()` に greedy 設定を渡し、draft は argmax になります。

その後の `verify()` は、draft がサンプリングされた場合に保存済みの q 分布を検証器へ渡します。draft 側と検証側の sampler 条件が一致しない場合、draft token ごとの一点分布を q として使う分岐があります。検証後は `drafts_q` が false に戻ります。ソースコメントは sampled draft に speculative-sampling の受理規則を適用すると説明しています。実際の生成速度や受理率について、この変数を有効にした測定値は確認できませんでした。

この環境変数専用のログ出力はありません。値が有効でも要求温度が 0 以下の場合は、サンプリングdraftへの切り替えを示す出力はなく、greedy 経路になります。

## 根拠

- `CMakeLists.txt:800-810` — DSV4.1 ビルドオプションと `strata-dsv41` のソース構成。
- `src/dsv41/ds4_model.cu:907-916` — `sample_drafts` の保持、環境変数の `getenv` / `atoi` 判定。
- `src/dsv41/ds4_model.cu:2034-2035` — DSpark が無効なら `g.n_mtp` を 0 にし、drafter を使わない条件。
- `src/dsv41/ds4_model.cu:6715-6733` — 要求温度と環境変数によるサンプリングdraftの選択、draft上限の適用。
- `src/dsv41/ds4_model.cu:6830-6847` — 要求 sampler 引数を渡し、`sample_draft()` または greedy `sample_tokens()` を選ぶ処理。
- `src/dsv41/ds4_model.cu:6935-6965` — 提案分布を使った検証、sampler条件不一致時の q 分布構築、検証後の状態リセット。
- `src/dsv41/ds4_main.cpp:164-187` — speculative decode の呼び出し条件。
- `src/dsv41/ds4_model.cu:9352` — 公開 `Model` の生成時に `Impl` を構築。
