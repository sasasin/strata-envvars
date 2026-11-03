# `FNX_RING_TAG_START`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Qwen3.8-Flash-Next の split engine が ring buffer 用の tag を割り当てる際、その最大使用 tag カウンター `tag_max_` の初期値を設定します。GPU ring の値が古い window のものかを識別する tag を通常より先の値から始められ、上限に近い場合は ring buffer を早期にクリアする経路にも入ります。コメントでも `tag_max_` の初期値を与える設定として説明されています（`src/split/src/engine.hpp:222-231`）。

この読み取りを含む `Engine` は、opt-in の `strata-split-N`（sFNX）と、同じ engine を組み込む `split_fnx_run` で使われます。split engine は Linux CUDA または Linux HIP 用で、`STRATA_BUILD_SPLIT` が有効な場合にだけ構成されます（`src/split/CMakeLists.txt:1-5,20-27,64-80,92-103,153-165`）。通常の Strata engine の設定としては使われません。

## 値と判定

変数が未設定なら constructor 内の `tag_max_` 初期値 `1` が維持されます。設定されている場合は `env_int("FNX_RING_TAG_START", 0)` で読みます。`env_int` は符号付き10進整数を文字列全体で解析し、先頭の `+` または `-` は許可します。空文字、空白、数字以外の末尾、10進整数でない表記、`long long` の範囲外は整数として受理されず、例外になります（`src/split/src/env.hpp:15-22,33-40`）。

変換後の範囲は `1` 以上 `TAG_END - 1` 以下です。`TAG_END` は `1u << 24`（16,777,216）なので、有効範囲は `1..16,777,215` です。範囲外では `FNX_RING_TAG_START: want 1..16777215, got <値>` という例外になります。値は `unsigned` に変換して `tag_max_` に代入されます（`src/split/src/engine.cu:411-416`; `src/split/src/engine.hpp:229-231`）。

| 入力 | 結果 |
|---|---|
| 未設定 | 既定の `tag_max_ = 1` を維持 |
| `1` ～ `16777215`（符号付き10進整数として全体が有効） | `tag_max_` に設定 |
| 空文字、整数でない文字列、整数変換の範囲外 | `env_int` の例外（`<NAME>: '<値>' is not a whole number`） |
| `0`、負数、`16777216` 以上 | 範囲エラーの例外 |

## 有効になる条件

- `src/split` の engine を組み込んだ実行ファイルを使うことが必要です。CMake は split engine を Linux CUDA または Linux HIP に限定し、`STRATA_BUILD_SPLIT` を opt-in としています（`src/split/CMakeLists.txt:1-5,20-27`）。
- sFNX の engine は Qwen3.8-Flash-Next 用です（`src/split/src/engine.cu:1-2`; `src/split/CMakeLists.txt:1-3`）。サーバー実行では `sfnx` が model と `Engine` を初期化し、`split_fnx_run` も同じ engine ソースを使います（`src/split/tools/sfnx.cpp:1051-1060`; `src/split/CMakeLists.txt:153-165`）。
- この変数に対応する CLI 引数や別の環境変数による優先順位・上書き分岐は、調査対象 commit の Strata 所有ソースでは確認できません。値は Engine constructor で直接読み取られます（`src/split/src/engine.cu:31,411-416`）。

## 実行時の詳細

`Engine` の構築後半で環境変数の設定有無を確認し、設定があれば整数を解析して範囲を検証します（それ以前に card buffer の確保と同期を行います）。constructor ごとの読み取りで、`static` cache はありません。Engine を作った後に環境を変更しても、既存 Engine の `tag_max_` は再評価されません。後で別の Engine を構築すれば、その constructor で改めて環境を読みます（`src/split/src/engine.cu:31,395-416`）。

`tag_max_` は ring tag の最大値として使われます。単一 tag は `ring_tag()` が `tag_max_` を増やして返し、複数 tag は `take_tags()` が現在の最大値より上から lane の parity に合う tag を割り当てます（`src/split/src/engine_common.cu:154-165`）。したがって、設定値は次に使う tag そのものではなく、初期の最大値です。`tag_` は別メンバーで初期値 `1` のままです（`src/split/src/engine.hpp:222-228`）。

割り当て前に `tags_room()` が `tag_max_ + n + 1 >= TAG_END` を判定します。上限に達する場合は全カードの処理を同期し、decode ring と attention ring（prompt ring があればそれも）をゼロクリアして、stderr に `fnx: ring tags reached <値>: the rings' buffers cleared, tags start again` を出し、`tag_max_` を `1` に戻します（`src/split/src/engine.cu:419-436`; `src/split/src/engine.hpp:229-239`）。たとえば最大値近くから始めると、最初の tag 割り当て前にこのクリア経路が発生し得ます。

未設定時は通常の初期値から始まります。設定値が不正または範囲外の場合、sFNX は Engine 初期化時の例外を失敗経路に渡し、標準出力のプロトコル行 `ERR <理由>` と `sfnx: failed: <理由>` を stderr に出して終了コード `1` で終了します（`src/split/tools/sfnx.cpp:1030-1035,1051-1062`）。`split_fnx_run` は `fnx_run: <理由>` を stderr に出し、終了コード `1` を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 根拠

- 候補名の実読み取りと範囲検証: `src/split/src/engine.cu:411-416`。
- 整数変換規則: `src/split/src/env.hpp:15-22,33-40`。
- tag の上限、初期値、割り当てとクリア: `src/split/src/engine.hpp:222-239`, `src/split/src/engine_common.cu:154-165`, `src/split/src/engine.cu:419-436`。
- split engine の backend・build 条件と実行ファイル: `src/split/CMakeLists.txt:1-5,20-27,64-80,92-103,153-165`。
