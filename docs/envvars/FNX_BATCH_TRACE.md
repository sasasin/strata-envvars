# `FNX_BATCH_TRACE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX のバッチデコードで、各 decode window の lane ごとの draft offer と選択 plan を stderr に出す診断スイッチです。デコード計画や draft の選択自体を変更しません。値を `BatchDecoder` のメンバー `trace_` に保存し、window の plan を計算した後にその値で出力を分岐します。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 既定値 `0`。トレースしない |
| `0` と数値変換される整数 | トレースしない |
| `0` 以外の整数 | トレースする。負数も含む |
| 空文字、整数でない文字列、整数の後ろに余分な文字がある値、`long long` の範囲外 | 整数として受理されず、例外になる |

値は `env_int()` で 10 進の符号付き整数として全体を parse します。`+` / `-` と数字列を受け付け、空白や小数、`1x` などは受け付けません。したがって `00` や `-0` は 0、`-1` は非 0 です。環境変数の整数値に別の上限・下限 clamp はありません。根拠: `src/split/src/env.hpp:15-21,33-39`、`src/split/src/batch.cpp:85`。

## 有効になる条件

- sFNX は `STRATA_BUILD_SPLIT=ON` で追加される任意ビルドで、CMake は Linux CUDA または Linux HIP の構成に限定しています。Windows / macOS と、split build を含まない通常の Strata 実行にはこの読み取り箇所は入りません。根拠: `CMakeLists.txt:2945-2949`、`src/split/CMakeLists.txt:1-7,20-30,92-103`。
- sFNX サーバーでは `--batch` の slot 数が 2 以上で、`FNX_BATCH_DRAFTS` が `off` でないとき `BatchDecoder` が作られます。`--batch` の既定値は 1 なので、明示的に複数 slot を設定しないサーバーでは読み取りません。`FNX_BATCH_DRAFTS` は未設定時 `mtp`、`1` で `mtp`、`lookup` で lookup mode、`0` で off です。根拠: `src/split/tools/sfnx.cpp:65-68,89-103,443-445`、`src/split/src/engine_common.cu:1020-1028`。
- `split_fnx_run` では `bdecode` mode が `BatchDecoder` を生成します。この mode は `FNX_BATCH_DRAFTS` が off なら案内を stderr に出して status 2 で終了し、off でなければ読み取りに進みます。これは CMake で作られる sFNX の診断用 test driver です。根拠: `src/split/tools/fnx_run.cpp:646-670`、`src/split/CMakeLists.txt:153-165`。
- `FNX_BATCH_TRACE` 自体を上書きする CLI 引数や、別環境変数との優先順位は実装にありません。`FNX_BATCH_DRAFTS` が off の経路は decoder が生成されず、このトレースも発生しません。

## 実行時の詳細

`BatchDecoder` のコンストラクターで環境から値を読み、`trace_` に一度保存します。sFNX サーバーでは `Server` の構築時、split_fnx_run の `bdecode` では decoder の構築時に読み取られます。window や request ごとの再読み取りはなく、プロセス起動後の環境変更は既に作成された decoder には反映されません。根拠: `src/split/tools/sfnx.cpp:435-445`、`src/split/tools/fnx_run.cpp:646-670`、`src/split/src/batch.cpp:64-86`。

`trace_` が真なら、各 `BatchDecoder::window()` で plan を求めた後、`batch plan:` に続けて各 lane の offer 種別（`chain` / `look`）、draft 数 `d`、最大 6 個の reach 値を並べ、stderr に 1 行出します。値が 0 の場合はこの出力分岐を通りません。根拠: `src/split/src/batch.cpp:287-323`。

不正値の場合、helper は `FNX_BATCH_TRACE: '<値>' is not a whole number` 形式の `std::runtime_error` を投げます。sFNX ではサーバー構築時の例外が `fail()` に届き、stdout に `ERR ...`、stderr に `sfnx: failed: ...` を出して status 1 で終了します。診断用 `split_fnx_run` は `fnx_run: ...` を stderr に出して status 1 で終了します。根拠: `src/split/src/env.hpp:33-39`、`src/split/tools/sfnx.cpp:1030-1035,1063-1092`、`src/split/tools/fnx_run.cpp:1364-1373`。

## 根拠

- 読み取り・既定値と保存先: `src/split/src/batch.cpp:64-86`
- 整数全体の変換と不正値: `src/split/src/env.hpp:15-21,33-39`
- 出力内容と stderr への書き込み: `src/split/src/batch.cpp:287-323`
- sFNX サーバーでの decoder 生成条件: `src/split/tools/sfnx.cpp:65-68,435-445`
- バッチドラフト mode の値と既定: `src/split/src/engine_common.cu:1020-1028`
- ビルド条件: `CMakeLists.txt:2945-2949`、`src/split/CMakeLists.txt:1-7,20-30`
- `bdecode` 診断用 driver の経路: `src/split/tools/fnx_run.cpp:646-670`、`src/split/CMakeLists.txt:153-165`
