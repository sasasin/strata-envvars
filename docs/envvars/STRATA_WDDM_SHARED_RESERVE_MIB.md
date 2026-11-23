# `STRATA_WDDM_SHARED_RESERVE_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows の `FileExpertSource::pin_cache_complement` が、GPU キャッシュ外の expert を RAM 予算内で保持する処理に適用する WDDM shared（non-local）segment の予備量を MiB 単位で指定する。DXGI で得た各 GPU の残量からこの予備量を差し引き、その結果を既存 RAM 予算の上限にする。設定値は resident RAM mode 自体を有効化せず、明示または自動で決まった正の予算を縮めるだけである（`engine/src/core/expert_source.cpp:4044-4057,4068-4103`）。

## 値と判定

環境から読むのは Windows 分岐内で DXGI 残量が少なくとも一台分取得できた後だけ。`getenv` が null、または指す文字列の先頭が NUL の場合は `2048` を使う。空文字は「設定値 0」ではなく既定値扱いになる（`engine/src/core/expert_source.cpp:4079-4094`）。

それ以外は `std::strtoull(r, nullptr, 10)` の結果を `1 << 20` 倍する。`endptr` を渡さず、`errno` も確認しないため、文字列全体の妥当性検査や範囲検査はない。10 進数字の先頭部分を読み、後続文字は判定に使わない。従って `12junk` は 12 MiB、`true` や `0anything` は 0 MiB になる。標準変換の先頭空白・符号もそのまま受け付け、負数や変換範囲超過も拒否・fallback されず、変換後の左シフトで `uint64_t` の範囲を超える値は折り返し得る。大文字小文字の比較はしない（同上）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・例 |
|---|---|---|---|
| Windows 分岐で DXGI 残量を取得 | 2048 MiB | 10 進数字の先頭部分を MiB として使用（`1` → 1 MiB、`12junk` → 12 MiB） | 空文字は既定値。`true`、`false`、`0anything` は変換数値 0 MiB。負数・過大値は検証されず、シフトで折り返す場合がある |
| 非 Windows、予算なし、pin 無効、GPU 条件不成立、または DXGI 残量を取得できない | 変数を読まない | 該当なし | 該当なし |

変換された予備量が GPU 残量以上なら上限は 0、そうでなければ `残量 - 予備量`。この上限を現在の RAM 予算に適用し、予算より小さい場合だけ予算を引き下げる（`engine/src/core/expert_source.cpp:137-140,4094-4103`）。

## 有効になる条件

- `_WIN32` 分岐であること。DXGI の非 Windows 実装は失敗を返す（`engine/src/core/expert_source.cpp:4068-4069`; `engine/src/platform/memory.cpp:190-194`）。
- `pin_cache_complement` に正の RAM 予算が渡されること。たとえば `--resident-budget-gib N`（`N > 0`）または自動 RAM copy の正の予算が対象になる。`--resident-budget-gib 0` / `--ram-experts-gb 0` と `--ssd-experts` は resident 予算を 0 にするので対象外（`engine/src/program/generate.cpp:4231-4252,11998-12001`）。
- `pin` が true であること。予算指定時は `STRATA_RESIDENT_PIN=0` が完全一致すると pin を無効にする。未設定またはそれ以外の値では pin が有効（`engine/src/program/generate.cpp:4246-4251`; `engine/include/strata/core/resident_ram_copy.hpp:11-15`）。
- `cudaGetDeviceCount` が成功し、デバイス数が 2 以上であること。デバイス数取得失敗時は 0 として扱われ、単一 GPU ではこの予算調整を行わない（`engine/src/core/expert_source.cpp:4079-4083`）。
- 少なくとも一台について、CUDA device property 取得と `gpu_shared_memory_budget` が成功し、DXGI shared budget が正であること。取得できた GPU のうち最小の `budget - usage` を使う。個々の失敗理由は出力せず、すべて失敗すれば環境変数を読まず予算を変更しない（`engine/src/core/expert_source.cpp:4082-4094`; `engine/src/platform/memory.cpp:112-151`）。
- 既存の RAM / Windows commit 上限による clamp が先に行われ、その後にこの WDDM 上限が適用される。従ってこの変数で既に小さくなった予算を増やすことはできない（`engine/src/core/expert_source.cpp:4044-4067,4094-4103`）。
- `--resident-experts` は既定で予算 0 の全量 resident 経路なので、それだけではこの分岐に入らない。soft resident の再試行は `kResidentWhatFits` 予算を渡すため、他の条件を満たせば適用される（`engine/src/program/generate.cpp:4216-4223,12012-12019`; `engine/include/strata/core/expert_source.hpp:787-799`）。

