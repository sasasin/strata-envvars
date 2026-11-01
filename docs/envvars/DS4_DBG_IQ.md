# `DS4_DBG_IQ`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンの Metal 経路で、GGUF の低 bit matvec 結果をホスト側で再計算し、GPU 計算結果と stderr に並べて出す診断用スイッチです。モデルの計算結果や kernel 選択を変える設定ではありません。

## 値と判定

| 状態 | 判定 | 結果 |
|---|---|---|
| 未設定 | `getenv` が null | 診断しない |
| 空文字を含む設定済みの値 | `getenv` が null ではない | 診断を有効化 |
| その他の値（例: `0`, `false`, `1`） | 値の parse・比較なし | 診断を有効化 |

数値変換、境界値、無効値の扱いはありません。CLI 引数、設定値、他の環境変数との優先順位もありません。この値は各 `ds4_dbg("DS4_DBG_IQ")` 呼び出し時に `std::getenv` で調べられ、static cache されません。

## 有効になる条件

- `STRATA_METAL` が定義されたビルドでのみ、`ds4_dbg` が環境を確認します: それ以外のビルドでは同 helper は常に `false` を返します。`DS4_DBG_IQ` の参照と診断コードも `#if defined(STRATA_METAL)` 内です。したがって CUDA/HIP ではこの変数は Strata による読み取りも診断出力もありません。
- そのビルドに DeepSeek-V4.1 エンジンが含まれ、GGUF matvec (`gguf::mv`) が呼ばれ、低 bit job (`nij > 0`) があり、`iq::mv` が成功した場合に診断部へ進みます。CMake の `STRATA_BUILD_DSV41` は既定 OFF で、ON かつ gfx906 HIP でない場合に `strata-dsv41` ターゲットを追加します。
- 低 bit job がない場合や `iq::mv` が失敗した場合は、この診断部は実行されません。`nij` が正でもホスト decoder がその型を扱えない場合、`DBG iq: no host decode for type %d` を出してその job の行ループを抜けます。

## 実行時の詳細

`gguf::mv` は GGUF 行列の matvec job を低 bit job として集め、device 側 `iq::mv` の成功後に本変数を確認します。診断が有効なら Metal の保留処理を flush し、最大 2 job について各 job の先頭 3 行をホスト decoder `gg_row_to_bf16` で復元します。各行について BF16 重み・量子化済み activation (`xq`, `xd`) から double 累算した `host` 値と、kernel 出力 `y[r]` の `kernel` 値などを `DBG iq job ...` 行として stderr に出します。この処理は比較値の出力だけで、診断値に応じた fallback、終了、または matvec 結果の書き換えはありません。

診断部より前の通常の失敗経路は別です。`iq::mv` が false を返すと `ds4 gguf mv: a low-bit job not covered` を stderr に出し、エラーカウンターを増やして `false` を返します。呼び出し元 `Model::mv` はそれを `exl3 mv failed` として返します。この失敗ログは `DS4_DBG_IQ` の値に依存しません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36`: Metal では `getenv(name) != nullptr`、非 Metal では定数 `false`。
- `src/dsv41/ds4_gguf.cu:1173-1203,1298-1324`: matvec job の分類、低 bit job 数、`iq::mv` 成功後に限る診断分岐と通常失敗。
- `src/dsv41/ds4_gguf.cu:1302-1322`: Metal 条件、値の存在判定、最大 2 job・各 3 行のホスト再計算と stderr 出力。
- `src/dsv41/ds4_gguf_cpu.hpp` を参照する `src/dsv41/ds4_gguf.cu:10-13,1311-1319`: ホスト decoder の呼び出しと比較計算。
- `src/dsv41/ds4_gguf.cu:34-44`: 通常の error / fail の stderr 出力とカウンター。
- `src/dsv41/ds4_model.cu:7639-7653`: GGUF matvec の呼び出しと失敗の伝播。
- `CMakeLists.txt:906-920`: DeepSeek-V4.1 の独立ターゲットと `STRATA_BUILD_DSV41` の既定値・条件。
