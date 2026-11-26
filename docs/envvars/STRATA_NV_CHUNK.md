# `STRATA_NV_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/NVIDIA の裸の `--prefill auto` が使える prompt chunk 上限を、通常の 8192 token から引き上げる設定。GPU の expert cache が貸せる量や RAM guard が許す量まで実際の chunk は小さくなり得る。設定値は `nv_chunk_ceiling_for_vram` を通じて `generate.cpp` の `prefill_auto_max`、`prefill_chunk` に反映される。明示的な `--prefill N`、`--prefill auto:N`、`STRATA_PREFILL_AUTO_MAX` を使う経路はこの NVIDIA 補正対象ではない。`engine/src/program/generate.cpp:4494-4525, 4000-4019`、`engine/include/strata/core/nv_chunk.hpp:21-38`。

## 値と判定

engine は `std::getenv` で値を取得し、`nv_chunk_ceiling` では文字列全体が厳密に `"16"` かを `strcmp` で調べた後、それ以外は先頭文字が `'0'` かだけを調べる。数値変換、空白除去、大文字小文字変換はしない。`STRATA_DEFAULTS=026` 相当が有効なら、この値判定より先に上限 0 を返す。`0` は NVIDIA 固有上限を加えず、engine の裸 auto 既定値 8192 を保つ意味である。`engine/include/strata/core/nv_chunk.hpp:21-29`、`engine/src/program/generate.cpp:4519-4523`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・別扱いになる値 |
|---|---|---|---|
| CUDA/NVIDIA の裸 `--prefill auto`、`STRATA_DEFAULTS` が 0.2.6 でない | 通常は 32768。最小可視 GPU VRAM が 0 より大きく 16.5 GiB 以下なら 0（実効既定 8192） | `"16"` は 16384。先頭が `0` の文字列（`"0"`、`"0anything"`、`"016"` など）は 0。その他（`"1"`、`"16x"`、空文字、`" 0"` など）は 32768 | 0/16 以外を無効値として弾く処理はなく、すべて 32768 扱い |
| `STRATA_DEFAULTS` が `"026"`、`"0.2.6"`、`"v0.2.6"` | 0（8192 を維持） | なし。この master switch が設定値に優先 | `STRATA_NV_CHUNK` の内容にかかわらず旧既定動作 |

VRAM 条件は最小の可視 NVIDIA GPU の総 VRAM で決まり、閾値は `(16 GiB + 512 MiB)` 以下。VRAM を取得できず値が 0 の場合、この特例は適用されない。`engine/include/strata/core/nv_chunk.hpp:23-39`、`engine/src/program/generate.cpp:4503-4519`。なお `terminal/setup.py` のベンチ tip は `STRATA_NV_CHUNK` の先頭が `0` または `16` なら 32768 ではないと扱う簡易判定だが、engine 本体の厳密な parse とは異なる（例: `16x` は setup tip 上は抑制、engine 上は 32768）。これは推奨文の表示判定であり engine 設定ではない。`terminal/setup.py:8968-8986, 8998-9004`。

## 有効になる条件

- NVIDIA/CUDA 相当のビルドで、`STRATA_USE_HIP` と `STRATA_GPU_METAL` が未定義であること。判定コードはこの compile guard 内にある。`engine/src/program/generate.cpp:4494-4496`。
- `--prefill auto` が裸指定であること。`--prefill auto:N`、数値指定、または `STRATA_PREFILL_AUTO_MAX` が設定された auto は `prefill_auto_bare` にならず、この処理で引き上げない。`engine/src/program/generate.cpp:4000-4019, 4495`。
- 可視 GPU 群の最小 compute capability が 8.0 以上、または 7.0（Volta）であること。混在構成では最小 capability が判定に使われる。Turing 7.5 や Pascal 6.x は上限を引き上げない。`engine/include/strata/core/nv_chunk.hpp:41-43`、`engine/src/program/generate.cpp:4506-4521`。
- `STRATA_DEFAULTS` が 0.2.6 token でないこと。該当値は `STRATA_NV_CHUNK` より優先して旧上限に戻す。認識する token は完全一致の `026`、`0.2.6`、`v0.2.6` である。`engine/include/strata/core/defaults_026.hpp:21-30`、`engine/include/strata/core/nv_chunk.hpp:23-25`。
- bare auto の host cap が 0 であること。Windows HIP など別 platform policy の cap が正なら NVIDIA 判定ブロックには入らない。`engine/src/program/generate.cpp:4016-4019, 4495`。
- 複数 GPU (`multi_gpu`) の layer split では、`STRATA_SPLIT_CHUNK16K` が `atoi` で非 0 にならない限り上限を 8192 に戻す。空文字・非数値・`0` は 0 扱い、`1` や `-1` は非 0 扱い。`engine/src/program/generate.cpp:11248-11258`。
- 32768/16384 の候補は expert cache の fit scan と RAM guard の対象になる。RAM が不足すれば 32768→16384→8192 と段階的に下がる。ただし `STRATA_NV_CHUNK` が文字列として厳密に `"1"` の場合は、この RAM step-down 条件を無効にする。`"01"` 等は ceiling 判定では 0 扱いでも、この guard override には該当しない。`engine/src/program/generate.cpp:11267-11301`。

