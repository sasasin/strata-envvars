# `DS4_DBG_EMB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 エンジンの埋め込み（embedding）経路を調べるための診断スイッチです。モデル読み込み後の pinned embedding データの先頭、embedding 計算後の中間値、および一部経路で tap 処理後の residual stream の統計値を stderr に出します。モデル計算の設定を選ぶ環境変数ではありません。

Metal ビルドでは共通 helper `ds4_dbg()` が環境変数を読みます。CUDA/HIP ビルドでは同 helper は常に `false` を返すため、この診断分岐は無効です（`src/dsv41/ds4_launch.h:30-36`）。

## 値と判定

| ビルド | 未設定 | 設定時 |
|---|---|---|
| Metal | 無効 | 空文字を含む、値が存在するすべての場合に有効 |
| CUDA / HIP | 無効 | 値にかかわらず無効 |

Metal では `std::getenv(name) != nullptr` だけで判定します。`1` との比較、数値変換、空文字検査はありません。したがって `0`、`false`、空文字も有効です。CLI 引数や別の環境変数による上書き・優先順位はありません。helper は値を static cache せず各チェック時に `getenv()` を呼ぶため、チェック時のプロセス環境が使われます（`src/dsv41/ds4_launch.h:30-36`）。

## 有効になる条件

- Metal ビルドであること。CUDA/HIP では `ds4_dbg()` がコンパイル時定数 `false` です。
- モデル読み込み時の embedding 初期化、または後述の forward / draft 経路が実際に実行されること。

DS4 エンジンであること自体が前提です。この変数が通常のモデル生成経路へ分岐や値の選択を加える箇所は見つかりませんでした。測定値・性能改善の主張はありません。

## 実行時の詳細

モデルの embedding weight を読み終えた後、`DS4_DBG_EMB` が有効なら `embed_pinned` の先頭 4 要素と次の行の先頭 2 要素を `DBG emb pinned: ...` として stderr に出します。weight 読み込み自体が失敗した場合は先に `embed.weight: read failed` を返すため、このログには到達しません（`src/dsv41/ds4_model.cu:2810-2833`）。

embedding 行列を GPU 側へ適用する各経路では、embedding 呼び出し後に `h[0..3]` の値を stderr に出す箇所があります。対象は MTP draft (`draft_`, `src/dsv41/ds4_model.cu:7758-7784`)、chunked forward の layer-split 経路（同 `8621-8635`, `8792-8809`）、serial forward（同 `9774-9792`）、parallel forward（同 `9888-9900`）です。serial forward ではさらに初期化後の `h` の最大絶対値・非有限値数・`h0` を `DBG hmax after init_pre ...` として、最初の tap 後には `DBG hmax after tap ...` として出します（同 `9759-9772, 9790-9792, 9817-9819`）。これらの forward 診断は通常経路の `h` や tap を変更するものではなく、値を読み出して表示します。

判定に static cache はなく、これらの箇所へ到達するたびに環境変数を確認します。GPU 値の診断箇所は Metal の `ds4_metal_flush()` の後に先頭 4 float を `cudaMemcpy()` で host にコピーし、`DBG at embed site ...` を出します。この flush と readback は診断有効時に追加される処理なので、実行時間の観測に影響し得ます。コピー呼び出しの戻り値はこれらの診断コードでは検査されません。診断固有の終了・エラー処理はなく、記録できる観測結果は stderr の `DBG ...` 行です（`src/dsv41/ds4_model.cu:7772-7783, 8628-8635, 8801-8808, 9781-9791, 9891-9900`）。

## 根拠

- 動的な名前を受け取る `ds4_dbg(const char*)` の定義と Metal / 非 Metal の差: `src/dsv41/ds4_launch.h:30-36`。
- 候補名の全参照: `src/dsv41/ds4_model.cu:2829, 7772, 7779, 8629, 8802, 9783, 9791, 9818, 9893`。リポジトリ全体の `rg` で確認し、これらはすべて前記 helper に渡される参照です。
- モデル読み込み後の pinned embedding ログ: `src/dsv41/ds4_model.cu:2810-2833`。
- forward / draft の値表示と `dbg_h()` 集計: `src/dsv41/ds4_model.cu:7758-7784, 8617-8636, 8792-8809, 9759-9792, 9817-9819, 9888-9900`。
