# `STRATA_CKPT_ASYNC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA build で、1 MiB 以上の GDN conversation checkpoint を host vector に保存するとき、device-to-device の staging copy と、その後の device-to-host 転送を別々に進める opt-in です。device 上の GDN state を staging buffer へコピーした後、背景 thread が pinned host buffer へ 4 MiB ずつ転送し、完了した piece を checkpoint vector へコピーします。checkpoint 内の他の小さな state は従来どおり同期的にコピーされます。生成 token や checkpoint の選択規則を変える処理ではなく、コピーの進め方を変えます。[`engine/src/core/conversation_state.cpp:319-320,337-388`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L319-L388)

## 値と判定

CUDA 実装は `std::getenv` の結果が null でないことに加え、値の先頭 1 byte が文字 `1` かを判定します。文字列全体の parse や大文字小文字変換はありません。関数内 `static const bool` に結果を保存します。[`engine/src/core/conversation_state.cpp:214-220`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L214-L220)

| build / 状況 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA (`STRATA_USE_HIP` 等の除外 macro なし) | off | `1`, `10`, `1anything` | 空文字、`0`, `true`, ` 1`, `01` |
| HIP、gfx906 compat、Metal | 常に off | なし | すべて。値を読まず `false` を返す |
| SYCL | この機能の設定読み取りなし | なし | 設定値は checkpoint save に作用しない |

