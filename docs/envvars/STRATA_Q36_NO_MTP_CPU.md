# `STRATA_Q36_NO_MTP_CPU`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Qwen3.6-35B-A3B (`qwen35moe`) の専用 engine が、VRAM に全 routed expert を置けない場合に使う MTP 専用配置を抑止します。unset なら、条件が揃うと通常の main layer は全 expert を VRAM に置き、MTP block の expert だけを slot と CPU pool に分けます。設定するとこの配置を選ばず、main layer と MTP block の両方を対象にする通常の hybrid 配置判定へ進みます。

環境変数は `place_experts()` で参照されます。汎用 `strata` は GGUF の architecture が `qwen35moe` のとき専用 engine に切り替わり、単体の `strata-q36` も同じ engine を使います。他の model family ではこの変数を読む経路はありません。

## 値と判定

値の parse はありません。`std::getenv("STRATA_Q36_NO_MTP_CPU") == nullptr` で設定有無だけを確認します。

| 状態 | 判定 |
|---|---|
| unset | MTP 専用配置を選ぶ候補になる。ほかの条件も満たす必要がある |
| `1`、`0`、`false`、任意の文字列 | 設定済みとして MTP 専用配置を抑止 |
| 空文字 | 設定済みとして MTP 専用配置を抑止 |

大文字小文字、数値変換、先頭文字、値の範囲は調べません。環境変数は expert 配置を行う `place_experts()` の実行中に参照されます。そこで配置が決まった後にプロセス環境を書き換えても、配置はやり直されません。

## 有効になる条件

unset 時でも MTP 専用配置 (`mtp_only`) が成立するのは、次をすべて満たす場合です。

- モデルに MTP block がある。
- `--expert-slots` が正値でない（既定値は 0）。
- `--expert-vram` が負値（既定値は -1.0）で、空きVRAMから予備量を引く自動 budget を使う。
- main と MTP を合わせた expert が現行 budget を超える。
- main layer の expert と attention buffer 64 MiB 分が budget 内に入る。最初の判定に入らない場合は attention score buffer を縮め、予備量を 768 MiB から 256 MiB にした余地も判定する。

この条件を満たさなければ、unset でも通常の全層 hybrid 判定または全 expert VRAM 配置になります。特に `--expert-vram` を明示する場合、または `--expert-slots` を正値にする場合は `mtp_only` 判定に入りません。

## 実行時の詳細

unset かつ MTP 専用配置が成立すると、`place_experts()` は main layer の全 expert を VRAM に置き、MTP block の slot 数を残り budget から算出します。MTP block の expert はすべて host memory に保持され、slot にない expert の decode batch 分は CPU pool が処理します。ログには `every main layer's routed experts in VRAM ...; the MTP block's: ... in VRAM, the rest on the CPU pool (its drafts only)` と出ます。MTP block 以外の host expert 領域は確保しません。

変数が設定されている場合は `mtp_only` が立たないため、VRAM が不足すると通常の hybrid 分岐へ進みます。この分岐では各 layer の host expert を確保し、GPU slot と CPU pool を全 layer に適用します。ログは `hybrid experts: ... per layer in VRAM ...` 形式です。全 expert がVRAMに収まれば環境変数の状態にかかわらず全VRAM配置が先に選ばれ、この変数による配置差はありません。

`STRATA_Q36_NO_MTP_CPU` は、packed Q8_0 decode copy を解放する判定にも関係します。通常の「全 expert が解放分を含めれば収まる」条件はこの変数に関係なく有効です。一方、MTP 専用配置を見込んで main expert だけが余裕内に収まるかを見る追加条件は、変数 unset かつ MTP block がある場合に限られます。解放時は stderr に `the packed Q8_0 decode copies ... given back so that every routed expert fits in VRAM` と出ます。`STRATA_Q36_KEEP_PACKED` が設定されていると、この解放処理自体が抑止されます。

ハイブリッド配置のコードは `STRATA_Q36_CPU_POOL` がビルド時に有効な場合だけ利用できます。無効の build では、全 expert がVRAMに収まらないと `the routed experts ... do not fit in VRAM, and this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)` で失敗します。この場合、この環境変数は配置失敗を解消しません。CMake は `STRATA_NATIVE_EXPERTS` が有効な場合に `STRATA_Q36_CPU_POOL=1` を定義します。

## 根拠

- `src/program/generate.cpp:1866-1879` — `qwen35moe` model を Qwen3.6 専用 engine に切り替える。
- `src/qwen35/q36_engine.cu:1934-1951` — `place_experts()`、対象 layer 群、VRAM budget。
- `src/qwen35/q36_engine.cu:1952-1977` — packed-copy 解放条件。MTP専用配置向けの追加条件だけが本変数に依存する。
- `src/qwen35/q36_engine.cu:1978-2001` — MTP専用配置の条件、attention buffer と予備量を縮める fallback。
- `src/qwen35/q36_engine.cu:2003-2017` — 全 expert がVRAMに収まる場合の先行 return。
- `src/qwen35/q36_engine.cu:2019-2045,2057-2128` — CPU pool build 条件、slot/host 配置、MTP専用配置時の差とログ。
- `src/qwen35/q36_engine.cu:2346-2387,2443-2446` — CLI の既定値・`--expert-vram` / `--expert-slots` parsing、および配置関数の呼び出し。
- `CMakeLists.txt:637-640` — `STRATA_NATIVE_EXPERTS` 有効時に Q36 CPU pool を compile definition する。
- `docs/DETAILS.md` には、この環境変数の動作を説明する記述は確認できませんでした。
