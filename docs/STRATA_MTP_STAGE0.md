# `STRATA_MTP_STAGE0`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数動作は扱わない。

## 役割

複数 GPU の layer split で pipelined decode を使うとき、MTP drafter を最後の stage の GPU ではなく最初の stage の GPU に配置するかを決めます。既定の配置は最後の stage です。最初の stage に移すと、pipeline 中の drafter の処理を、window の処理が終わって空いている最初の GPU で行う構成になります。drafter の source rows と draft head の rows は別 GPU へコピーされます。

この環境変数は GPU や stage を直接指定するものではなく、配置変更の有効・無効を選びます。配置変更の実体は `mtp_first` を使った drafter のロード先、session、head、K/V state、行バッファーの選択に反映されます（`src/program/generate.cpp:3649-3654,4621-4630,7918-7930`）。

## 値と判定

変数を読む箇所は一つです。条件を満たす経路に入った時点で `std::atoi()` を呼び、戻り値が 0 でなければ配置変更を有効にします（`src/program/generate.cpp:3649-3654`）。文字列全体の厳密な数値検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | backend の既定値を使う |
| `0`、空文字、数字で始まらない文字列 | `atoi` の結果が 0 となり、配置変更しない |
| `1`、`-1`、その他 `atoi` の結果が 0 以外の文字列 | 配置変更する |

`atoi` は先頭の空白と符号を許容し、数値として読める先頭部分を変換します。したがって ` 1tail` や `+1` も有効、`1tail` も有効、`tail1` は無効です。`-0` は無効です。空文字は未設定と異なり明示値ですが、変換結果は 0 です。設定値の読み取り結果は static cache されず、配置判定の lambda が実行される時に一度読みます。

明示値は既定値を上書きしますが、後述する適用条件を省略するものではありません。たとえば `STRATA_MTP_STAGE0=1` でも pipeline が 2 window 未満なら配置変更しません。

## 有効になる条件

実際の配置変更には、次の条件が必要です（`src/program/generate.cpp:3500-3506,3649-3654`）。

- `--mtp` が指定され、`--spec` が 2 以上。
- MTP drafter 用の subset vocabulary file がある。`--mtp-draft-vocab` 指定時はそのパス、未指定時は MTP ディレクトリー内の `draft_vocab.bin` を確認します。
- `STRATA_MTP_FULL_HEAD` が先頭文字 `1` でない。先頭文字だけを比較し、該当する場合は `mtp_first_ok` 自体が false になります。
- `--serve` で、layer split が 2 stage 以上（各 stage が別 GPU）、`--pipeline-windows` の有効値が 2 以上、`--batch` が 0。pipeline の適用チェックで `--peer-device` や helper cache が指定されていないことも必要です。3 stage 以上では `--adapt-async` も併用できません。
- `STRATA_MTP_STAGE0` の変換結果が非 0、または未設定時の backend 既定値が on。

未設定時の backend 既定値は、HIP build で現在の GPU が gfx1200 または gfx1201 の場合に on、それ以外は off です。HIP では `cudaGetDevice` / `cudaGetDeviceProperties` で現在 device を調べ、`gfx_arch_is_gfx12_wmma()` が gfx1200 / gfx1201 を判定します。HIP 以外の build では既定 off です（`src/program/generate.cpp:1630-1648`, `include/strata/kernels/gfx_arch.hpp:30`）。明示値があると既定値は使わないため、上の適用条件を満たせば他の GPU でも選択できます。

自動 pipeline 設定は別途 backend 条件を持ちます。`--pipeline-windows` を自動選択する HIP 経路では gfx12 以外で pipeline 自体が off になります。明示的に pipeline を要求する場合も `--serve`、stage ごとの GPU、helper cache・peer-device・batch 条件などの適否チェックで無効にされることがあります。この変数は pipeline の有効化そのものを行いません（`src/program/generate.cpp:3507-3525,3527-3545`）。

## 実行時の詳細

`mtp_first` は stage 構成後、MTP drafter のロードより前に決定されます。設定が有効なら MTP drafter のロード時に現在 GPU を最初の stage にし、最初の stage の session を使います。無効なら drafter を最後の stage の GPU / session に置きます（`src/program/generate.cpp:3644-3654,4621-4630`）。

この選択は後続の GPU memory planning にも渡され、最初または最後の stage の空き容量見積もりで drafter を置く側を考慮します（`src/program/generate.cpp:3823-3827`）。pipeline 準備時には drafter の行バッファーを配置先 GPU 上に確保し、verifier や snapshot で drafter の K/V state を最初／最後どちらの stage に関連付けるかも切り替えます（`src/program/generate.cpp:7918-7930,8242-8249,10998-11007,11072-11093`）。

この変数そのものについて値のログ出力は確認できません。pipeline の自動有効化時には「`--pipeline-windows 2 is on by default ...`」という stderr ログがありますが、配置先を表示するログではありません（`src/program/generate.cpp:3523-3525`）。不適用時にこの変数固有の警告を出す処理も確認できません。

## 文書との照合

`docs/MULTI_GPU.md:257-264` は、pipelined decode で drafter を最初の GPU に移す設計、`STRATA_MTP_STAGE0=0` で従来配置を維持すること、および測定値を記載しています。資料の測定は R9700 の複数 GPU 構成での exact-flags A/B、5 組の比較で、2 / 3 / 4 GPU それぞれの decode tok/s と prompt / prose 結果が記されています。これらは文書に報告された特定環境の値であり、今回独自に測定したものではありません。ソースでは未設定時に HIP gfx1200 / gfx1201 のみ既定 on、明示値で切替可能という条件を確認できます。

## 根拠

- `src/program/generate.cpp:1630-1648` — HIP / CUDA での既定値と GPU architecture 判定。
- `include/strata/kernels/gfx_arch.hpp:30` — gfx1200 / gfx1201 の判定。
- `src/program/generate.cpp:3491-3525` — `mtp_first_ok`、subset vocab 条件、自動 pipeline window の条件。
- `src/program/generate.cpp:3644-3654` — `STRATA_MTP_STAGE0` の値変換と優先順位。
- `src/program/generate.cpp:3823-3827,4621-4630,7918-7930` — 配置先が memory planning、drafter load/session、行バッファーに与える影響。
- `src/program/generate.cpp:8242-8249,10998-11007,11072-11093` — pipeline state の stage 選択。
- `docs/MULTI_GPU.md:257-264` — 配置の説明と、条件付きで報告された測定。
