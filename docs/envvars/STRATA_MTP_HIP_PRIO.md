# `STRATA_MTP_HIP_PRIO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP ビルドで MTP drafter が使う `cs_` ストリームについて、最優先度を指定した non-blocking stream の作成を有効にするか選ぶ。MTP の prefill、draft graph、chain の起動はこの `cs_` を使うため、変わるのは drafter の stream 作成時に Strata が要求する優先度である（`engine/src/core/mtp.cpp:629-646,1577-1656,1936-1948,2110-2154`）。CUDA の `STRATA_MTP_PRIORITY` 分岐とは別で、この変数は HIP ビルドの分岐でのみ読まれる（同 `:613-645`）。

## 値と判定

`std::getenv` で取得し、未設定または空文字なら値を `atoi` に渡さず、GPU 世代による既定値を使う。空でない文字列は `std::atoi` で変換し、結果が 0 以外なら優先 stream を要求する。文字列全体の検証、範囲検査、大文字小文字の判定はない。したがって `1`、`-1`、` 1`、`1tail` は有効、`0`、`0tail`、`true`、`false`、`x1` は無効になる（`atoi` が数値接頭部を変換し、先頭の空白を読み飛ばすため）。

| ビルド・GPU | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_USE_HIP` かつ `STRATA_HIP_GFX906` ではない。gfx1200 / gfx1201 | GPU 情報の取得に成功すれば ON。空文字もこの既定値 | 空でない文字列の `atoi` 結果が 0 以外（例: `1`, `-1`, ` 1`, `1tail`） | 空でない文字列の `atoi` 結果が 0（例: `0`, `0tail`, `true`, `x1`） |
| 同 HIP ビルド。他の GPU、または既定判定で GPU 情報を得られない場合 | OFF。空文字もこの既定値 | 同上 | 同上 |
| CUDA、gfx906 互換 HIP、Metal、およびこの環境変数を読む分岐を持たない build | この変数による判定なし | 適用なし | 適用なし |

GPU 既定値の gfx12 判定は `gfx_arch_is_gfx12` が `gfx1200` / `gfx1201` と完全一致（または `:` で続く arch 名）する場合に true を返すもの（`engine/src/core/mtp.cpp:634-639`、`engine/include/strata/kernels/gfx_arch.hpp:15-19,41-42`）。数値として表現できない文字列は `atoi` が 0 を返すため無効扱いになる。数値の範囲外を含む `atoi` のオーバーフロー時の結果はここで定義されていない。

## 有効になる条件

- `engine/src/core/mtp.cpp` の HIP 分岐は `STRATA_USE_HIP` が定義され、`STRATA_HIP_GFX906` が未定義のときだけコンパイルされる（`engine/src/core/mtp.cpp:623-645`）。gfx906 互換 build は別 macro を定義する（`engine/cmake/backends/hip.cmake:6-26`）。
- MTP drafter をロードする経路で判定される。generate は `--spec` が 2 未満なら `--mtp` を無視してクリアし、MTP パスが残った場合に `mtp.load(...)` を呼ぶ（`engine/src/program/generate.cpp:8243-8265`）。
- HIP 以外の backend ではこの名前を読む実装がない。HIP の gfx12 以外で優先 stream を使うには、環境変数を空でない値にし、`atoi` が 0 以外を返す必要がある（`engine/src/core/mtp.cpp:623-646`）。
- `hipDeviceGetStreamPriorityRange` が成功し、続く `hipStreamCreateWithPriority` も成功したときに限り優先 stream が使われる。どちらかが失敗すると通常 stream の作成に進む（同 `:640-646`）。

## 実行時の詳細

`MtpDrafter::load` が GPU バッファを確保した後、`cs_` を作る時点で `getenv` を評価する。対象変数自体は `static` に保存されないため、同一プロセスでも後続の `load` はその時点の環境値を読み直す。一方、未設定・空文字時に使う GPU 世代判定器 `gfx12_dev` は関数内 static で、device ordinal ごとに最初の probe 結果を保存する。環境を実行中に変更して後続 load へ反映する場合も、明示値が設定されればそれが使われ、unset / empty の GPU 判定は probe 済み device では再取得されない（`engine/src/core/mtp.cpp:623-639`、`engine/include/strata/core/per_device_flag.hpp:13-30`）。

優先が有効なら `hipDeviceGetStreamPriorityRange` から得た `hi` を渡して `hipStreamCreateWithPriority(&cs_, hipStreamNonBlocking, hi)` を呼ぶ。`prio` が立たなければ `cudaStreamCreateWithFlags(&cs_, cudaStreamNonBlocking)` で `cs_` を作る。以降、MTP の prefill / draft graph の capture と graph launch は `cs_` を使用する（`engine/src/core/mtp.cpp:640-646,1577-1656,1936-1948`）。この設定は MTP の有効化や draft の値・選択を直接変更する分岐ではなく、stream 作成時の指定を選ぶ。

## ログと測定値

優先 stream を選んだことや、優先 stream 作成に失敗して通常 stream に fallback したことを知らせる専用ログはない。優先度取得・作成 API の失敗は `cudaGetLastError()` を呼んでクリアし、通常 stream 作成へ進む。通常 stream も作れなければ `err = "mtp: stream"` として load が失敗し、generate は `strata generate: %s%s%s` を stderr に出して終了コード 1 を返す（`engine/src/core/mtp.cpp:640-646`、`engine/src/program/generate.cpp:8264`）。

ソースコメントには R9700 / UD-Q4_K_XL で draft wall が 1 window あたり 5.8 ms から 3.5 ms になったという記載があるが、コメントが参照する `notes-latency.md` は checkout 内で確認できなかったため、測定値としては採用しない（`engine/src/core/mtp.cpp:624-628`）。

## 根拠

- `engine/src/core/mtp.cpp:613-646` — CUDA と HIP の別分岐、HIP の値判定、優先 stream 作成と通常 stream fallback。
- `engine/src/core/mtp.cpp:345-356,623-646` — MTP load と backend macro 条件。
- `engine/src/core/mtp.cpp:1577-1656,1936-1948` — 選択された `cs_` を使う graph capture / launch。
- `engine/src/program/generate.cpp:8243-8265` — `--spec` 条件と MTP load 呼び出し。
- `engine/include/strata/core/per_device_flag.hpp:13-30` — device ごとの既定値 probe の cache。
- `engine/include/strata/kernels/gfx_arch.hpp:15-19,41-42` — gfx12 arch 名の判定。
- `engine/cmake/backends/hip.cmake:6-26` — gfx906 互換 build の macro 定義。
