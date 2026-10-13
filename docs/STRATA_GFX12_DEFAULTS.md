# `STRATA_GFX12_DEFAULTS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP ビルドで gfx1200 / gfx1201（RDNA4）を検出したとき、Strata が選ぶ5つの prompt 用環境変数デフォルトを一括で無効にする opt-out です。また Linux HIP では、裸の `--prefill auto` が prompt chunk 上限を 16384 に引き上げる処理も無効にします。変数名に `DEFAULTS` とありますが、値を `1` にして機能を有効化する設定ではありません。unset も含め、先頭文字が `0` でない場合に既定処理を許可します。

## 値と判定

どちらの読み取り箇所も `getenv()` の結果が null でなく、先頭文字が `'0'` である場合だけ opt-out と判定します。文字列全体の parse、数値変換、大文字小文字変換はしません。

| 設定値 | 判定 |
|---|---|
| 未設定 | opt-out しない（既定処理を許可） |
| 空文字 | opt-out しない。値は設定済みだが先頭文字は `\0` |
| `0`, `0anything` | opt-out |
| `1`, `true`, `false`, `2`, その他 `0` 以外で始まる文字列 | opt-out しない |

根拠: `src/core/arch_defaults.cpp:21-22`、`src/program/generate.cpp:2166-2170`。

## 有効になる条件

- **HIP のアーキテクチャ別デフォルト:** `src/program/generate.cpp` の `STRATA_USE_HIP` ビルド分岐で、engine が環境スイッチを初回参照する前に GPU 0 のプロパティを取得し、成功した場合に `apply_arch_defaults()` を呼びます。gfx1200 / gfx1201 の場合だけ表が返ります。アーキテクチャ名は完全一致または `:` で始まる feature suffix を許容します（例: `gfx1201:sramecc-:xnack-`）。他の GPU、CUDA ビルド、GPU プロパティ取得失敗ではこの表は適用されません。`STRATA_GFX12_DEFAULTS=0`（または `0` で始まる値）なら gfx12 でも表を適用しません。
- **自動 prefill chunk:** `STRATA_USE_HIP` かつ非 Windows のビルドで、`--prefill auto` が裸で指定され、`STRATA_PREFILL_AUTO_MAX` が設定されず、Windows HIP 向け上限がなく、GPU 0 のプロパティ取得に成功し、GPU が gfx1200 / gfx1201 の場合にだけ上限値と初期 chunk 値を 16384 にします。この分岐でも `STRATA_GFX12_DEFAULTS` が `0` で始まると 8192 のままです。`--prefill N`、`--prefill auto:N`、`STRATA_PREFILL_AUTO_MAX` を使う経路はこの変更の対象外です。

## 実行時の詳細

アーキテクチャ別デフォルトの表は `STRATA_GDN_HEAD=1`、`STRATA_GDN_PP=2`、`STRATA_GDN_CONVL2=1`、`STRATA_GDN_NOY=1`、`STRATA_CVEC_FUSE=1` です。`apply_arch_defaults()` は各変数が既に存在すれば、その値が空文字や `0` であってもユーザー設定を優先して変更しません。未設定のものだけをプロセス環境に設定し、1つ以上設定した場合は stderr に `strata: gfx12 (RDNA4): 5 exact speed switches on by default (STRATA_GFX12_DEFAULTS=0 turns them off; a switch you set is kept): ...` 形式の行を出します。設定済み変数名の表示部分は `STRATA_` を除いた名前です。opt-out した場合や何も新規設定しなかった場合、この関数からログは出ません。

裸の `--prefill auto` の gfx12 分岐では、上限と初期 chunk を 16384 にし、stderr に `strata generate: gfx12: --prefill auto may take chunks up to 16384 (STRATA_GFX12_CHUNK=0 keeps 8192)` を出します。実際の自動 chunk 選択は後段の fit scan によるため、16384 は上限であり、常にそのサイズを使う意味ではありません。opt-out 時はこの分岐で値を変更せず、このログも出しません。

値はいずれも起動時の引数処理中に直接読み取られ、static cache はありません。アーキテクチャ別の設定は engine が各スイッチを初回参照する前に行われます。起動後に環境を書き換えても、すでに行われたデフォルト適用や prefill 値の決定はさかのぼって変わりません。

`docs/DETAILS.md` は Linux gfx12 の裸の `--prefill auto` が 16384-token chunk を取り得ること、明示的な chunk 指定や `STRATA_PREFILL_AUTO_MAX` は対象外であること、`STRATA_GFX12_CHUNK=0` または本変数を `0` にすると 8192 を維持することを記載しています。これはソースの条件分岐と一致します。資料にある性能・残差に関する主張は、この調査では独自に測定していません。

## 根拠

- `src/program/generate.cpp:2152-2158`: HIP ビルドで GPU 0 の architecture defaults を engine 初期化前に適用。
- `src/core/arch_defaults.cpp:12-32`: gfx12 判定、opt-out 条件、5つの既定値。
- `src/core/arch_defaults.cpp:61-81`: 既存設定の保持、環境への設定、stderr ログ。
- `include/strata/kernels/gfx_arch.hpp:15-20,35-36`: architecture 名の一致規則と gfx12 対象。
- `src/program/generate.cpp:1946-1965,2160-2176`: prefill 指定の分類、Linux HIP 限定の gfx12 chunk 条件・効果・ログ。
- `docs/DETAILS.md:1947`: 裸の auto、明示指定、8192/16384 に関する説明。
