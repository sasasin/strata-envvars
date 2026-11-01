# `DS4_FAT_PIECE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`DS4_FAT_PIECE` は DeepSeek V4.1 の CUDA 実装で、busy expert の gate/up 計算を一度に処理する最大行数を指定します。これは単独で busy expert 経路を有効にするスイッチではありません。`DS4_FAT_ROWS` などの条件でその経路が有効になり、さらにモデル層と重み形式が条件を満たした場合にだけ参照されます。

この経路は `STRATA_BUILD_DSV41` が有効な場合にビルドされる独立実行ファイル `strata-dsv41` に含まれます。HIP と Metal では `fat_ready()` が早期に `false` を返すため、この変数を読む行には到達しません。根拠: `CMakeLists.txt:906-920`, `metal/CMakeLists.txt:135-169`, `src/dsv41/ds4_model.cu:3481-3502`。

## 値と判定

| 環境値 | `R`（行数） |
|---|---:|
| 未設定 | 1024 |
| 設定あり | `max(64, atoi(value))` |

値は `std::atoi` で変換され、文字列全体の妥当性検査やエラー判定はありません。したがって空文字、数値に変換できない文字列、64 未満の数値、負値はすべて下限の 64 になります。数値の後ろに非数値文字が続く場合は `atoi` が変換した数値部分が使われます（例: `128tail` は 128）。コード上の上限 clamp はなく、64 以上の変換結果はそのまま使われます。`atoi` の扱える範囲を超える入力はこのコードで検査されず、結果は保証されません。未設定時の既定値 1024 は、設定値を 0 にした場合の値とは異なります。

`R` は関数内の `static const int` です。busy expert の準備条件を通り、`fat_w` が未割り当ての最初の呼び出しで初期化された後は、同一プロセス内で再評価されません。バッファ確保がその呼び出しで失敗しても、初期化済みの `R` は変わりません。実行中に環境値を変更しても反映されません。根拠: `src/dsv41/ds4_model.cu:3481-3489`。

## 有効になる条件

以下の条件を満たす `run_set()` の呼び出しでのみ値が使われます。

- `DS4_FAT_ROWS` が正の値として解釈されること。未設定・0・負値・数値に変換できない値では busy expert 経路は無効です。正値は最低 17 に引き上げられ、行数がその閾値以上の expert が対象になります。
- `c.fat_off` が未設定で、対象 `Chunk` の busy expert バッファが未割り当てであること。
- 層が MXFP4 で、`gg::mx_experts()` が false、`D` と `FF` がともに 256 の倍数であること。
- gate/up の型が同じで、gate/up と down の両方で `gg::iq::f16_rows_ok()` が true を返すこと。
- HIP と Metal 以外のビルドであること。コード上、この機能のバッファ確保と GEMM 呼び出しは CUDA API を使います。

いずれかを満たさない場合 `DS4_FAT_PIECE` は読み取られず、通常の `gg::set_gate_up()` / `gg::set_down()` の経路になります。根拠: `src/dsv41/ds4_model.cu:3474-3488,4209-4225,4243-4258`。

## 実行時の詳細

`run_set()` は条件を満たすと `fat_ready()` を呼びます。準備処理では `R` 行分の `fat_x` と `fat_gu` を確保し、成功時にその値を `c.fat_r` に保存します。gate/up の `fat_gate_up()` は expert ごとに `R` 行以下の部分へ分けて入力行を gather し、各部分を `cublasGemmEx()` で計算します。最後の部分は残り行数です。down 側の `fat_down()` は expert の行を分割せず、一回の `cublasGemmEx()` で処理します。よってこの変数は gate/up の作業バッファ寸法と分割に作用し、down GEMM の分割には使われません。根拠: `src/dsv41/ds4_model.cu:3488-3500,3505-3525,3528-3541`。

バッファ確保のいずれかが失敗すると CUDA の最終エラーを `cudaGetLastError()` で取り出し、stderr に `ds4: CUDA%d: no VRAM for the busy experts' path (... MB): the tiles take them` と出します。その `Chunk` では `c.fat_off` を立てて以後の試行を止め、`fat_ready()` は false を返すため `run_set()` の通常タイル経路で計算を続けます。根拠: `src/dsv41/ds4_model.cu:3489-3500,4215-4225,4243-4258`。

busy expert GEMM 自体が失敗すると `fat_gate_up()` または `fat_down()` は `err` に失敗内容を設定して false を返します。`run_set()` と上位の実行経路はその false を伝播します。CLI は feed の失敗時に stderr へ `ds4: <err>`（呼び出し経路によっては `strata-dsv41: <err>` または `maya-ds4: <err>`）を出します。CUDA の結果を含む具体的な終了コードは、環境変数の実装からは固定されていません。根拠: `src/dsv41/ds4_model.cu:3510-3522,3530-3539,4243-4254,8485-8488,10702-10714`; `src/dsv41/ds4_main.cpp:887-919,1138-1147,1209-1211,1404-1406`。

## 根拠

- 直接の環境変数参照は `src/dsv41/ds4_model.cu:3488` のみです。リポジトリ全体の `DS4_FAT_PIECE` 完全一致検索でもこの一箇所だけでした。動的に名前を受け取る helper 経由の参照はありません。
- busy expert 経路がオプトインであることと `DS4_FAT_ROWS` の閾値: `src/dsv41/ds4_model.cu:3470-3486,4212-4225`。
- DSV41 実行ファイルのビルド条件: `CMakeLists.txt:906-920`。
- `docs/DETAILS.md` に `DS4_FAT_PIECE` の追加説明や測定値は見つかりませんでした。ソースコメントにある busy expert 経路の測定主張は、`src/dsv41/ds4_model.cu:3470-3473` にありますが、本調査で測定を再現・検証したものではありません。
