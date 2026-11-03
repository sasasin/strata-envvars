# `FNX_PF_STAGE_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の opt-in `strata-split` エンジンが prompt prefill 用に確保する expert staging buffer の容量上限を MiB 単位で指定します。各 GPU で、slot に載っていない expert のうち最大 layer 分の重さを求め、その値とこの上限の小さい方を stage 1 個分の容量にします。stage は二重バッファです。

この設定が使われるのは split engine のみです。split engine は Linux の CUDA または HIP ビルドで `STRATA_BUILD_SPLIT=ON` の場合に限りビルド対象になり、通常の Strata 実行経路には含まれません（`src/split/CMakeLists.txt:1-5,20-29,64-80`）。

## 値と判定

`fnx::env_int()` が `std::getenv()` で値を読み、10 進の符号付き整数として文字列全体を解析します。変換は `strtoll(..., 10)` で、先頭・末尾の空白、空文字、末尾の余分な文字、小数、範囲外整数は受理されません。先頭の `+` または `-` は受理されます。未設定の場合だけ既定値を返します（`src/split/src/env.hpp:15-21,33-40`）。

| 値 | 結果 |
|---|---|
| 未設定 | 384 MiB を上限として使う |
| `0` | stage 容量は 0。stage buffer を確保せず、staging は使われない |
| 1 以上の整数 | 指定 MiB と、slot 外 expert の最大 layer 重量の小さい方を使う |
| 負の整数 | `FNX_PF_STAGE_MIB: want MiB >= 0, got <値>` の `std::runtime_error` |
| 空文字、空白を含む値、整数以外、long long の範囲外 | `FNX_PF_STAGE_MIB: '<値>' is not a whole number` の `std::runtime_error` |

非負値に明示的な上限検査や clamp はありません。MiB 値を `size_t` に変換して `<< 20` した後、最大 layer の必要量と比較します。したがって通常の範囲では指定値が上限になりますが、極端に大きな値に対する size_t 変換・シフトの上限動作を Strata は検査していません（`src/split/src/prefill.cu:914-926`）。

## 有効になる条件

- model の card に `ExpertCache` slots があること。slots がなければ `pf_stage_bytes()` は環境変数を読む前に 0 を返し、stage は確保されません（`src/split/src/prefill.cu:914-917,832-852`）。
- stage 容量が 0 より大きいこと。容量が 0 なら `prefill_stages()` は確保を飛ばし、prompt 経路の staging 条件を満たしません（`src/split/src/prefill.cu:929-940`）。
- prefill token 数が `FNX_PF_STAGE_ROWS` の値以上であること。`FNX_PF_STAGE_ROWS` は同じ Engine 初期化時に読み、既定値は 2048、許容範囲は 0..INT32_MAX です。これより短い prompt は expert を RAM 上の元位置から chunk ごとに読み、stage を使いません（`src/split/src/prefill.cu:832-836,989-991`）。
- split engine の prefill prompt 経路が呼ばれること。通常の session prompt は `e_.prefill(seg, ...)` に渡されます（`src/split/src/session.cpp:253-265`）。`fnx_run` の `mtp` mode では `FNX_PREFILL` が非 0 で prompt が 1 token より長い場合に `Engine::prefill()` を呼びます。`FNX_PREFILL` が 0 のその mode では prompt を window ごとに処理するため、この staging 判定は通りません（`src/split/tools/fnx_run.cpp:1003-1025`）。

容量 0 の場合、staging 用 buffer は割り当てられません。正の容量でも、個別 layer の slot 外 expert が stage に収まらない分は RAM 上の元位置から参照されます。各 layer で入る expert 数は `min(slot 外 expert 数, stage_bytes / (gu_stride + down_stride))` です（`src/split/src/prefill.cu:1088-1127`）。

## 実行時の詳細

Engine 構築中に容量を計算し、stage が必要なら各 card に同容量の二つの buffer を確保します。非 arena 経路では `prefill_stages()` が engine 構築中に呼ばれます。arena 経路では VRAM の必要量見積もりに `2 * pf_stage_bytes(c)` を使い、expert を置き直すたびに見積もり直した後、stage を確保します（`src/split/src/engine.cu:299-316,340-348`; `src/split/src/prefill.cu:929-940`）。

環境値は `static` に cache されず、`pf_stage_bytes()` の計算ごとに読み直されます。確保後は `p.stage_bytes` に容量が保持され、その Engine の prefill 中に値を読み直しません。従って Engine 構築後の環境変更はその Engine の stage 容量を変えません（`src/split/src/env.hpp:34-40`; `src/split/src/prefill.cu:914-940,1097-1101`）。CLI 引数や別環境変数による `FNX_PF_STAGE_MIB` 自体の上書きはありません。`FNX_PF_STAGE_ROWS` と `FNX_PREFILL` は別々に staging の利用条件を左右します。

stage に入れる expert の参照表を作り、layer ごとに copy stream で次の layer の expert を二重 buffer へコピーします。容量が足りない expert は host 上の元アドレスのまま表に残ります（`src/split/src/prefill.cu:1088-1138`）。`FNX_PF_TIMING` が有効な場合は stderr に `prefill on card %d: passes of %d chunks, stages of %zu MiB` と確保容量を表示します（`src/split/src/prefill.cu:939-940`）。

負値・不正表記は例外経路です。`fnx_run` のトップレベル例外 handler は stderr に `fnx_run: <例外内容>` を出し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1365-1372`）。stage buffer の GPU メモリ確保に失敗すると、`palloc()` は `prefill: cudaMalloc of <MiB> MiB on card <番号>: <GPU error> (<空き MiB> MiB free; the prompt path holds <MiB> MiB there already)` の例外を送出します（`src/split/src/pf_common.cuh:44-62`）。arena では stage 容量が VRAM の必要量見積もりに含まれ、再配置を 8 回試しても不足する場合は `FNX_ARENA: VRAM still short after placing the experts again 8 times` で失敗します（`src/split/src/engine.cu:299-316`; `src/split/src/prefill.cu:933-940`）。

## 根拠

- 読み取り、非負チェック、MiB 換算、slot 外 expert 重量の上限: `src/split/src/prefill.cu:914-926`。
- 整数の未設定時既定・厳密な全体解析・無効値例外: `src/split/src/env.hpp:15-21,33-40`。
- slots 条件、stage rows と初期化: `src/split/src/prefill.cu:832-852,929-940`。
- prompt 長による staging 判定: `src/split/src/prefill.cu:989-991`。
- stage への expert 配置、収まりきらない expert の in-place 参照、layer copy: `src/split/src/prefill.cu:1088-1138`。
- split build 条件: `src/split/CMakeLists.txt:1-5,20-29,64-80`。
- `FNX_PREFILL` の分岐例: `src/split/tools/fnx_run.cpp:1003-1025`。
- session の prompt を Engine に渡す箇所: `src/split/src/session.cpp:253-265`。
- arena における容量見積もり・再配置・stage 確保: `src/split/src/engine.cu:299-316,340-348`。
- `FNX_PF_TIMING` の容量ログ: `src/split/src/prefill.cu:939-940`。
- `fnx_run` の例外ログと終了コード: `src/split/tools/fnx_run.cpp:1365-1372`。
- stage buffer の GPU 割当て失敗メッセージ: `src/split/src/pf_common.cuh:44-62`。
