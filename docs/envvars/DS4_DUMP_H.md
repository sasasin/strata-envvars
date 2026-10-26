# `DS4_DUMP_H`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンの通常の window 処理で、各層の処理後に residual stream を float32 のバイナリファイルへ出力します。`tools/dsv41/compare.py --layers` が参照側の中間状態と比較するための診断用フックです。モデル計算の分岐を変える設定ではありません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | ファイルを開かず、記録しない |
| 空文字を含む設定値 | 値をパスとして `fopen(path, "wb")` に渡す。数値や真偽値への変換はしない |
| 開けるパス | 起動時にバイナリ書き込みで開く。既存ファイルは切り詰められる |
| 開けないパス（空文字を含む） | `fopen` が null を返し、記録処理は無効のまま。ここでは警告・エラーを出さない |

値は `Impl` のメンバー初期化時に読み取られ、開いた `FILE*` が保持されます。したがって、モデル生成後に環境変数を変更しても出力先は変わりません。ファイル名の解析や別設定との優先順位はありません（`src/dsv41/ds4_model.cu:1127`）。

## 有効になる条件

- CMake の `STRATA_BUILD_DSV41=ON` でビルドされる専用実行ファイル `strata-dsv41` が必要です。この CMake オプションは既定で `OFF` で、通常の `strata` 実行ファイルを有効化しません（`CMakeLists.txt:797-811`）。
- `Impl::forward()` がパラレル経路ではなく `forward_serial()` を使うときに記録します。`par` が真なら `forward_par()` へ進み、同関数には `DS4_DUMP_H` の記録処理がありません（`src/dsv41/ds4_model.cu:8613-8616, 8635-8648, 8691-8708`）。
- `forward_chunks()` の層別 chunk 処理にもこの変数による書き出しはありません。`Model::feed()` が chunk 経路を選んだ場合、その呼び出しでは記録されません。window 経路または `step()` から `forward_serial()` に到達する呼び出しが対象です（`src/dsv41/ds4_model.cu:8189-8192, 9355-9367`）。

## 実行時の詳細

`forward_serial()` は window ごとに `T × 層数 × hc × dim` 個の float32 一時バッファを用意します。各層の `layer()` 完了後、その層を実行した GPU の `dd.h` をホストへ非同期コピーし、CUDA stream を同期してから一時バッファの該当位置へ格納します。全層の処理後にバッファ全体を `fwrite()` します（`src/dsv41/ds4_model.cu:8636-8648, 8670-8683`）。

ファイルにはヘッダーがなく、window ごとに float32 値が追記されます。配列順は `[token, layer, hc, dim]` で、1 window あたり `T × g.nl × H × D × 4` バイトです。これは書き込み時のインデックス計算と `compare.py` の reshape `[T, layer, hc, dim]` に基づきます（`src/dsv41/ds4_model.cu:8672-8683`, `tools/dsv41/compare.py:45-56`）。

各層の GPU→CPU コピーと stream 同期、および window 全体の一時バッファ確保が追加されます。`fwrite()` の戻り値は検査されず、この変数専用のログもありません。実装内で `dump_h` に対する明示的な `fflush()` / `fclose()` は確認できません（`src/dsv41/ds4_model.cu:1127, 8672-8683, 1243-1286`）。

## 根拠

- 値の取得とファイルのオープン: `src/dsv41/ds4_model.cu:1127`
- serial window での層別コピーと出力: `src/dsv41/ds4_model.cu:8635-8688`
- parallel window 経路: `src/dsv41/ds4_model.cu:8691-8708`
- chunk 経路の選択: `src/dsv41/ds4_model.cu:8189-8192, 9355-9367`
- 対応する専用ターゲットと既定ビルド条件: `CMakeLists.txt:797-811`
- 比較ツールの入力形状と用途: `tools/dsv41/compare.py:23, 45-56`
- `docs/DETAILS.md` にはこの変数の説明や測定値を確認できませんでした。