## 実行時の詳細

`generate` の resident copy 構築時に `pin_cache_complement` が呼ばれ、通常の RAM / commit 上限を処理した後、Windows かつ pin 有効の場合に CUDA デバイスを列挙する。各デバイスの LUID を使って `gpu_shared_memory_budget` が DXGI adapter を探し、non-local segment の `Budget` と `CurrentUsage` を取得する。成功したデバイスの残量の最小値から環境変数の予備量を引き、RAM 予算をそれ以下に切り詰める。対象外の expert は既存の mapped file / file tier に残る（`engine/src/core/expert_source.cpp:4068-4103,4130-4185`; `engine/src/platform/memory.cpp:112-151`）。

値は関数内で `getenv` され、static cache はない。リクエストごとの評価ではなく resident copy の構築時に読む。実行中に環境を変更しても作成済みコピーには反映されない。soft resident の二回目の試行に進む場合は関数が再度呼ばれるため、その呼び出しでは再読込される（`engine/src/core/expert_source.cpp:4091-4094`; `engine/src/program/generate.cpp:12000-12019`）。

この変数は CLI 予算や自動予算の値を置き換えない。DXGI で残量を得られない場合はこの調整を飛ばし、元の予算処理を続ける。上限が 0 になった場合、budget 経路で保持する expert はなくなり、残りはファイルから読む経路になる。soft の「空きに収まる分だけ」試行で一つも保持できない場合は `pin_cache_complement` が false を返し、呼び出し元が mmap/file tier へ fallback する（`engine/src/core/expert_source.cpp:4091-4103,4130-4147`; `engine/src/program/generate.cpp:12012-12027,12124-12135`）。

## ログと測定値

DXGI 残量を取得できたときは stderr に次の行を出す（予算を切らない場合も出力する）。

```text
FileExpertSource: WDDM shared segment: %.2f GiB left on the tightest GPU, %.2f GiB kept for the engine's later mapped buffers
```

切り詰めが実際に起きた場合だけ、続けて次の行を出す。`%.2f` は実行時の GiB 値で、後半の文字列は固定文言である（`engine/src/core/expert_source.cpp:4095-4102`）。DXGI 残量取得に失敗したとき、この変数に関する理由ログはない。対象変数の効果を比較した測定値は、調査対象ソースで確認できなかった。

## 根拠

- 全参照の検索では、値を読むのは `engine/src/core/expert_source.cpp:4092` の一箇所。設定表 `docs/SETTINGS.md:463` と設定登録データ `terminal/data/settings-register.json:50600` の記載は候補確認にのみ使い、動作根拠にはしていない。
- 値変換・予算上限: `engine/src/core/expert_source.cpp:137-140,4091-4103`。
- Windows DXGI shared budget 取得: `engine/src/platform/memory.cpp:112-151,190-194`。
- 呼び出しと CLI / 自動予算の条件: `engine/src/program/generate.cpp:4216-4252,11998-12019`。
- 後続の予算適用と fallback: `engine/src/core/expert_source.cpp:4130-4185`; `engine/src/program/generate.cpp:12124-12135`。
