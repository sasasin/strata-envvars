# `STRATA_GFX12_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。調査開始時の作業ツリーは clean（`## main...origin/main`）。

## 役割

Linux HIP ビルドで gfx12 (RDNA4) を使う `strata generate --prefill auto` の自動 prompt chunk 上限を変更する。通常の上限 8192 tokens に対し、未設定または多くの設定値で 32768、文字列全体が `16` のとき 16384 に引き上げる。`0` で始まる値は引き上げを無効にする。これは上限であり、実際の chunk はモデルの context、借用できる expert-cache slots、RAM 判定などで小さくなり得る。読み取りと gfx12 判定は `engine/src/program/generate.cpp` にある（同ファイル: 4537-4559）。

## 値と判定

`std::getenv` の結果を `gfx12_chunk_ceiling` に渡し、数値変換はせず文字列で判定する。未設定 (`nullptr`) は 32768。設定値が文字列全体で `16` と一致すれば 16384。先頭文字が `0` なら 0（gfx12 上限を引き上げず、通常の 8192 のまま）。それ以外は 32768。空文字も「それ以外」なので 32768 となり、無効値エラーや警告は出ない（`engine/include/strata/core/gfx12_chunk.hpp:13-19`）。

| 条件 | unset | 有効になる値（例） | 無効・その他の値（例） |
|---|---|---|---|
| gfx12 Linux HIP の bare `--prefill auto` | 32768 | `16` → 16384、`1` → 32768（RAM guard も抑止） | `0`、`0anything`、`016` → 8192 上限。空文字、`16x`、`true`、` 0`、`-1`、`2` → 32768 |
| それ以外の build / OS / GPU / prefill 指定 | この変数による上限変更なし | 該当なし | 値はこの gfx12 分岐では使われない |

さらにRAM guardは `STRATA_GFX12_CHUNK` を動的に選んで再度 `getenv` し、値が文字列全体で `1` の場合だけ段階縮小を抑止する。したがって `1` は単に既定上限を選ぶだけでなく、空きRAMが不足してもこのguardによる 32768→16384→8192 の縮小を行わない。`01` や `1x` はこの例外にならない（`engine/src/program/generate.cpp:11267-11297`）。

## 有効になる条件

- ビルドが HIP で、Windows ではないこと（`#if defined(STRATA_USE_HIP) && !defined(_WIN32)`、`engine/src/program/generate.cpp:4537`）。CUDA ビルドと Windows HIP ビルドではこの gfx12 chunk 分岐に入らない。
- `--prefill auto` が bare 指定で、`STRATA_PREFILL_AUTO_MAX` が未設定であること。`--prefill auto:N`、数値指定、または `STRATA_PREFILL_AUTO_MAX` がある場合は `prefill_auto_bare` が false となり、gfx12 分岐は使われない（`engine/src/program/generate.cpp:4000-4018,4538`）。
- GPU 0 の device properties を取得でき、その `gcnArchName` が gfx12 と判定されること。取得失敗時は gfx12 上限を設定せず、通常上限が残る（`engine/src/program/generate.cpp:4550-4559`）。
- `STRATA_GFX12_DEFAULTS` が `0` で始まらないこと。`0`、`0anything` などは gfx12 の引き上げを無効にする。空文字や `false` は無効化しない（同: 4548, 4552-4559）。
- 複数 GPU の layer split では、`STRATA_SPLIT_CHUNK16K` を `atoi` した値が 0 の場合、上限を 8192 に戻す。非ゼロの変換結果なら上限を維持する（同: 11252-11258）。
- RAM guard は追加 slot の見積もり、利用可能 RAM、resident expert 用 RAM、`STRATA_PREFILL_RAM_RESERVE_MIB` に基づき上限を段階的に下げる。`STRATA_GFX12_CHUNK=1` はこの縮小を抑止する。RAM 条件を満たす限り、guard は上限を変更しない（同: 11267-11301）。
- `--no-prefill-borrow` が指定されるか expert profile が空の場合、後段で `prefill_auto` 自体が無効になり、chunk は通常 2048（専用 keep 条件がある場合を除く）に戻る。この経路では設定した上限は実際の auto chunk 選択に使われない（`engine/src/program/generate.cpp:4990-4995`）。
- chunk 上限の引き上げだけでは実際のサイズは保証されない。後続の fit scan が cache slot や prompt に応じて実サイズを選ぶ（同: 11304-11318, 23990-24063）。

