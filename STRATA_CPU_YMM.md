# `STRATA_CPU_YMM`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

CPU の Q2_0 expert row dot が使うベクトル幅を選びます。未設定なら 512-bit の ZMM 実装、設定されていれば 256-bit の YMM 実装を選びます。対象は `src/kernels/cpu/expert.cpp` の S2 expert の行計算（単一 activation と複数 token の両方）です。CUDA/HIP/SYCL カーネルや GGUF block-layout 用の `q2_0_gguf_rows_multi()` はこのフラグを参照しません。

## 値と判定

文字列の値は parse せず、`std::getenv()` の結果が null かどうかだけで判定します。

| 環境変数の状態 | 選択される経路 |
|---|---|
| 未設定 | ZMM: 512-bit の `row_dot_z()` / `row_dot_multi_z()` |
| 設定あり | YMM: 256-bit の `row_dot()` / `row_dot_multi()` 内の AVX-VNNI 計算 |

空文字、`0`、`false` を含め、何らかの値が設定されていれば YMM 側です。大文字小文字、前後の空白、数値としての妥当性による違いはありません。CLI 引数や設定ファイルによる上書きは実装にありません。

## 有効になる条件

- Strata の CPU S2 expert kernel が使われる場合に限ります。Q2_0 の S2 expert では `s2_expert_vnni_q()` が各 gate/up/down row について `row_dot()` を呼び、multi-token 経路は `row_dot_multi()` を呼びます（`src/kernels/cpu/expert.cpp:408-430,434-446,472-498`）。
- canonical Q2_0 pack は CPU expert kernel の実行前に AVX-512 CPU 要件を確認します。要件を満たさない場合は `strata: this CPU cannot run the expert kernel: ...` を stderr に出し、終了コード 1 で終了します（`src/program/generate.cpp:2774-2775`, `src/kernels/cpu/expert_layout.cpp:337-345`）。
- この変数は CPU 要件チェックを回避しません。YMM 経路も AVX-VNNI と `_mm256_multishift_epi64_epi8` を使い、同じ AVX-512 向け翻訳単位には `act_quant_q8_1()` の ZMM 実装もあります（`src/kernels/cpu/expert.cpp:123-135,151-157,230-245,273-298,341-375`）。CMake でも `expert.cpp` を AVX-512 用オプション付きでコンパイルします（`CMakeLists.txt:1160-1172`）。したがって、変数名の YMM は AVX-512 非対応 CPU 用のフォールバックを意味しません。

## 実行時の詳細

`kZmm` はファイルスコープの `static const bool` として一度だけ初期化されます。未設定なら true になり ZMM row kernel を呼びます。設定ありなら false になり、8 lane の accumulator、256-bit の unpack/VNNI dot と最終水平和を使う YMM row kernel に進みます。単一 token と multi-token の両方がこのフラグを参照します。プロセス起動後の環境変更は再評価されません（`src/kernels/cpu/expert.cpp:151,230-245,273-298`）。

この切替の性能差や出力差について、`docs/DETAILS.md` に `STRATA_CPU_YMM` の値ごとの測定はありません。資料は canonical Q2_0 pack が AVX-512 CPU 用の fast CPU kernel を使うことを説明していますが、この環境変数の詳細までは記載していません（`docs/DETAILS.md:215-223,419-420`）。

## 根拠

- 変数名の直接参照は `src/kernels/cpu/expert.cpp:151` の1箇所です（Strata リポジトリ全体を検索）。
- ZMM / YMM の分岐と二つの row kernel: `src/kernels/cpu/expert.cpp:142-151,172-189,221-245,273-298`。
- 単一・分割 row・複数 token の呼び出し: `src/kernels/cpu/expert.cpp:408-446,472-498,561-576`。
- canonical pack の CPU 要件チェック: `src/program/generate.cpp:2774-2783`, `src/kernels/cpu/expert_layout.cpp:337-345`。
- 翻訳単位の ISA compile flags: `CMakeLists.txt:1160-1172`。
