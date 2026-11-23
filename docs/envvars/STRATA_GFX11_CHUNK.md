# `STRATA_GFX11_CHUNK`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 版 `strata generate` で、離散 RDNA3 GPU の bare `--prefill auto` が選べる prompt chunk の上限を 8192 から引き上げます。Linux では未設定でも引き上げ規則が有効ですが、Windows ではこの変数による明示的な opt-in が必要です。chunk の上限を設定するだけであり、実際にそのサイズが選ばれるかは context、expert cache の貸出可能量、RAM guard などで決まります（`engine/src/program/generate.cpp:4532-4564`, `engine/src/program/generate.cpp:4571-4586`, `engine/src/program/generate.cpp:11166-11180`）。

## 値と判定

`gfx11_chunk_ceiling` は文字列を数値として parse せず、未設定・空文字、文字列全体が `16` か、先頭文字が `0` かで判定します（`engine/include/strata/core/gfx11_extra.hpp:149-156`）。

| HIP build / 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux、`STRATA_DEFAULTS=026` でなく `STRATA_GFX11_DEFAULTS` が `0` 始まりでもない | 上限 32768 | `16` は 16384。先頭が `0` でないそれ以外（例 `1`, `32`, `true`, ` 16`, `16x`）は 32768 | 先頭が `0` の値（`0`, `00`, `0anything`）は上限を引き上げない。空文字は unset と同じ 32768 |
| Windows、他の条件は同じ | 引き上げなし | 非空かつ先頭が `0` でない値が opt-in。`16` は 16384、それ以外（例 `1`, `32`, `true`, `16x`）は 32768 | 未設定・空文字・先頭が `0` の値は引き上げない |
| どちらの OS でも `STRATA_DEFAULTS=026` または `STRATA_GFX11_DEFAULTS` が `0` 始まり | 引き上げなし | 対象外 | 対象外 |

大文字小文字や空白を検査する規則はありません。`16` との完全一致だけが 16384 になり、`016` や `16x` は 16384 ではありません（後者は先頭 `0` でなければ 32768）。Linux で値が空文字の場合も helper は unset と同じ扱いです。Windows の呼び出し側は空文字を helper に渡す前に除外します（`engine/include/strata/core/gfx11_extra.hpp:151-155`, `engine/src/program/generate.cpp:4572-4579`）。

## 有効になる条件

- `STRATA_USE_HIP` の build が必要です。Linux 側の処理は `STRATA_USE_HIP && !_WIN32`、Windows 側は `STRATA_USE_HIP && _WIN32` のコンパイル分岐です（`engine/src/program/generate.cpp:4532`, `engine/src/program/generate.cpp:4568`）。
- `--prefill auto` を bare で指定する必要があります。`--prefill auto:N` と `STRATA_PREFILL_AUTO_MAX` が設定されている場合は bare auto 扱いにならず、この変数による引き上げを行いません。数値指定の `--prefill N` も対象外です。`STRATA_PREFILL_AUTO_MAX` が空文字でも設定されていれば bare 扱いを外し、その値は `atoll` により 0 として上限 8192 に丸められます（`engine/src/program/generate.cpp:3995-4014`, `engine/src/program/generate.cpp:4533`, `engine/src/program/generate.cpp:4571`）。
- デバイス 0 の GPU が integrated でなく、アーキテクチャ名が `gfx1100`, `gfx1101`, `gfx1102` のいずれかである必要があります。アーキテクチャ名はその文字列の完全一致、または後続が `:` の場合に一致します（`engine/src/program/generate.cpp:4545-4558`, `engine/src/program/generate.cpp:4573-4579`, `engine/include/strata/kernels/gfx_arch.hpp:15-25`）。
- `STRATA_DEFAULTS` が `026`, `0.2.6`, `v0.2.6` のいずれかなら既定値を無効にします。これは初回呼び出し時に static cache されます。また `STRATA_GFX11_DEFAULTS` の先頭文字が `0` でも機能を無効にします。これらの無効化条件は対象変数の設定値より優先されます（`engine/include/strata/core/defaults_026.hpp:21-29`, `engine/include/strata/core/gfx11_extra.hpp:27-31`, `engine/src/program/generate.cpp:4555-4558`, `engine/src/program/generate.cpp:4574-4579`）。
- Linux でデバイス 0 が gfx12 (`gfx1200` / `gfx1201`) なら、先行する gfx12 分岐が選ばれ、gfx11 の `else if` は実行されません（`engine/src/program/generate.cpp:4546-4558`, `engine/include/strata/kernels/gfx_arch.hpp:41-42`）。
- 起動時の RAM guard は、追加で必要な host RAM が不足すると上限を 32768 → 16384 → 8192 と段階的に下げます。`STRATA_GFX11_CHUNK=1` の完全一致はこの RAM guard の段階縮小を抑止しますが、他の値は抑止しません（`engine/src/program/generate.cpp:11189-11222`）。
- 複数 GPU で layer split を行う場合、`STRATA_SPLIT_CHUNK16K` が未設定、空、または `atoi` 結果 0 なら上限を最大 8192 に戻します。`STRATA_SPLIT_CHUNK16K` の `atoi` 結果が非 0 ならこの縮小を抑止します（`engine/src/program/generate.cpp:11171-11180`）。

