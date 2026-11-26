# `STRATA_PLE_COPY_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプト処理で PLE（prompt lookup embeddings）の IQ4_NL raw row を device に送るとき、compute stream とは別の non-blocking stream を使うかを制御する。別 stream が使われると、次 chunk の raw row の DMA を layer 0 の計算と重ね、compute stream は PLE dequant の時点で upload 完了を待つ。raw row と dequant の経路が成立しない場合はこの変数による stream 分離も行わない。`engine/src/prefill/prefill.cpp:298-303,4544-4569`。

## 値と判定

`ple_copy_stream_on()` は最初の呼び出し時に `std::getenv` の結果を関数内 `static const bool` に保存し、値が非 null かつ `v[0] == '1'` の場合だけ true とする。文字列全体や数値としての妥当性は検査しない。したがって unset と空文字は false、`1`・`10`・`1anything` は true、`0`・`0anything`・`true`・` 1` は false。大文字小文字の変換や空白除去もない。`engine/src/prefill/prefill.cpp:300-303`。

| 条件 | unset（自動設定前） | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| 通常の判定 | false | 先頭文字が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `0anything`, `true`, ` 1` など先頭文字が `1` 以外 |
| CUDA のアーキテクチャ別既定値が適用された場合 | 対象表にあれば `1` が設定される | 明示値は上記と同じ | 明示値は上記と同じ。空文字や `0` も「設定済み」として既定値注入を抑止する |

## 有効になる条件

- PLE のプロンプト経路が実行されること。PLE が ready で、現在の prefill stage が layer 1 を含む場合に PLE 行を gather する（`engine/src/prefill/prefill.cpp:4327-4335`）。
- 別 stream の upload は `m.ple_compact[ple_buf]` が true の場合に限る。raw IQ4_NL 経路は `STRATA_PLE_COMPACT` が有効で、pinned host buffer と `ple_raw_dev` が使え、`gather_raw_iq4nl` が成功した場合に選ばれる。それ以外は通常の float 行 gather に戻る（`engine/src/prefill/prefill.cpp:4346-4354`）。
- `ple_raw_dev` の確保に失敗した場合、raw gather 条件が成立せず通常 gather になるため、この変数だけでは別 stream upload は起きない（`engine/src/prefill/prefill.cpp:2606-2610,4346-4354`）。
- `ple_copy` stream または `ple_raw_free` event の作成に失敗すると stream を破棄し、compute stream upload に fallback する。これは stderr に記録される（`engine/src/prefill/prefill.cpp:2612-2620`）。
- CUDA build では、起動時に可視 GPU がすべて同一 compute capability の場合、sm_86・sm_89・sm_120・sm_121 の既定値表がそれぞれ `STRATA_PLE_COMPACT=1` と本変数を含む。`STRATA_SM86_PERF=0` は sm_86 表を抑止する。sm_89・sm_120・sm_121 表は `STRATA_SM89_PERF=0` / `STRATA_SM120_PERF=0` / `STRATA_SM121_PERF=0`、または `STRATA_DEFAULTS=026` による既定値表停止で適用されない（`engine/src/program/generate.cpp:4421-4449`, `engine/src/core/nv_defaults.cpp:41-43,62-66,75-83,94-99,104-107,120-128,176-180,206-214`）。
- この既定値表は CUDA runtime を使う起動処理の同一 capability 条件下で適用される。混在 compute capability の複数 GPU ではこの表の適用を skip する（`engine/src/program/generate.cpp:4421-4453`）。HIP build ではこの CUDA 既定値注入ブロックはコンパイル対象外（`engine/src/program/generate.cpp:4421`）だが、環境変数の判定・prefill 側の stream 経路は `prefill.cpp` にある。
- 既定値適用は環境変数が null の場合だけ行われる。利用者が空文字や `0` を設定していれば、その値を上書きしない（`engine/src/core/nv_defaults.cpp:222-233`）。CLI 引数による個別の上書き箇所は確認できなかった。

## 実行時の詳細

CUDA の生成処理は prefill の各 switch を読む前に GPU capability を調べて既定値を環境へ設定する（`engine/src/program/generate.cpp:4421-4449`）。`apply_nv_defaults()` は未設定の変数だけに `setenv(..., 0)`（Windows は `_putenv_s`）で `1` を設定する。既定値を一つ以上設定した場合は `strata: <arch>: ... speed switches on by default ...` の一覧ログを stderr に出す（`engine/src/core/nv_defaults.cpp:222-255`）。

prefill 初期化中に `ple_copy_stream_on()` が評価され、結果は関数内 static に cache される。後から環境値を変えても同一プロセスでは再評価されない（`engine/src/prefill/prefill.cpp:300-303,2612-2616`）。stream と event の作成に成功すると、raw upload は `ple_copy` stream で行い、compute stream は `ple_copied` event を待ってから `ple_iq4nl_dequant` を実行する。`ple_raw_free` event は dequant 完了を示し、次 chunk が raw device buffer を上書きする前の待ち合わせに使われる。別 stream がない場合は upload と dequant を compute stream で行う（`engine/src/prefill/prefill.cpp:4544-4569`）。prefill run の終了時にも copy stream を drain し、release 時に同期・破棄する（`engine/src/prefill/prefill.cpp:4278,1832-1839,1858-1860`）。

upload、event wait/record の API 呼び出しが失敗した場合は `err` に `prefill: the PLE rows' upload failed: ` と runtime error string を設定して、その処理を失敗させる（`engine/src/prefill/prefill.cpp:4552-4568`）。stream/event 作成失敗だけは通常 stream への fallback で継続する。

## ログと測定値

stream/event 作成失敗時の stderr は `prefill: STRATA_PLE_COPY_STREAM=1: the upload stream could not be created, the PLE rows go up on the compute stream`。CUDA の既定値表を適用した場合は前節の起動時一覧ログにも変数名（`PLE_COPY_STREAM`）が含まれる。通常値の個別有効ログは確認できなかった（`engine/src/prefill/prefill.cpp:2617-2620`, `engine/src/core/nv_defaults.cpp:249-255`）。

`docs/DETAILS.md:1817,1826` は CMP 170HX 上での四変数（`STRATA_PLE_COMPACT`、`STRATA_PLE_COPY_STREAM`、`STRATA_EMBED_VRAM`、`STRATA_DEQUANT_SIDE`）併用時について、prompt が `+2.2 %`〜`+2.6 %` と記載し、この組合せを bitwise としている。個別の本変数単独の測定値ではないため、その性能差を本変数単独の効果とは扱えない。

## 根拠

- `engine/src/prefill/prefill.cpp:298-303` — 値の取得、先頭文字判定、static cache。
- `engine/src/prefill/prefill.cpp:2606-2620` — raw buffer・stream/event の作成と失敗時 fallback。
- `engine/src/prefill/prefill.cpp:4327-4354,4544-4569` — PLE 条件、raw gather、upload と dequant の順序。
- `engine/src/program/generate.cpp:4421-4453`、`engine/src/core/nv_defaults.cpp:41-43,62-66,75-83,94-99,104-107,120-128,176-180,206-214,222-255` — CUDA 既定値表の適用条件、上書き優先、起動ログ。
- `docs/DETAILS.md:1817,1826` — 四変数併用時の資料記載。
