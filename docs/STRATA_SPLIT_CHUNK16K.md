# `STRATA_SPLIT_CHUNK16K`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

AMD gfx12（gfx1200 / gfx1201、Linux HIP build）で、裸の `--prefill auto` が単一 GPU 向けに選べる 16,384-token 上限を、レイヤー分割時にも維持するための opt-in 環境変数です。未設定または無効値では、分割時の自動 chunk 上限を 8,192 にします。実際に選ばれる chunk は、コンテキスト長、借用可能な expert cache 枠、RAM 量による後段の制約を受けます。

## 値と判定

値全体の検証はせず、C の `std::atoi` で整数に変換し、結果が 0 かどうかを見ます。先頭の空白や符号は `atoi` の規則で処理され、数値の後ろは無視されます。

| 値 | 判定 | 分割時の動作 |
|---|---|---|
| 未設定 | 無効 | 自動 chunk 上限を 8,192 にする |
| 空文字 | 無効（`atoi` は 0） | 同上 |
| `0`, `false`, `abc` | 無効（変換結果 0） | 同上 |
| `1`, `2`, `-1`, `1abc`, `1.5` | 有効（変換結果が非 0） | この変数による 8,192 への引き下げを行わない |

文字列としての `true` / `false` 判定ではありません。大文字小文字も比較しません。値は、実行中にこの分岐が初めて評価される際に `static` ポインターへ取得されます。

## 有効になる条件

以下をすべて満たす経路でのみ読み取られ、影響します。

- `STRATA_USE_HIP` かつ非 Windows のビルドで、裸の `--prefill auto` が指定されている。`--prefill auto:N`、数値指定、`STRATA_PREFILL_AUTO_MAX` を使った指定には gfx12 の 16K 上限自体が設定されないため、この変数も作用しません。
- GPU 0 のアーキテクチャが gfx12（`strata::kernels::gfx_arch_is_gfx12`）である。
- `STRATA_GFX12_CHUNK` と `STRATA_GFX12_DEFAULTS` のいずれも、値の先頭文字が `0` ではない。これらの条件を通ると `o.prefill_gfx12_16k` が設定されます。
- 実際に複数 GPU の layer split が使われる。`--split-skip-if-fits` で分割が解除された場合など、`multi_gpu` が false なら影響しません。

したがって CUDA、Windows HIP、gfx12 以外の GPU、単一 GPU、明示 chunk 指定では、この変数を設定してもこのコード経路の chunk 選択は変わりません。

## 実行時の詳細

裸の `--prefill auto` は、Linux HIP gfx12 の条件を満たすとまず 16,384 を上限候補にします。レイヤー分割中に本変数の `atoi` 結果が 0 なら、実装は `auto_ceiling`、`o.prefill_auto_max`、`o.prefill_chunk` を最大 8,192 に抑えます。非 0 ならこの引き下げを行わず、16,384 を候補として残します。これは上限の選択であり、16,384-token chunk を必ず使う指定ではありません。後続の auto fit scan が cache の借用可能量や context に応じてより小さい値を選びます。

また、gfx12 の RAM 安全判定は本変数と独立して後段にあります。利用可能 RAM が resident expert の pin 量、16,384 chunk による追加 slot 分、6,144 MiB の余裕の合計に届かない場合、`STRATA_GFX12_CHUNK` が `1` で始まらない限り、chunk 上限を再び 8,192 に下げて stderr に `strata generate: gfx12: prompt chunks stay at 8192: ...` を出します。本変数を有効にしてもこの RAM 判定は無効化されません。

## 文書と測定値

`docs/MULTI_GPU.md` は gfx12 の分割 prompt では、16K を二つ、32K を四つの chunk にして各 GPU の読み込みを重ねる動作を記述しています。同文書には R9700 の 2x / 3x / 4x 構成で測定した prompt tok/s の差（16K: +36% / +45% / +53%、32K: +18% / +21% / +29%、64K: +4% / +12% / +17%、8K: 変化なし）も記載されています。これは同文書記載の条件での測定値で、他環境の性能を示すものではありません。

## 根拠

- `src/program/generate.cpp:2041-2060` — `--prefill auto` / `auto:N` と `STRATA_PREFILL_AUTO_MAX` の区別、bare auto の判定。
- `src/program/generate.cpp:2256-2272` — Linux HIP gfx12 での 16,384 上限設定、および `STRATA_GFX12_CHUNK` / `STRATA_GFX12_DEFAULTS` による前提条件。
- `src/program/generate.cpp:2407,3470-3479` — `multi_gpu` の定義と split skip 時の解除。
- `src/program/generate.cpp:6612-6626` — 対象変数の読み取り、`atoi` 判定、8,192 上限への変更。
- `src/program/generate.cpp:6635-6658` — RAM 条件による別の 8,192 fallback と stderr 出力。
- `docs/MULTI_GPU.md:196-200` — 分割 prompt の chunk pipeline と記載された測定値。
