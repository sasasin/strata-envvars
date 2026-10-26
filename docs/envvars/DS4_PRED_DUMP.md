# `DS4_PRED_DUMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4 のチャンク式 prompt 処理中、各対象 layer・chunk の router logits と router 入力の固定符号射影をバイナリファイルへ記録します。モデル計算の選択や出力を変える設定ではなく、学習・解析用データの出力フックです。`src/dsv41/ds4_model.cu` の DS4 実装にだけ読み取り箇所があります。

## 値と判定

| 値 | 挙動 |
|---|---|
| 未設定 | ファイルを開かず、予測データを出力しない。 |
| 設定あり | 値全体をファイルパスとして `fopen(path, "wb")` に渡す。既存ファイルは書き込み用に開かれ、内容が切り詰められる。`1` なども真偽値ではなくファイル名。 |
| 空文字 | `fopen("", "wb")` を試みる。開けず `nullptr` になれば出力処理は無効のまま進む。 |
| パスを開けない | `fopen` の結果が `nullptr` となり、出力ブロックが実行されない。専用の警告・エラー処理はない。 |

文字列比較や数値変換はありません。環境変数は `Model::Impl` の `pred_f` 初期化時に読み、その後は保持した `FILE*` を使用します。実行中に環境変数を変更してもパスは再評価されません。

## 有効になる条件

- DS4 モデルのチャンク式 prompt 経路を実行すること。短い prompt が window 経路を選ぶ場合、この出力箇所は通りません。チャンク経路は `forward_chunks()` です。
- レイヤー処理が `mi == 0` であり、かつ MTP layer (`l.mtp`) ではないこと。
- `fopen` が成功すること。

環境変数の有無だけでチャンク式 prompt 経路が選択されるわけではありません。たとえば `--prefill-chunk`、thread/tensor parallelism、`DS4_WINDOWS` などの経路選択条件は別に処理されます。データの内容について Strata の `docs/DETAILS.md` に追加説明や測定値は見つかりませんでした。

## 実行時の詳細

チャンクの各対象 layer で router logits (`c.glog`) と router 入力 (`c.x`) を取得し、以下のレコードを順に書き込みます。

1. 3 byte のヘッダー: layer index の下位 8 bit (`u8`)、chunk の token 数 `T` の下位 8 bit、`T` の上位 8 bit (`u16` little-endian を想定したホスト表現)。
2. `T × l.n_exp` 個の router logits を fp16 に変換した値。
3. `T × 256` 個の router 入力射影を fp16 に変換した値。

現行コードのコメントでは router logits を `T × 384` と記しています。射影は token ごとに 256 要素を計算し、各要素は入力次元 `D` の要素へ固定ハッシュで決まる `+1/-1` 符号を掛けて加算し、`sqrt(D)` で正規化した値です。各レコードは `mi == 0` の worker だけが出力し、共通の `dump_mu` mutex の下で書き込まれます。`fwrite` の戻り値検査、`pred_f` の明示的な `fflush` / `fclose` はこのソース内で確認できません。

## 根拠

- `src/dsv41/ds4_model.cu:509-521` — チャンク処理用 buffer と固定符号射影 kernel。
- `src/dsv41/ds4_model.cu:1150-1154` — レコード形式の説明と環境変数からのファイルオープン。
- `src/dsv41/ds4_model.cu:7325-7342` — `mi` / MTP 条件、GPU からのデータ取得、fp16 変換、レコード書き込み。
- `src/dsv41/ds4_model.cu:8187-8195` — チャンク式 prompt の `forward_chunks()`。
- `docs/DETAILS.md` — `DS4_PRED_DUMP` に関する記載なし。
