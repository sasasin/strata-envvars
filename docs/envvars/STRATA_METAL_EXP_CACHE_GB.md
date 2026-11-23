# `STRATA_METAL_EXP_CACHE_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この値は `strata-hy4-metal` の cold-expert 経路で確保する GPU expert LRU cache の初期 budget（10進 GB）を指定する。未指定時の自動 budget を置き換え、確保 slot 数に影響する。キャッシュは expert 本体の読み込み先であり、通常の非 cold-expert 経路ではこの環境変数を読まない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:637-659, 1168-1172`）。

## 値と判定

`Runner::init` 内で `getenv` し、ポインターが非 null かつ先頭文字が NUL でない場合に `atof(env_gb) * 1e9` を `size_t` にキャストする。従って未設定と空文字は自動 budget のまま。`atof` は数値の prefix を読み、末尾までの妥当性検証をしない。たとえば `1.5junk` は 1.5 GB、`0anything`・`true`・数値 prefix のない文字列は 0 GB 相当となる。先頭空白は `atof` の数値変換に従い、`1` と `1GB` はいずれも 1 GB 相当。小数 byte は `size_t` への変換で切り捨てられる。値の明示的な範囲検査はない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:643-644`）。

| 条件 | unset / 空文字 | 設定時に有効になる値 | 値の解釈・後段の扱い |
|---|---|---|---|
| cold-expert 経路 | 自動 budget。working set に空きが 4 GiB 超あれば `work_set - used_now - 4 GiB`、それ以外は 2 GiB | `atof(value) * 1e9` が `size_t` の範囲内にある正の値（例 `1`, `1.5`, `1GB`） | 10進 GB を byte に換算して自動 budget を置換。その後に追加 KV 分、Metal buffer 上限、expert 総量で上限を適用し、最低 512 expert 分まで引き上げる |
| cold-expert 経路 | 同上 | `0`, `0anything`, `true`, `abc` | `atof` が 0 を返す入力は一旦 0 byte。その後、最低 512 expert 分まで引き上げられる |
| cold-expert 経路 | 同上 | 負値・`nan`・`inf` など | `atof` がこれらを数値として返しても、範囲外または非有限値を整数へ変換する結果は C++ の浮動小数点整数変換の範囲外であり、ソースは扱いを定義・検査していない。依存できる値として扱えない |
| 非 cold-expert 経路 | 参照されない | 参照されない | `Model::load` が `cold_experts` を false にした場合、`Runner::init` の該当分岐を通らず変数を読まない |

budget は厳密な確保量ではない。cold-expert cache の各 slot は最大 expert 本体サイズを 4096 byte 単位に切り上げた大きさで、算出 budget を slot サイズで割って slot 数を決める。budget の下限は 512 slot 分で、これは直前に適用した各上限を超える場合もある（`engine/src/hy4flash/metal/hy4_metal_main.cpp:639-659`）。

## 有効になる条件

- 対象は `engine/src/hy4flash/metal/hy4_metal_main.cpp` の Apple Silicon Metal runner（ファイル先頭の runner 説明と `engine/src/hy4flash/metal/build_mac.sh:47`）。CUDA/HIP 実装ではない。
- `Model::load` で cold-expert モードになる必要がある。これは `--cold-experts` による強制、またはページ丸めしたモデル長が Metal の最大 buffer 長を超える場合、または working set が正かつファイルサイズがその 88% を超える場合に成立する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:214-255, 1543-1545`）。
- モデルの load に成功し、続いて offline run または `--serve` の runner 初期化まで進む必要がある。`--load-only` は runner 初期化より前に終了するため、この変数を読まない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1617-1636, 1762-1765`）。
- `--serve` では session reuse 時に `--conversation-slots`、`--conversation-cache-mib`、spill 設定から追加 KV 予算を計算し、環境変数で指定した budget からその分を差し引く。これらは cache budget を上書きする指定ではない（`engine/src/hy4flash/metal/hy4_metal_serve.h:222-232`; `engine/src/hy4flash/metal/hy4_metal_main.cpp:647-652`）。
- `--chunk` などの CLI 引数に cache GB を直接指定する項目はなく、この変数と同名の CLI override もない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1609`）。

## 実行時の詳細

モデル読み込み時に cold-expert 条件を判定し、モデルが cold なら section 1 の trunk のみを map/wrap し、expert section は LRU cache と `pread` で扱う。続く `Runner::init` は `g.cold_experts` のときに限って環境変数を読み、slot cache を確保し、hotness 順の最大 512 experts を起動時に先読みする。値は初期化中に一度評価され、cache buffer と slot 数に反映されるため、実行中に環境を変更しても既存 Runner の割当は変わらない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:214-255, 637-679`）。

各層の MoE expert 選択後、cold-expert 経路では必要 expert を確認し、miss 分を空きまたは LRU slot に `pread` してから、Metal dispatch に cache buffer を渡す。非 cold-expert 経路では元のモデル buffer を渡す（`engine/src/hy4flash/metal/hy4_metal_main.cpp:898-960, 1168-1172`）。serve は起動時に Runner を一つ初期化して要求処理に使う（`engine/src/hy4flash/metal/hy4_metal_serve.h:219-243`）。

予算後の cache allocation は `cx.alloc` に渡されるが、この呼び出し箇所に環境値の妥当性エラー用分岐はない。初期化が false を返した場合、offline run は stderr に `init: <error>` を出して終了コード 1、serve は protocol stdout に `ERR init: <error>` を出して戻り値 1 となる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:576-577, 659, 1762-1765`; `engine/src/hy4flash/metal/hy4_metal_serve.h:239-242`）。

## ログと測定値

cold-expert モード選択時はモデル load で `[load] 32GB cold-expert mode: wrapped trunk ...` を stderr に出す。cache 初期化時は、設定値そのものではなく実際の slot 総量・slot 数・slot サイズ・先読み数を `[cold-experts] LRU cache %.2f GB (%d slots x %.2f MB, preloaded %d)` の形式で stderr に出す。cold-expert 経路を通らない場合、環境変数に関するログはこのソースにはない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:253-254, 678-679`）。資料にこの変数の測定値は見つからない。

Strata の `docs/SETTINGS.md:160` はこの変数の backend を「NVIDIA and AMD」と記しているが、確認した読み取り実装は Metal runner にあり、ソース上の適用先と一致しない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:214-255` — cold-expert モードの判定とモデル mapping。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:637-679` — budget の既定・環境変数読取・補正・割当・先読み・ログ。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:898-960, 1168-1172` — LRU miss の読み込みと dispatch buffer の選択。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1613, 1635-1636, 1762-1765` — CLI、load-only、runner 初期化と失敗時の終了。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:219-243` — serve 側の初期化とエラー出力。
- `engine/src/hy4flash/metal/build_mac.sh:47` — Metal runner の build 対象。
