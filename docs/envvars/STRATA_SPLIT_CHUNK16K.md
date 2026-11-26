# `STRATA_SPLIT_CHUNK16K`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU 世代別の既定値によって bare `--prefill auto` の上限が 8192 より高くなった場合に、マルチ GPU の layer split でもその上限を保つための設定です。unset または `atoi` で 0 になる値では、layer split 時に prompt auto の上限を最大 8192 に戻します。非ゼロなら、この抑制を行いません。変数自体が 16384 を設定するわけではなく、より高い上限を作る backend・GPU・他設定の条件が別途必要です。実読み取りと上限変更は `engine/src/program/generate.cpp:11248-11258` にあります。

## 値と判定

この値を読むのは `multi_gpu && o.prefill_gfx12_16k` の分岐内だけです。`std::getenv` の戻り値ポインターを関数内 `static` に保存し、その後 `std::atoi(keep16) != 0` で判定します。したがって文字列全体の検証はなく、数値変換できない先頭なら 0、数値の後ろの文字列は無視されます。空文字は `atoi` で 0 です。`1`, `-1`, ` 1`, `1suffix` は非ゼロとなり抑制を解除し、`0`, `0suffix`, `true`, `false`, 空文字、未設定は抑制を解除しません。範囲検証や無効値の警告はありません。`atoi` の範囲外入力の結果はこのコードで扱っていません。読み取りコード: `engine/src/program/generate.cpp:11252-11258`。

| 条件 | unset / 空文字 | 抑制を解除する例 | 抑制を解除しない例 |
|---|---|---|---|
| layer split かつ raised auto ceiling が有効 | ceiling と `prefill_chunk` の上限を最大 8192 にする | `1`, `-1`, `1suffix`, ` 1` | unset, ``, `0`, `0suffix`, `true`, `abc` |
| 上記以外 | この変数を読まない。値にかかわらずこの処理の変更なし | 該当なし | 該当なし |

## 有効になる条件

- `--prefill auto` を bare 指定する必要があります。`--prefill auto:N` と、`STRATA_PREFILL_AUTO_MAX` が設定されている `--prefill auto` は `prefill_auto_bare` にならず、GPU 世代別の bare-auto 引き上げ処理に入りません。環境変数は空文字や不正値でも「設定あり」と判定されます。引数の分類と環境変数優先順位は `engine/src/program/generate.cpp:4000-4021` にあります。
- `o.prefill_gfx12_16k` が立つ必要があります。CUDA/NVIDIA 経路では HIP・Metal でない build で bare auto のとき、可視 GPU の最低 compute capability が 8.0 以上または 7.0 (Volta) で、NVIDIA ceiling が正の場合に raised ceiling が設定されます。`STRATA_NV_CHUNK`, `STRATA_DEFAULTS=026`, 最小 VRAM も判定に関わります（`engine/src/program/generate.cpp:4494-4532`; ceiling 判定: `engine/include/strata/core/nv_chunk.hpp:21-43`）。
- HIP/Linux 経路では bare auto、gfx12 (`gfx1200` / `gfx1201`) または discrete RDNA3、対応する ceiling が必要です。gfx12 の `STRATA_GFX12_DEFAULTS=0` は引き上げを止めます。gfx11 では `STRATA_GFX11_CHUNK` や `STRATA_DEFAULTS=026` が ceiling に関わります（`engine/src/program/generate.cpp:4537-4571`; ceiling 判定: `engine/include/strata/core/gfx12_chunk.hpp:13-19`, `engine/include/strata/core/gfx11_extra.hpp:149-155`）。
- HIP/Windows では discrete RDNA3 に対して `STRATA_GFX11_CHUNK` が空でなく、先頭文字が `0` でなく、既定値無効化もなく、GPU ceiling が正の場合に raised ceiling が設定されます（`engine/src/program/generate.cpp:4573-4595`）。
- さらに `multi_gpu`、すなわち別 GPU を使う layer split である必要があります。同じ GPU を指定した split は除外されます（`engine/src/program/generate.cpp:4856`）。layer split 自体は `--serve` が必要です（不正な組み合わせの検査: `engine/src/program/generate.cpp:4848-4853`）。
- 非ゼロ値は上限抑制だけを外します。基礎となる世代別 ceiling が 16384 ならその上限、32768 ならその上限が候補になり、context、Windows HIP の cap、cache/VRAM fit、RAM guard でさらに小さくなる場合があります（`engine/src/program/generate.cpp:11248-11303`, `11966-12000`）。RAM guard は通常、追加 loan と RAM reserve が足りなければ ceiling を下げますが、対応する `STRATA_NV_CHUNK`, `STRATA_GFX11_CHUNK`, または `STRATA_GFX12_CHUNK` が文字列として厳密に `1` の場合はその guard を迂回します（`engine/src/program/generate.cpp:11267-11301`）。

