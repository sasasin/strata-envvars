# `STRATA_GLM_EXL3_DECODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 エンジンの EXL3 decode で使う CUDA kernel family を選びます。`legacy` は v1.1.8 由来の decode kernel、`new` は現在の `exl3.cu` の kernel を選びます。GPU の compute capability による既定選択は NVIDIA の sm_80 より前で legacy、それ以外で new です。この selector は Project Maya 由来の `src/dsv41/vendor` 内にありますが、Strata への port 時の変更として環境変数の読み取りが追加され、Strata の EXL3 経路から呼び出されています（`third_party/project-maya/NOTICE.md:3-11`, `src/dsv41/vendor/exl3.cu:1268-1294`）。

対象は `STRATA_BUILD_DSV41=ON` で構築される `strata-dsv41` の EXL3 経路です。この build option は既定で OFF です。GGUF の BF16 / MXFP4 行列は別 kernel 経路を使い、この変数による選択対象ではありません（`CMakeLists.txt:906-919`, `src/dsv41/ds4_model.cu:7639-7644`）。

## 値と判定

CUDA build では値全体を大文字小文字を区別して比較します。数値変換や空白除去はありません。

| 値 | 選択結果 |
|---|---|
| 未設定 | GPU の compute capability major が 8 未満なら legacy、8 以上なら new |
| `legacy`（完全一致） | legacy |
| `new`（完全一致） | new |
| 空文字、`Legacy`、`NEW`、その他の文字列 | 未設定と同じ GPU 世代による自動選択 |

明示値と CLI 引数・設定ファイル・他の環境変数との優先順位はありません。コードにこの環境変数を読む箇所は一つで、読み取り時には `legacy` / `new` の完全一致が GPU 世代判定より優先します（`src/dsv41/vendor/exl3.cu:1284-1290`）。

## 有効になる条件

- `STRATA_BUILD_DSV41` が有効で `STRATA_HIP_GFX906` build ではないこと。CMake はこの条件下で `strata-dsv41` と `strata_dsv41_kernels` を作ります。option の既定値は OFF です（`CMakeLists.txt:906-919`）。
- CUDA backend では環境変数を読み、EXL3 decode の kernel family を選びます。NVIDIA の device index が 0–63 の場合に選択が行われます。範囲外なら `use_legacy()` は false を返し、new 側になります（`src/dsv41/vendor/exl3.cu:1279-1294`）。
- HIP または Metal build では `use_legacy()` がコンパイル時に false を返す分岐となり、この環境変数を読みません。したがって値を設定しても legacy は選ばれません（`src/dsv41/vendor/exl3.cu:1272-1278`）。HIP では legacy kernel のソースも build 対象に加えません（`CMakeLists.txt:911-915`）。
- 選択は EXL3 行列の device decode 呼び出しに適用されます。EXL3 以外の GGUF BF16 / MXFP4 は別の `gg::mv` 等へ進みます（`src/dsv41/ds4_model.cu:7639-7644`）。モデルのパック形式により EXL3 decode API が使われない場合、この選択も使われません。

## 実行時の詳細

CUDA では EXL3 API の `prepare`、`several_ok`、`mv`、MoE gate/up・down、window experts の各呼び出しで selector が参照されます（`src/dsv41/vendor/exl3.cu:1391-1403,1523-1549`）。その selector は現在 device を取得し、デバイスごとの `static std::atomic<int> cache[64]` に最初の選択結果を保存します。以降同じプロセス・device では環境変数を読み直さないため、選択後にプロセス環境を変更しても反映されません。複数 device では device ごとに初回判定されます（`src/dsv41/vendor/exl3.cu:1279-1294`）。

legacy が選ばれた device では初回選択時に stderr へ `exl3: CUDA%d decodes with v1.1.8's kernels` を出力します。new 選択時にはこの selector からログは出ません（`src/dsv41/vendor/exl3.cu:1291-1292`）。この選択関数に無効値の警告や終了処理はありません。compute capability の取得結果 `major` は 0 で初期化され、API 呼び出しの失敗を別途処理せず、その値で自動選択します（同 `:1284-1290`）。

kernel 呼び出し側は API が失敗を返す場合に `exl3 mv failed` などのエラー文字列を設定する経路を持ちます（`src/dsv41/ds4_model.cu:7645-7653`）。これは環境変数の parse エラーではなく、選択後の decode API の失敗経路です。

## 根拠

- 読み取りと値判定、device ごとの cache、legacy 選択ログ: `src/dsv41/vendor/exl3.cu:1268-1295`。
- 各 EXL3 decode API で legacy/new を振り分ける処理: `src/dsv41/vendor/exl3.cu:50-53,1391-1403,1523-1549`。
- 呼び出し元と EXL3 / GGUF 行列の振り分け: `src/dsv41/ds4_model.cu:7639-7653,10356-10363,10400`。
- 対象 executable と build 条件: `CMakeLists.txt:906-919`。
- Project Maya 由来ファイルと Strata port 変更の説明: `third_party/project-maya/NOTICE.md:3-11`。