## 実行時の詳細

裸の `--prefill auto` は引数解析時に `prefill_auto_bare` と host cap を決める。GPU 情報を取得した後、起動時の NVIDIA 判定で `STRATA_NV_CHUNK` を読み、可視 GPU の最小 capability と最小 VRAM を調べる。値が正の上限となり GPU 条件も満たすと `prefill_auto_max` と `prefill_chunk` を更新する。`engine/src/program/generate.cpp:4000-4019, 4494-4525`。

値の読み取りは NVIDIA 判定時の getenv と、後段 RAM guard 内の動的な名前による getenv の 2 箇所。関数内 static cache ではない。後段の再読み取りは、`prefill_raise_who == "NVIDIA"` のとき `STRATA_NV_CHUNK` を選び、値が厳密に `"1"` かを確認する。環境を起動後に変更した場合の同期や反映を保証する処理は見当たらない。なお、`STRATA_DEFAULTS` は `qwen_defaults_026()` の関数内 static で初回評価結果を cache する。`engine/src/program/generate.cpp:4503, 11267-11288`、`engine/include/strata/core/defaults_026.hpp:26-30`。

候補上限を設定しても、それがそのまま各 prompt の chunk になるとは限らない。RAM guard が上限を段階的に下げ、後続の fit scan が cache 等に収まる chunk を選ぶ。auto の実 chunk は `strata generate: prompt chunk auto: %lld tokens` と stderr に出る。`engine/src/program/generate.cpp:11267-11301, 11304-11317, 24055-24064`。

## ログと測定値

上限を引き上げると `strata generate: NVIDIA: --prefill auto may take chunks up to ...` を stderr に出す。小容量 VRAM（16.5 GiB 以下）で、対応 capability、変数 unset、`STRATA_DEFAULTS` 無効の場合は、8192 に据え置く理由を `strata generate: NVIDIA (%.1f GiB): --prefill auto stays at 8192 ...` と出す。明示的な `STRATA_NV_CHUNK=0` や `STRATA_DEFAULTS=026` ではこの unset 専用理由ログは出ない。RAM guard が候補を下げた場合は、現在の上限・必要な追加 cache slots/RAM・利用可能 RAM と reserve を示す stderr 行を出す。`engine/src/program/generate.cpp:4520-4532, 11288-11297`。

## 根拠

- `engine/include/strata/core/nv_chunk.hpp:21-46` — 値の解釈、VRAM 特例、対応 compute capability。
- `engine/include/strata/core/defaults_026.hpp:21-30` — `STRATA_DEFAULTS` の認識 token と static cache。
- `engine/src/program/generate.cpp:4000-4019, 4494-4535` — CLI 条件、compile guard、GPU 条件、設定値反映と理由ログ。
- `engine/src/program/generate.cpp:11248-11301, 24055-24064` — layer split、動的 env 名での RAM guard override、chunk fit/選択ログ。
- `terminal/setup.py:8968-9004` — セットアップ画面の助言専用判定。
- `docs/DETAILS.md:1513-1519` — ソースの上限・RAM guard に関する記述との照合。現行挙動の根拠は上記ソース。