## 実行時の詳細

`--prefill` を解析して bare auto かどうかを記録し、GPU 情報に基づいて世代別上限を設定した後、layer split の prompt auto 上限を計算する段階で変数を参照します。分岐内の `static const char*` 初期化は最初にこの条件へ到達した時に一度だけ行われます。以降は環境を再読込しません。Strata 内にこの値を設定・転送する別箇所はありません（候補名の全参照は `engine/src/program/generate.cpp:4501,11251-11254`。実読み取りは同ファイル 11253 行）。

unset または 0 扱いなら `auto_ceiling`, `o.prefill_auto_max`, `o.prefill_chunk` の各値を 8192 以下にします。非ゼロならその変更をせず、すでに設定された raised ceiling を保ちます。その後も cache の貸出可能量を調べる auto scan が最大 chunk を選ぶため、実際の chunk が ceiling と同じとは限りません（`engine/src/program/generate.cpp:11248-11303`, `11966-12000`）。prompt 実行時には `--prefill auto` の実 chunk を `strata generate: prompt chunk auto: %lld tokens` と stderr に出します（`engine/src/program/generate.cpp:24055-24064`）。

## ログと測定値

この変数の値そのものに対するログ、無効値警告、エラー終了経路はありません。世代別引き上げが成立した場合は、NVIDIA で `strata generate: NVIDIA: --prefill auto may take chunks up to ...`、HIP/Linux で gfx12 または gfx11 の同様のログ、HIP/Windows では `strata generate: gfx11 (Windows): STRATA_GFX11_CHUNK raised --prefill auto up to ...` が出ます（`engine/src/program/generate.cpp:4520-4531,4554-4569,4583-4592`）。実際に選ばれた auto chunk は前節の `prompt chunk auto` ログで確認できます。

ソースコメントは layer split で 8192-token chunks を使った比較として、2x R9700 の pp32k +14%、4x の pp32k +19%、pp64k +4% / +16% と記しています（`engine/src/program/generate.cpp:11249-11251`）。同じソースには測定条件の詳細がこの箇所にないため、ここでは比較の一般化や再現性を主張しません。`STRATA_SPLIT_CHUNK16K=1` は当該 source comment 上も split の raised ceiling を保つ指定です。

## 根拠

- `engine/src/program/generate.cpp:4494-4532` — NVIDIA bare-auto ceiling の適用条件と上限設定。
- `engine/src/program/generate.cpp:4537-4595` — HIP/Linux と HIP/Windows の gfx 世代別 bare-auto ceiling。
- `engine/src/program/generate.cpp:4856` — `multi_gpu` の定義（異なる GPU を使う split）。
- `engine/src/program/generate.cpp:11244-11258` — ceiling 算出、対象環境変数の実読み取り、split 時の上限変更。
- `engine/src/program/generate.cpp:11267-11303,11966-12000` — RAM guard と split/cache fit による追加の上限制約。
- `engine/src/program/generate.cpp:24055-24064` — prompt 実行時の選択 chunk とログ。
- `engine/include/strata/core/nv_chunk.hpp:21-43`, `engine/include/strata/core/gfx12_chunk.hpp:13-22`, `engine/include/strata/core/gfx11_extra.hpp:149-155` — 周辺の世代別 ceiling の変換規則。