## 実行時の詳細

`--prefill` の解析で `STRATA_PREFILL_AUTO_MAX` と bare 指定を決めた後、GPU が分かる段階で `STRATA_GFX12_CHUNK` と `STRATA_GFX12_DEFAULTS` を読み、条件に合えば `prefill_auto_max` と `prefill_chunk` を上限値に設定する（`engine/src/program/generate.cpp:4000-4018,4537-4559`）。gfx12 分岐の読み取りに static cache はなく、関数スコープの値として処理される。後続のRAM guardは、その guard のループ時に `o.prefill_raise_who` から環境変数名を選び、`getenv` を再実行する。リクエストごとの再評価を行う実装ではない（同: 11267-11274）。サーバー専用の読み取り箇所はなく、同じ `generate.cpp` の起動経路で評価される。

上限は `max_context` と 8192 の床の間に制限される。複数 GPU のlayer split条件やRAM guardがさらに上限を下げ、その後、cache slot のfit scanが実行可能なchunkを選ぶ。対象変数は生成 token の選択やモデル設定そのものを直接変更するコードではなく、bare auto prefill のchunk上限に作用する（同: 11244-11318, 23990-24063）。

## ログと測定値

引き上げが適用されると stderr に次の形式で出る（上限値は実行時の値）。

```text
strata generate: gfx12: --prefill auto may take chunks up to <上限> (STRATA_GFX12_CHUNK=16 keeps 16384, =0 keeps 8192)
```

RAM不足で上限を落とす場合は `strata generate: gfx12: prompt chunks stay at ...` の行が出る。ループは 32768 から 16384、8192 へ降ろす。値 `1` でこのRAM guard条件を強制通過した場合、縮小ログも出ない。引き上げが適用されない場合、この変数専用の無効値警告はない（`engine/src/program/generate.cpp:4559,11288-11299`）。実際に選んだ chunk は別途 `strata generate: prompt chunk auto: <tokens> tokens` と出る（同: 24061-24063）。

`docs/DETAILS.md:1209` は gfx12/Linux/1 GPU の bare auto が 32768 を取り得ること、`=0` と `=16` の効果、RAM guard を記載している。そこでの測定例は R9700 の IQ3_S で 20K prompt +12%、32K +1.3%、64K +2.6%、UD-Q4_K_XL の 20K +26%、first-token KL は 16384 比で最大 `5e-5` とされる。これは同資料に記載された条件付き測定であり、本調査で再測定した値ではない。現行コードでは既定上限が 16384 ではなく 32768 で、`STRATA_GFX12_CHUNK=16` が 16384 を選ぶ（`engine/src/program/generate.cpp:4543-4559`）。

## 根拠

- 値の判定: `engine/include/strata/core/gfx12_chunk.hpp:13-19`
- CLI 指定と bare auto の判定: `engine/src/program/generate.cpp:4000-4018`
- Linux HIP gfx12 判定、環境変数読み取り、上限設定、stderr: `engine/src/program/generate.cpp:4537-4559`
- layer split 条件と RAM guard の動的環境変数読み取り: `engine/src/program/generate.cpp:11244-11301`
- auto の無効化条件: `engine/src/program/generate.cpp:4990-4995`
- chunk のfit判定と実際に出る chunk のログ: `engine/src/program/generate.cpp:11304-11318,23990-24063`
- 文書化された適用条件と測定値: `docs/DETAILS.md:1209`