## 実行時の詳細

`--prefill` の引数を処理した段階で bare auto を記録し、GPU が特定された後に Linux / Windows それぞれの HIP 分岐で対象変数を読みます。`STRATA_GFX11_CHUNK` 自体を保持する static cache はありません。さらに、auto chunk の RAM guard を走らせる際、`prefill_raise_who == "gfx11"` なら同じ名前を動的に選んで再度 `getenv` し、値が完全に `1` かを調べます（`engine/src/program/generate.cpp:3995-4014`, `engine/src/program/generate.cpp:4544-4563`, `engine/src/program/generate.cpp:4571-4586`, `engine/src/program/generate.cpp:11189-11210`）。

上限は context 長を超えず、最終的な auto scan は expert cache が貸し出せる範囲で最大の chunk を選びます。そのため、変数で上限を 16384 / 32768 にしても、短い context、RAM guard、cache の余裕がない場合は実際の chunk が小さくなります。chunk の決定処理は single GPU の `plan_lend` と split 用 scan の双方で上限・context 上限を確認します（`engine/src/program/generate.cpp:11166-11180`, `engine/src/program/generate.cpp:11224-11228`, `engine/src/program/generate.cpp:11254-11270`, `engine/src/program/generate.cpp:11887-11895`, `engine/src/program/generate.cpp:12451-12455`）。

## ログと測定値

Linux で gfx11 の上限引き上げ条件を通ると stderr に `strata generate: gfx11: --prefill auto may take chunks up to %lld (STRATA_GFX11_CHUNK=16 keeps 16384, =0 keeps 8192)` を出します。Windows では opt-in が成立し上限が正なら `strata generate: gfx11 (Windows): STRATA_GFX11_CHUNK raised --prefill auto up to %lld` を出します。条件を満たさない場合、これらの gfx11 ログは出ません（`engine/src/program/generate.cpp:4555-4564`, `engine/src/program/generate.cpp:4574-4586`）。

RAM guard が上限を下げる場合は stderr に `strata generate: gfx11: prompt chunks stay at ...` の形式で、候補 chunk、追加貸出 slot 数、RAM 使用見込みと利用可能 RAM、予約量を含む理由を出します。ログにある `%s=1` は gfx11 経路では `STRATA_GFX11_CHUNK=1` です（`engine/src/program/generate.cpp:11189-11220`）。

確認した読み取り箇所には、この変数を理由とする終了・エラー分岐はありません。観測できる対象固有の結果は上限設定と上記 stderr ログです。

この変数による性能測定値は記載しません。上記のソース内コメントには複数の GPU / モデル / prompt 条件の測定が混在しますが、この設定固有の条件付き比較として結果を確定できる測定資料は調査範囲で確認していません。

## 根拠

- 読み取りと OS / GPU / bare-auto 分岐: `engine/src/program/generate.cpp:3995-4014`, `engine/src/program/generate.cpp:4532-4567`, `engine/src/program/generate.cpp:4568-4590`
- 値の変換: `engine/include/strata/core/gfx11_extra.hpp:149-156`
- master defaults と個別 defaults の無効条件: `engine/include/strata/core/defaults_026.hpp:21-29`, `engine/include/strata/core/gfx11_extra.hpp:27-31`
- アーキテクチャ判定: `engine/include/strata/kernels/gfx_arch.hpp:15-25`
- RAM guard、split 縮小、最終 chunk 上限: `engine/src/program/generate.cpp:11166-11224`, `engine/src/program/generate.cpp:11887-11895`, `engine/src/program/generate.cpp:12451-12455`
