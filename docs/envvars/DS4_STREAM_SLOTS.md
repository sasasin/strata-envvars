# `DS4_STREAM_SLOTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 engine の検証 window で、PCIe lane にストリームさせる CPU lane の distinct expert 数の上限です。既定値は 16 で、実装上の window pull の slot 数 (`pcie::kSlots`) が上限です。上限を小さくすると window ごとの候補数が制限されますが、この変数だけで streaming を有効にするものではありません。`src/dsv41/ds4_model.cu:1375-1382,10039-10054,10063-10098`、`src/dsv41/ds4_pcie.cuh:23-35`。

## 値と判定

`Model::Impl` のメンバー初期化時に `getenv` で設定有無を調べ、設定されていれば `atoi` で整数化して `[0, pcie::kSlots]` に clamp します。unset の既定値は `pcie::kSlots`（16）です。

| 設定値 | `ln_win_max` |
| --- | ---: |
| unset | 16 |
| 空文字、整数に変換できない文字列 | 0 (`atoi` が 0) |
| `0`、負値 | 0（0 未満は clamp） |
| `1`〜`15` | その整数 |
| `16` 以上 | 16（上限に clamp） |

`atoi` のため文字列全体の妥当性は検査されず、先頭の空白と符号は整数変換で扱われ、数字の後ろに続く文字は値の判定に使われません（例: `4junk` は 4）。`int` で表現できない数値文字列に対する `atoi` の結果は C++ の仕様上定義されません。この変数に対応する CLI 引数や別の変数からの値上書きはありません。根拠: `src/dsv41/ds4_model.cu:1380-1382`、上限定数は `src/dsv41/ds4_pcie.cuh:23-24`。

## 有効になる条件

- 読み取り箇所は DSV41 engine の `src/dsv41/ds4_model.cu` にあります。CMake では `STRATA_BUILD_DSV41` が既定 OFF で、CUDA/HIP 対応の `strata-dsv41` target にこのファイルが含まれます。GPU backend なしの build は host-side `ds4_gg_bench` のみなので、この変数を読む model 実装はその build に含まれません。`CMakeLists.txt:931-945,2930-2941`。
- 上限が使われるのは `T > 1` の verify window で `ln_win` が有効になり、`lane_take_win()` に進む経路です。単一 token の `lane_take()` にはこの上限を使いません。呼び出し条件は `src/dsv41/ds4_model.cu:9531-9538`。
- `ln_win` は `DS4_STREAM_WIN` が未設定なら one-GPU path の判定値に従い、設定時は `atoi` の結果が 0 以外なら有効です。CUDA の one-GPU path は NVIDIA の単一 discrete GPU 条件と `DS4_STREAM` / lane calibration などの影響を受けます。HIP ではその自動 one-GPU 判定を行いませんが、明示した `DS4_STREAM_WIN` の値は `ln_win` の判定に使われます。したがって `DS4_STREAM_SLOTS` は window streaming をオンにせず、その有効条件を上書きもしません。`src/dsv41/ds4_model.cu:6103-6138,6143-6175`。
- `ln_win` が有効でも、PCIe lane の初期化が失敗すると lane は解放されて終了し、window streaming は行われません。また window ごとの選択はコスト情報 `k.ok()`、lane timing の判定、強制指定 `ln_force` の有無にも依存し、条件を満たさなければ streamed expert 数 `ns` は 0 のままです。`src/dsv41/ds4_model.cu:10055-10070,10456-10466`。

## 実行時の詳細

環境値は static cache ではなく `Model::Impl` の `ln_win_max` メンバー初期化子で読み取られます。`Model` の生成時に `Impl` を作るため、その時点で値が固定され、同じ model instance の実行中にプロセス環境を変えてもこの上限は再評価されません。新しい `Model` instance を生成すれば再読込されます。`src/dsv41/ds4_model.cu:1052-1054,1380-1382,14858-14860`。

window 内の pick を distinct expert ごとにまとめ、lane が warm と判定した expert を token 数の多い順に並べます。実際に lane に渡す数 `ns` は、コスト関数が評価する `s_` の最大値を `min(ex.size(), D.slots, ln_win_max)` で制限した範囲から選ばれます。したがってこの値は「必ず streaming する数」ではなく、候補上限です。選ばれた expert の pick は `picks` から取り除かれ、lane pull に登録されて `lane_go()` が開始します。`src/dsv41/ds4_model.cu:10039-10054,10055-10102`。

この変数専用のログや無効値警告はありません。実行時には PCIe lane の読取失敗で、最初の失敗時に stderr へ `ds4: PCIe lane: reading a streamed expert failed - that token went without it` を一度出す経路があります（変数値固有のエラーではありません）。STAT 出力では stream があった場合に限り `pcie=...` が付きますが、この統計は `DS4_STREAM_SLOTS` の設定値そのものを表示しません。`src/dsv41/ds4_model.cu:10020-10027,10093-10098`、`src/dsv41/ds4_main.cpp:972-983`。

## 根拠

- 読み取り・既定値・clamp: `src/dsv41/ds4_model.cu:1380-1382`。
- window slot の上限と候補選択、実行: `src/dsv41/ds4_model.cu:10039-10102`。
- window streaming の呼び出し条件と GPU fetch: `src/dsv41/ds4_model.cu:9531-9538,14198-14205`。
- one-GPU path と `DS4_STREAM_WIN` の関係: `src/dsv41/ds4_model.cu:6103-6138,6143-6175`。
- pull slot 数: `src/dsv41/ds4_pcie.cuh:23-35`。
- target の build 条件: `CMakeLists.txt:931-945,2930-2941`。
