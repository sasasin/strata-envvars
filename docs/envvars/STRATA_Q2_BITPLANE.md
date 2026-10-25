# `STRATA_Q2_BITPLANE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

native pack の Q2_0 expert 行列を CPU で計算するとき、AVX2 用の従来 row kernel に代えて bit-plane row kernel を使います。bit-plane 形式の activation データも token ごとに前処理します。コードコメントと `docs/DETAILS.md` によると、整数演算部分は正確ですが浮動小数点の加算順序が変わるため、結果の最下位ビットが変わる場合があります。

通常の native Q2_0 専用カーネル経路は、Q2_0 型（ggml type 42）かつ CPU が AVX2 対応の場合に限られます。AVX-512 対応 CPU では row 計算が AVX-512 カーネルへ dispatch され、この変数による AVX2 bit-plane 選択は行われません。AVX2 非対応 CPU では通常の native pack 経路が ggml-cpu に委ねられます。ソースには AVX1 版にも同じ変数判定と bit-plane 実装がありますが、通常の native Q2_0 専用カーネルの選択条件が AVX2 を要求するため、AVX1 版はその通常経路では選択されません。

## 値と判定

AVX2 版と AVX1 版それぞれで、`std::getenv()` の結果が null でなく、先頭文字が `'1'` なら有効です。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定） |
| 空文字 | 無効 |
| `1`、`10`、`1anything` | 有効（先頭文字だけを確認） |
| `0`、`true`、` 1`、その他先頭文字が `1` でない値 | 無効 |

大文字小文字、末尾、数値としての妥当性は判定しません。有効・無効の値を通知するログは、この判定箇所にはありません。

## 有効になる条件

- native pack の Q2_0 expert 行列を Strata の CPU Q2_0 カーネルで計算する経路であること。通常の native Q2_0 カーネル predicate は型 42 と AVX2 対応の両方を要求します。
- AVX2 row 関数に到達すること。AVX-512 対応 CPU は `q2_rows_any()` で AVX-512 を優先し、AVX2 版は使いません。
- activation 量子化器が bit-plane image を作成できる形状であり、全 activation の `bp_pairs` が行列の `nblocks / 2` と一致すること。条件が合わない場合は従来 row kernel に fallback します。
- 行列の `nblocks` が偶数であること。activation image 側でも `nchunks % 4 == 0` が必要です。不成立なら image を持たず、row 関数は bit-plane を使いません。

## 実行時の詳細

判定結果 `kBitplane` は AVX2/AVX1 の各翻訳単位にある名前空間スコープ `const bool` として初期化されます。各翻訳単位の初期化時に環境を読み、以降はその値を使います。プロセス起動後に環境を変更しても再判定されません。AVX2 と AVX1 は別々に同じ変数を読みます。

AVX2 または AVX1 activation quantizer は、`kBitplane` が真の場合だけ Q8_1 activation から bit-plane image (`qp`, `psum`, `pscale`) を構築します。偽の場合は `bp_pairs` を 0 にします。Q2_0 row 関数は `kBitplane`、偶数 `nblocks`、全 token の image 形状一致を確認し、条件がそろえば bit-plane row kernel を呼びます。そうでなければ AVX2/AVX1 の従来 kernel を呼びます。対象外の型や CPU dispatch による別 backend の計算はこの設定で変わりません。

`docs/DETAILS.md` は AVX2 かつ AVX-512 なしの CPU 向けの opt-in と記載し、最下位ビットが変わると説明しています。現行ソースには AVX1 実装もありますが、通常の native Q2_0 専用カーネル predicate は AVX2 を要求します。性能値は本調査では確認・測定していません。

## 根拠

- `src/kernels/cpu/q2_avx2.cpp:146-149,172-189,197-225,229-269` — 変数判定、AVX2 row-kernel の選択、image 生成条件。
- `src/kernels/cpu/q2_avx1.cpp:178-181,185-212,232-252,254-292` — AVX1 版の判定、row-kernel、image 生成。
- `src/kernels/cpu/expert_layout.cpp:356-374` — AVX-512 / AVX2 / AVX1 の dispatch と activation quantizer dispatch。
- `include/strata/kernels/cpu/expert_layout.hpp:78-90` — native Q2_0 専用 kernel predicate が type 42 と AVX2 を要求すること。
- `src/core/expert_source.cpp:3890-3900`, `src/kernels/cpu/pool.cpp:693-714,830-837` — CPU expert 用 activation 量子化と native Q2_0 row 計算の呼び出し。
- `docs/DETAILS.md:287-289` — opt-in、対象 CPU の説明、最下位ビットに関する記載。