`1` は先頭文字のみを見るため `10` や `1anything` も on です。先頭が `1` でなければ、後続に `1` があっても off です。空文字は設定済みでも off です。無効値をエラーにしたり警告したりする処理はありません。[`engine/src/core/conversation_state.cpp:214-220`; `engine/sycl/src/core/conversation_state.cpp:165-180`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L214-L220) [`engine/sycl/src/core/conversation_state.cpp:165-L180`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/sycl/src/core/conversation_state.cpp#L165-L180)

## 有効になる条件

- CUDA backend の build であること。CUDA/HIP 共通 engine の `conversation_state.cpp` が build 対象です。HIP と gfx906 compat は compile-time guard で無効です。[`engine/cmake/strata_gpu_engine.cmake:6-9,310-316`; `engine/src/core/conversation_state.cpp:214-220`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/cmake/strata_gpu_engine.cmake#L6-L9) [`engine/src/core/conversation_state.cpp:214-L220`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L214-L220)
- save 対象の GDN state が 1 MiB 以上であること。小さい state は変数が on でも同期 copy へ進みます。[`engine/src/core/conversation_state.cpp:307-320,385-388`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L307-L320)
- staging device buffer、pinned host buffer、CUDA stream の用意と device-to-device copy が成功すること。buffer/stream の割当てに失敗した場合は async 経路に入らず通常 copy に戻ります。device-to-device copy 自体が失敗した場合は save failure です。[`engine/src/core/conversation_state.cpp:337-350,385-388`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L337-L350)
- `STRATA_CKPT_VRAM_SLOTS` が有効で利用可能な slot がある場合、GDN state の device-to-device staging 先にその slot を使います。slot が無い場合は通常の staging buffer を使います。この別変数は非同期機能を有効化する条件ではありません。[`engine/src/core/conversation_state.cpp:189-212,337-350`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L189-L212)
- Metal build は専用の window checkpoint 関数へ分岐し、共通関数の async 判定も false です。SYCL は別の移植版 `conversation_state.cpp` を build し、同ファイルの save は同期 copy のみです。[`engine/metal/CMakeLists.txt:89-94,135-141`; `engine/src/core/conversation_state.cpp:303-306`; `engine/sycl/CMakeLists.txt:290-301`; `engine/sycl/src/core/conversation_state.cpp:165-180`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/metal/CMakeLists.txt#L89-L94) [`engine/src/core/conversation_state.cpp:303-L306`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L303-L306) [`engine/sycl/CMakeLists.txt:290-L301`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/sycl/CMakeLists.txt#L290-L301) [`engine/sycl/src/core/conversation_state.cpp:165-L180`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/sycl/src/core/conversation_state.cpp#L165-L180)

## 実行時の詳細

値は `ckpt_async_on()` の初回呼び出し時に読み、以降は process 内の static 値を使います。save の条件式では GDN size の判定より先にこの関数を呼ぶため、最初の checkpoint save が 1 MiB 未満でも値が cache されます。実行中に環境を変更しても再評価されません。CLI 引数や設定ファイルからの上書きはありません。[`engine/src/core/conversation_state.cpp:214-220,307-320`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L214-L220)

async save はまず前回の checkpoint copy を join し、GDN state を device 上の staging 先へ copy します。その後 `std::async` で背景 thread を起動し、thread は 4 MiB ごとに device-to-host DMA を発行し、event 完了を待って host vector へ `memcpy` します。この間、save 関数は小さな state の copy を進めて戻るため、GDN の host copy は後続処理と重なり得ます。[`engine/src/core/conversation_state.cpp:296-320,343-388`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L296-L320)

checkpoint の読取・restore、snapshot の保存や破棄、session file 操作、次の serve request などは必要な GDN copy を `conversation_checkpoint_join` で待ちます。join に timeout はありません。全体 join と対象 checkpoint の選択 join があり、copy が無い場合は何も待ちません。[`engine/src/core/conversation_state.cpp:276-291,574-619,712-715`; `engine/src/program/generate.cpp:18502-18506,19029-19033`; `engine/include/strata/core/conversation_snapshot.hpp:74-82`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L276-L291)

## ログと測定値

背景 copy が失敗すると、join 時に stderr へ `strata: STRATA_CKPT_ASYNC: a checkpoint copy failed (%s)` と出します。`join_locked` はエラーをログに記録するだけで呼出元へ返しません。同期 save の失敗は呼出側で `strata serve: checkpoint save: %s` と出力されます。stage/host/stream の割当てに失敗して同期 copy へ戻る場合、それ自体の専用ログはありません。[`engine/src/core/conversation_state.cpp:276-281,337-350`; `engine/src/program/generate.cpp:2561-2566`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/engine/src/core/conversation_state.cpp#L276-L281)

`docs/DETAILS.md` は、変更作者による CMP 170HX（GA100 / sm_80）、PCIe Gen2 x4 での checkpoint save の報告値を fresh vector 104–105 ms から 34–35 ms、reused vector 71.4 ms から 0.9 ms と記載しています。同文書は当プロジェクトで同カード上の測定をしていないと明記しています。また独立ユーザーの 0.2.6 / RTX 3090 / PCIe 3.0 x16 の試行として 73.2 ms から 62.4 ms への報告があります。これらは文書にある報告値であり、この調査で再測定した値ではありません。[`docs/DETAILS.md:1762-1778`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/docs/DETAILS.md#L1762-L1778)

`docs/SETTINGS.md` は対応先を「NVIDIA and AMD」としていますが、実装は `STRATA_USE_HIP` を含む build で常に false を返します。実装上は CUDA が有効で、HIP/gfx906/Metal と SYCL が対象外です。[`docs/SETTINGS.md:42`; `engine/src/core/conversation_state.cpp:214-220`; `engine/sycl/src/core/conversation_state.cpp:165-180`](https://github.com/Niko1221/Strata/blob/73d4f4196c25a65e02f6b9ef25d354826ce55105/docs/SETTINGS.md#L42)

## 根拠

- `engine/src/core/conversation_state.cpp:214-220` — build guard、先頭文字判定、static cache。
- `engine/src/core/conversation_state.cpp:296-407` — checkpoint save、1 MiB gate、allocation fallback、背景 copy と small state copy。
- `engine/src/core/conversation_state.cpp:276-291,417-465,563-619,703-715` — join、restore、snapshot の待ち合わせ。
- `engine/src/program/generate.cpp:2561-2576,18502-18506,19029-19033` — serve 側の失敗ログ・GPU 継続判定・request 境界の join。
- `engine/cmake/strata_gpu_engine.cmake:6-9,310-316`; `engine/metal/CMakeLists.txt:89-94,135-141`; `engine/sycl/CMakeLists.txt:290-301`; `engine/sycl/src/core/conversation_state.cpp:165-180` — backend ごとの build と SYCL の同期実装。
- `docs/DETAILS.md:1762-1778`; `docs/SETTINGS.md:42` — 測定報告と対応 backend 表記。
