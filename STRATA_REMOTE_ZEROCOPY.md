# `STRATA_REMOTE_ZEROCOPY`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

remote expert cache を使う GPU が入力 activation と出力行を pinned host staging buffer から直接読み書きする経路を選びます。通常の経路では入力を GPU buffer に転送し、計算後の出力行を host staging buffer に戻します。この環境変数を unset にした場合はゼロコピー経路を試みますが、host pointer の GPU 側 alias を取得できなければ通常のコピー経路に戻ります。

対象の読み取りは CUDA 実装と SYCL 実装の `RemoteExperts::open()` にあります。`--expert-cache-device1`（必要なら device2/3 も）で remote expert cache を作る実行経路でのみ読み取られます。primary GPU だけを使う実行ではこのコードに到達しません。

## 値と判定

値全体の parse はせず、先頭文字だけを見ます。大文字小文字、空白、数値としての妥当性は検査されません。

| 値 | 判定 |
|---|---|
| unset | ゼロコピーを試す |
| 空文字 | ゼロコピーを試す |
| 先頭文字が `0`（例: `0`, `0abc`） | ゼロコピーを無効にする |
| それ以外（例: `1`, `true`, `false`, `-1`） | ゼロコピーを試す |

「試す」場合、CUDA では `cudaHostGetDevicePointer()` が入力・出力 staging buffer の両方で成功したときだけ有効です。片方でも失敗すると通常のコピー経路を使います。SYCL 側では staging buffer のポインタをデバイスから使うポインタに割り当て、両方の `DPCT_CHECK_ERROR` が成功した場合に有効になります。

## 有効になる条件

- remote expert cache が実際に設定され、その `RemoteExperts::open()` が実行される必要があります。生成コードは `--expert-cache-device1..3` の正の slot 数について helper を開きます。remote expert cache 自体にも、profile、CUDA0 expert cache、expert pool などの前提条件があります。
- `STRATA_REMOTE_ZEROCOPY` が先頭 `0` でなくても、staging buffer の GPU 側 pointer を取得できなければ機能しません。この失敗による専用ログはありません。
- CUDA の `--remote-expert-opt` 経路では、入力のゼロコピーは維持されますが、出力行は reduction 用 GPU buffer `d_out_` に書かれるため、出力の host への転送は別経路です。`--remote-expert-opt` は `--serve` が必要です。
- SYCL 側の同名コードでも環境変数を読み、host staging pointer を直接使う経路を持ちます。CUDA API の `cudaHostGetDevicePointer` を使う CUDA 実装とは pointer 準備が異なります。

## 実行時の詳細

環境変数は各 `RemoteExperts::open()` の staging buffer 確保後に読み取られ、`zero_copy_` に保存されます。同じ helper の実行中に環境を書き換えても再評価されません。別の helper を開く場合にはその `open()` で再び読み取ります。

`begin()` は、入力 `x` をまず pinned host の `h_x_` に CPU memcpy します。ゼロコピーが有効なら CUDA では `z_x_`（SYCL では `z_x_`）を量子化 kernel に渡し、通常経路なら `h_x_` から `d_x_` への転送後に `d_x_` を渡します。ゼロコピーでは grouped expert kernel の出力先も pinned `h_out_` にできます。`finish()` は stream/queue の完了を待ってから、該当する compact 行を呼び出し元の出力へ CPU memcpy します。

通常経路への fallback 時に警告ログは出しません。`STRATA_REMOTE_ZEROCOPY=0` は明示的に通常経路を選びます。コードにはこの切り替えによる速度や token 結果の測定値はありません。

## 根拠

- `src/core/remote_experts.cpp:195-221`: pinned staging buffer の確保後に環境変数を読み、CUDA host alias の取得結果を含めて `zero_copy_` を設定。
- `src/core/remote_experts.cpp:292-345`: 入力 staging、通常経路の入力・出力転送、量子化と grouped kernel の buffer 選択、完了待ちと compact 行の取り出し。reduction 有効時の出力先選択も含む。
- `sycl/src/core/remote_experts.cpp:256-315,392-469`: SYCL staging allocation、環境変数判定、入力・出力 pointer の選択と fallback 転送。
- `src/program/generate.cpp:5431-5435,5501-5511`: remote cache の前提条件と正の remote slot 設定ごとの `RemoteExperts::open()` 呼び出し。
- `src/program/generate.cpp:2641-2643`: `--remote-expert-opt` が `--serve` を要求する検証。
- `docs/SECOND_GPU.md:3-8,18-22,87-100`: helper GPU、pinned host buffer、remote expert optimization の利用説明。環境変数の値判定と pointer fallback はソース実装に基づいて記載。
