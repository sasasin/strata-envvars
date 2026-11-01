# `DS4_ATTN_SLAB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

DeepSeek V4.1 のチャンク式 prompt path で使う attention slab の行数を指定します。slab は `q_b` / `wo_a` / `wo_b` の dense projection を処理する単位で、対応する `c.q`, `c.o`, `c.o16`, `c.oa`, `c.oa16` の GPU バッファ容量にも影響します。設定が効くのは `strata-dsv41` のモデル load 時に `chunk > 0` となり、`alloc_chunks()` が実行される場合です。通常の windows 式 prompt path では読み取りません（`src/dsv41/ds4_model.cu:2945-2956,3333-3387`）。

## 値と判定

読み取り時に `std::atoi` で整数変換し、その後 `std::max(0, ...)` を適用します。文字列全体の数値検査はなく、先頭の空白と符号の後にある数値部分を読み、後続文字は無視します（例: `12rows` は 12）。数値部分がない文字列や空文字は 0 として扱われます。値の判定と slab 行数は次のとおりです。

| 環境値 | 判定後の値 | 結果 |
|---|---:|---|
| 未設定 | `-1`（未指定） | 自動決定。ただし `DS4_DEFAULTS=026`、統合メモリ GPU、または `STRATA_DS4_A_MB` 指定時は既定 slab に戻る |
| 空文字、非数値、0、負数 | `0` | 既定 slab（`base`）を使う |
| 正の整数 `N` | `N` | `max(64, floor(min(chunk, N) / 64) * 64)` 行を要求する |

したがって正値は 64 行単位に切り下げられ、chunk を上限とします。ただし実装の最小値は 64 行なので、chunk が 64 未満の場合は chunk を超えて 64 行となります。実際の `chunk` は通常 256 以上ですが、`DS4_CHUNK` があると 16 以上で設定できるため、この境界はコード上到達可能です（`src/dsv41/ds4_model.cu:2298-2303`; `src/dsv41/ds4_experts_rule.hpp:117-130`）。

未設定時の自動値は `base` から始まります。RDNA4/HIP で GPU が保持できる routed experts の割合が 0.5 以上なら、最大 `min(chunk, 1024)` 行（64 行単位、最低 64 行）まで slab を増やします。さらに、attention buffers の増分が expert tier に使われない余剰 VRAM 内に収まる場合は最大 `min(chunk, 2048)` 行まで増やします。この余剰判定は `spare_bytes >= ((target - base) * bytes_per_row) * 1.25 + 256 MiB` です。どちらの増加条件も満たさなければ `base` のままです（`src/dsv41/ds4_experts_rule.hpp:117-130`; `src/dsv41/ds4_model.cu:3342-3354`）。

`base` は `STRATA_DS4_A_MB` と GPU 種別、`DS4_DEFAULTS` による別ルールで決まる値です。`DS4_ATTN_SLAB=0` はこの base を選びます（`src/dsv41/ds4_model.cu:3327-3332,3351-3354`; `src/dsv41/ds4_experts_rule.hpp:102-104`）。

## 有効になる条件と優先順位

- CMake の `STRATA_BUILD_DSV41` が有効なときにビルドされる独立実行ファイル `strata-dsv41` の実装です。この CMake option は既定 OFF です（`CMakeLists.txt:906-920`）。
- `chunk > 0` のチャンク式 prompt path が必要です。`--prefill-chunk 0` は chunk を無効にし、`--prefill-chunk N` は chunk の大きさを設定しますが、slab 行数を直接指定する CLI option はありません。`--prefill-chunk` が正値でも `DS4_WINDOWS` や実行モードにより chunk path が選ばれない場合、slab は使われません（`src/dsv41/ds4_model.cu:2224-2232,2293-2303,2945-2956`）。
- `DS4_DEFAULTS=026` の判定は文字列全体を `"026"`, `"0.2.6"`, `"v0.2.6"` と比較し、結果を `static const bool` に cache します。このモードでは `DS4_ATTN_SLAB` が未設定の場合だけ base に戻します。`DS4_ATTN_SLAB` が明示されていれば 0 も正値も優先されます（`src/dsv41/ds4_experts_rule.hpp:16-27,117-122`）。
- 統合メモリ GPU、または `STRATA_DS4_A_MB` が設定されている場合、`DS4_ATTN_SLAB` が未設定なら自動増加を止めて base にします。空文字など未設定以外の値はこの抑止条件には当たらず、数値変換結果（通常 0）が適用されます。正の `DS4_ATTN_SLAB` はこの抑止条件より優先します（`src/dsv41/ds4_model.cu:3322-3341`）。
- expert tier が `--vram-experts 0` 等で無効なら、自動 slab の余剰 VRAM を大きい値として扱い、GPU share は 0 とします。その場合も `DS4_ATTN_SLAB` の明示値は同じく優先されます（`src/dsv41/ds4_model.cu:3342-3354`）。

## 実行時の詳細

変数は `alloc_chunks()` 内で slab buffer を確保するたびに読み、`static` cache はしません。一方 `DS4_DEFAULTS` と `STRATA_DS4_A_MB` は同関数内の static 初期化で初回評価結果が cache されます。slab 行数の決定後、各 GPU でその行数に応じた `c.q`, `c.o`, `c.o16`, `c.oa`, `c.oa16` を確保し、dense projection の slab 処理幅に使います（`src/dsv41/ds4_model.cu:3300-3332,3338-3387`）。

自動増加した slab の割当てに失敗すると、確保を巻き戻し、stderr に `ds4: the automatic attention slab did not fit (%s): trying the 256-row slab` を出して base slab で再試行します。base slab でも失敗した場合は chunk を半分にして再試行し、chunk が 512 以下なら chunk path をやめて windows 式 prompt path へ切り替えます。それぞれ stderr に失敗理由と fallback を出します。明示的な正値による slab が確保できない場合は「自動 slab」fallback の対象ではなく、chunk を縮める再試行に進みます（`src/dsv41/ds4_model.cu:2945-2999`）。

自動増加が成功して `o.verbose` が有効なら、最初の device について stderr に slab 行数と、自動選択理由（RDNA4 の expert share または expert tier 超過分の余剰 VRAM）を出します。自動値が base と同じ場合や明示値の場合、このログは出ません（`src/dsv41/ds4_model.cu:3355-3364`）。

Strata のアプリ／Terminal の「DeepSeek speed-ups」を OFF にすると run config に `DS4_DEFAULTS=026` と `DS4_ATTN_SLAB=0` を書き、旧 base slab を明示します。通常の default ON ではこの設定を除去します（`strata_control/speed_switches.py:3-5,48-55`; `apps/host/server/native-settings.mjs:49-53`）。

## 根拠

- 実読取と値変換、自動 slab の入力値: `src/dsv41/ds4_model.cu:3333-3354`。
- slab の値域、丸め、自動選択、`DS4_DEFAULTS` との関係: `src/dsv41/ds4_experts_rule.hpp:16-27,102-130`。
- chunk path の条件、CLI 値、モデル load 時の割当てと fallback: `src/dsv41/ds4_model.cu:2224-2232,2293-2303,2945-2999,3300-3387`。
- ビルド対象と option の既定: `CMakeLists.txt:906-920`。
- UI/Terminal による設定値の受け渡し: `strata_control/speed_switches.py:3-5,48-55`; `apps/host/server/native-settings.mjs:49-53`。
