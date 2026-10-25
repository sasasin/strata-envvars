# `STRATA_GDN_PP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

AMD HIP の GDN prompt recurrence で、`STRATA_GDN_HEAD` が選んだ quad recurrence のカーネル形状を切り替えます。未設定相当では標準の quad カーネル、値 `2` では1レーンが2列を処理するカーネル、それ以外の非ゼロ値では別の PP カーネルを選びます。GDN の recurrence 自体を有効にするスイッチではありません。

## 値と判定

値は `std::atoi()` で整数に変換されます。変換値の範囲検査や文字列全体の妥当性検査はありません。

| `atoi()` の結果 | 選択される recurrence |
|---|---|
| `0` | `gdn_rec_quad_kernel`（PP 分岐なし） |
| `2` | `gdn_rec_quad2c_kernel`（2列/レーン） |
| 0以外で2以外 | `gdn_rec_quad_pp_kernel` |

未設定、空文字、数値に変換できない文字列は通常 `0` になります。たとえば `2junk` は `atoi()` が `2` を返すため2列カーネル、`1`・`-1`・`junk` はそれぞれ PP カーネル・PP カーネル・標準カーネルです。コードが最初にこの分岐へ入った時点で判定値を関数内 `static const` に保存するため、プロセス中の環境変更は再評価されません。

根拠: `src/prefill/kernels.cu:1951-1959`。同じ分岐のコードは `sycl/src/prefill/kernels.dp.cpp:2627-2635` にもありますが、いずれも `#if defined(__HIPCC__)` のブロック内です。

## 有効になる条件

- AMD/HIP の quad recurrence 分岐であること（`src/prefill/kernels.cu` では `__HIPCC__` 条件内）。CUDA ではこの分岐がコンパイル対象になりません。
- `STRATA_GDN_HEAD` が `atoi()` で非ゼロとなり、かつ `STRATA_GDN_REC_HEADS` が未設定であること。そうでなければ `gdn_recurrence()` は variant 1 を渡さず、この変数の分岐に入りません。
- recurrence の token 数 `T` が正であること。この場合に限って `pp` を読み、カーネルを起動します。`T <= 0` ではこの読み取りと起動を行いません。
- 設定が未指定でも、起動時の GPU arch defaults が値を補う場合があります。HIP エンジンはデバイス情報の取得後、エンジンが各スイッチを初めて読む前に `apply_arch_defaults()` を呼びます。gfx1151 では `STRATA_GFX1151_DEFAULTS`、gfx12 では `STRATA_GFX12_DEFAULTS` が未設定、または先頭文字が `0` でないとき、既存のユーザー設定がなければ `STRATA_GDN_PP=2` を設定します。いずれかの defaults 無効化変数が先頭文字 `0` ならテーブル全体を適用しません。その他の arch ではこの表から値を補いません。
- `apply_arch_defaults()` は `getenv()` で変数の存在を確認し、既に存在すれば値を問わず保持します。したがって `STRATA_GDN_PP=0` や空文字も明示設定として保持され、2列カーネルに上書きされません。

根拠: `src/core/arch_defaults.cpp:12-34,61-70`; 呼び出しは `src/program/generate.cpp:2152-2158` および `sycl/src/program/generate.cpp:1970-1976`; variant の決定は `src/prefill/kernels.cu:1996-2003`。

## 実行時の詳細

`STRATA_GDN_PP=2` の `gdn_rec_quad2c_kernel` は、各 lane が2列を計算し、同じ lane の列同士で q/k の shared-memory 読み出しを共有します。実装コメントは列ごとの算術順序を元の quad kernel と同じとしています。`STRATA_GDN_PP=1` など2以外の非ゼロ値は `gdn_rec_quad_pp_kernel` を選びます。どちらの場合も、選ばれた recurrence kernel の後に `gdn_out_norm_loop_kernel` が起動されます。

起動時に arch defaults が値を補った場合は、`strata: gfx12 (RDNA4): ... exact speed switches on by default ...` または gfx1151 の同形式のログに `GDN_PP` が含まれます。既に値が設定されていた場合や、defaults を無効にした場合、この関数は `GDN_PP` の設定ログを出しません。`STRATA_GDN_PP` 自体の parse エラーや選択カーネル名の個別ログは確認できません。

## 文書・測定との照合

`docs/STRIX_HALO.md:83-96` は gfx1151 で arch defaults がスイッチを設定すること、`STRATA_GDN_PP=2` が GDN prompt recurrence の「two columns per lane」に当たることを説明しています。同文書はそこで示す結果を maintainers の環境での確認として記述しています。`src/core/arch_defaults.cpp:39` のコメントには「64K prompt +2.9% (stream A, round 2)」とありますが、コメント単体では測定対象の詳細な機種・モデル・反復手順が揃わないため、一般的な性能効果とは扱いません。`docs/DETAILS.md` にこの変数固有の測定条件・数値は見つかりませんでした。

## 根拠

- 値の読み取りとカーネル選択: `src/prefill/kernels.cu:1951-1968`
- GDN head variant と serial override: `src/prefill/kernels.cu:1996-2003`
- 2列カーネルの lane 配置・実装意図: `src/prefill/kernels.cu:1309-1329`
- gfx1151/gfx12 での既定値と defaults 有効化条件: `src/core/arch_defaults.cpp:12-40`
- 既存環境値の保持と設定ログ: `src/core/arch_defaults.cpp:61-80`
- HIP 起動時の defaults 適用位置: `src/program/generate.cpp:2152-2158`
- gfx1151 でのスイッチ説明: `docs/STRIX_HALO.md:83-96`
