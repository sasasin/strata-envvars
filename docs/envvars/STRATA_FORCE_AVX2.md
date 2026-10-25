# `STRATA_FORCE_AVX2`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata 自身の CPU カーネル選択で AVX-512 を使わないようにするテスト用フックです。AVX-512 が実際に使える CPU でも、環境変数の値が `1` で始まると AVX-512 判定が false になり、AVX2 などの下位経路へ進みます。AVX2 自体の機能検出を無効にはしません。

## 値と判定

| 値 | `cpu_avx512_ok()` / `cpu_avx512bw_ok()` の扱い |
|---|---|
| 未設定 | この変数による抑止なし。続けて ISA 上限、CPU 機能、OS の保存状態を検査 |
| 空文字 | 設定済みだが先頭文字が `1` ではないため抑止なし |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | false を返し、以降の AVX-512 機能検査を行わない |
| その他（例: `0`, `true`, ` 1`） | この変数による抑止なし。通常の検査へ進む |

文字列全体の比較や数値変換はせず、先頭文字 `f[0] == '1'` だけを見ます。大文字小文字や後続文字は判定に関係しません。環境変数が AVX-512 を抑止しても `cpu_avx2_ok()` はこの変数を参照せず、別に CPU/OS の AVX2 対応を検査します。

## 有効になる条件

- Strata の CPU カーネル選択が `cpu_avx512_ok()` または `cpu_avx512bw_ok()` を使う経路で有効です。参照箇所は `src/kernels/cpu/expert_layout.cpp` と、その関数を呼ぶ CPU カーネル実装です。
- AVX-512 が元から利用できない CPU では、値を設定しても判定結果は変わりません。
- `STRATA_FORCE_ISA` による ISA 上限も `cpu_avx512_ok()` の条件です。AVX-512 を抑止した後も、利用可能であれば AVX2 判定は独立して通ります。
- 通常の canonical Q2_0 実行経路にある `cpu_require_expert_support()` は `STRATA_FORCE_AVX2` を参照せず、実 CPU の AVX-512 機能を `cpu_features()` で検査します。この環境変数はその起動要件を緩和しません。

## 実行時の詳細

`cpu_avx512_ok()` と `cpu_avx512bw_ok()` は、それぞれ関数内の `static const bool` に判定結果を保存します。環境変数はその関数が初めて評価される時に読み取られ、以降の変更は反映されません。両関数の初回評価タイミングは独立しています。

主な効果は次のとおりです。

- Native expert の i-quant gate/up 経路では、AVX-512 kernel の選択条件が false になり、形式・group size・他の設定が許せば AVX2 kernel を選びます。AVX2 kernel が無効または未対応の形式などでは、後続の ggml-cpu vec_dot 経路へ進みます。AVX2 も利用できない場合は、その AVX2 kernel は呼びません（older-CPU build の AVX1 経路など別条件の経路があります）。
- NVFP4 native expert の gate/up では AVX-512 経路を飛ばし、条件が合えば AVX2 kernel、そうでなければ ggml-cpu 経路を使います。
- `q2_rows_any()` と activation quantizer の dispatch では、AVX-512 の代わりに、CPU が対応していれば AVX2、さらに対応していなければ AVX1 の実装を選びます。
- Native pack では AVX-512 がない場合に `strata generate: this CPU has no AVX-512: the expert kernels run on ...` という stderr ログが出ます。このログは環境変数を直接報告するものではなく、判定結果に基づきます。

この設定で AVX2 側へ切り替わると、選ばれる演算実装が変わります。コードコメントは i-quant の AVX2 と AVX-512 で丸めが異なるケースに言及していますが、この環境変数自体について出力の同一性や性能を測定した資料は確認できませんでした。`docs/DETAILS.md` には AVX-512 / AVX2 の一般的な CPU 経路の説明がありますが、この変数の個別説明は見つかりませんでした。

## 根拠

- `src/kernels/cpu/expert_layout.cpp:41-73,76-108`: 両 AVX-512 判定で先頭文字 `1` を確認し、その場合 false を static cache。通常時は ISA 上限、CPUID、OSXSAVE/XCR0 も検査。
- `src/kernels/cpu/expert_layout.cpp:110-141,345-353`: AVX2 判定は本変数と独立。canonical Q2_0 の `cpu_require_expert_support()` は `cpu_features()` を直接使用。
- `src/kernels/cpu/expert_layout.cpp:356-373`: Q2_0 行計算と activation quantizer の AVX-512 → AVX2 → AVX1 dispatch。
- `src/kernels/cpu/native_expert.cpp:143-193,204-225`: Native expert の i-quant gate/up の AVX-512 / AVX2 / ggml-cpu 選択、および NVFP4 の fallback。
- `src/program/generate.cpp:2898-2907`: Native pack の AVX-512 不在時の stderr ログ。
- `include/strata/kernels/cpu/expert_layout.hpp:44-51`: ヘッダー上の機能説明。`STRATA_FORCE_AVX2` が AVX2 判定自体には影響しない旨を記載。
