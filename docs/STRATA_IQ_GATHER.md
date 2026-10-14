# `STRATA_IQ_GATHER`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU の AVX-512 multi-token i-quant expert kernel で、IQ3_XXS と IQ3_S の codebook grid を読む方法を選びます。未設定なら scalar lookup の値を `_mm512_set_epi32` でまとめ、設定されていれば `_mm512_i32gather_epi32` を使います。どちらも同じ grid table の同じ要素を読む実装です。コード上、変わるのは grid の読み方で、他の形式や計算式はこの変数の対象ではありません。

## 値と判定

| 環境変数の状態 | `gather` の値 | grid lookup |
|---|---:|---|
| 未設定 | `false` | scalar lookup を `_mm512_set_epi32` で組み立てる |
| 空文字を含む、何らかの値が設定済み | `true` | `_mm512_i32gather_epi32` を使う |

実装は `std::getenv("STRATA_IQ_GATHER") != nullptr` だけを判定します。数値・文字列の parse や値の比較はありません。そのため `0`、`false`、空文字も有効化し、`1` 以外の値も同じ扱いです。変数は `iq_avx512.cpp` の名前空間スコープの `const bool` として初期化されるため、実行中に環境を変更しても再評価されません。

## 有効になる条件

- AVX-512 用の CPU kernel がビルドに含まれていること。CMake は `iq_avx512.cpp` を CPU kernel target に加え、AVX-512 命令を有効にしてコンパイルします。
- 実行 CPU が `cpu_avx512_ok()` を満たし、`STRATA_NO_IQ512` が設定されていないこと。`STRATA_FORCE_AVX2` で AVX-512 を無効にする場合も、この kernel には入りません。
- gate/up の native expert dispatch が対象 IQ 形式を選び、token group 数が `STRATA_IQ_MT_MIN` による multi-token 下限以上であること。下限は通常2で、`STRATA_IQ_MT_MIN` が設定されると `atoi` の結果で変わります。
- 実際に lookup を切り替える形式は IQ3_XXS と IQ3_S（kernel 内の type 18 と 21）です。AVX-512 kernel が扱う IQ2_XXS、IQ2_XS、IQ2_S ではこの変数による gather 分岐はありません。

AVX-512 非対応 CPU で AVX2 kernel に進む場合、その経路の lookup は別の `STRATA_IQ256_GATHER` によって判定されます。`STRATA_IQ_GATHER` は AVX2 経路を切り替えません。AVX-512 対応 CPU で `STRATA_NO_IQ512` により AVX-512 kernel を無効にした場合は、この dispatch では AVX2 に降格せず ggml-cpu の dot product に進みます。

## 実行時の詳細

native expert の gate/up 行処理は、形式と CPU 機能を確認して AVX-512 kernel を呼びます。各 IQ3_XXS/IQ3_S block の decode で `gather` が真なら、読み込んだ byte index（IQ3_S では上位 bit も加えた index）を使って grid を gather します。偽なら同じ index の各 table 要素を個別に参照し、vector に詰めます。その後の sign mask、scale、整数 dot、SwiGLU 計算は同じ処理です。コードコメントは両経路で同じ値を得る設計としています。

`docs/DETAILS.md` にこの変数の説明や測定条件は見つかりませんでした。実装コメントには Ryzen 5 7600 で gather が scalar lookup より3–5%遅かったとの記述がありますが、同じ箇所に測定方法などの詳細はなく、他 CPU での性能を示す根拠にはできません。

## 根拠

- `src/kernels/cpu/iq_avx512.cpp:31-39`: 環境変数の有無判定、初期化時期、および隣接する prefetch 変数との区別。
- `src/kernels/cpu/iq_avx512.cpp:108-128,130-153`: IQ3_XXS/IQ3_S の gather と scalar lookup の分岐、他形式には同分岐がないこと。
- `src/kernels/cpu/native_expert.cpp:40-46,124-140,143-193`: AVX-512 対応形式、multi-token の下限、CPU 機能・無効化環境変数を含む gate/up dispatch。
- `src/kernels/cpu/expert_layout.cpp:41-65`: AVX-512 実行可否の CPU/OS 機能確認。`src/kernels/cpu/expert_layout.cpp:35-36,41-44` は `STRATA_FORCE_ISA` / `STRATA_FORCE_AVX2` の上限判定。
- `CMakeLists.txt:1317-1342`: CPU kernel target への登録と AVX-512 compile option。
- `docs/DETAILS.md:97-112`: `STRATA_IQ_MT_MIN` など関連する IQ multi-token 動作の説明。`STRATA_IQ_GATHER` 自体の説明はなし。
