# `STRATA_IQ256_GATHER`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

Native expert の AVX2 i-quant 複数 token カーネルで、量子化コードブックの値を scalar load で組み立てるか、AVX2 gather 命令で読むかを選びます。制御対象は Strata の gather variant 選択です。両方の variant は同じビットを計算する、とカーネル実装は説明しています。環境変数自体についての性能測定資料は確認できませんでした。

## 値と判定

`src/kernels/cpu/expert_layout.cpp:210-216` で `std::getenv` した値を一度だけ読みます。

| 値 | 設定値 | 選択 |
|---|---:|---|
| 未設定 | `-1` | 自動。実行スレッドのコアで gather が速いと判定された場合だけ gather variant |
| 空文字 | `-1` | 未設定と同じ自動判定 |
| 空でない値で `std::atoi(value) == 0` | `0` | scalar decode を全コアで選ぶ |
| 空でない値で `std::atoi(value) != 0` | `1` | gather decode を全コアで選ぶ |

空文字以外は文字列全体の比較ではなく `atoi` です。したがって `1`, `-1`, `2`, `1abc` は gather を選び、`0`, `abc`, `0abc` は scalar decode を選びます。先頭の空白や符号は `atoi` の規則で処理されます。無効な数値文字列専用の警告や fallback ログはありません。

## 有効になる条件

- 対象は Native expert の CPU AVX2 i-quant gate/up カーネルで、カーネルが有効な IQ2_XXS、IQ2_XS、IQ3_XXS、IQ3_S、IQ2_S、IQ4_XS が候補です。AVX2 カーネル選択自体には CPU/OS の AVX2 対応と `STRATA_NO_IQ256` が関わり、AVX-512対応 CPU は通常 gate/up で AVX-512 カーネルを優先します（`src/kernels/cpu/native_expert.cpp:143-190`）。
- gather と scalar の実装差があるのは IQ3_XXS（type 118）、IQ3_S（121）、IQ2_S（122）のコードブック decode です。IQ2_XXS、IQ2_XS、IQ4_XS はこの設定で選ぶ variant が変わっても、gather 用の decode 特殊化を持たず同じ decode を使います（`src/kernels/cpu/iq_avx2.cpp:293-345` および各 `Fmt32` 実装）。
- `=1` など非ゼロを指定すると自動の CPU 適性判定を上書きし、AVX2 カーネルが呼ばれる場合には全コアで gather を選びます。これは gather の実行速度を保証する指定ではありません。
- 未設定または空文字の自動判定は、Intel CPU で AVX-VNNI があり、特定の E-core 専用モデルに該当しないことを `cpu_gather_fast()` で調べます。ハイブリッド CPU では呼び出しスレッドが P-core かも調べ、P-core なら gather、E-core なら scalar decode を選びます。非 Intel CPU や判定条件を満たさない CPU は scalar decode です（`src/kernels/cpu/expert_layout.cpp:219-257`）。
- `STRATA_IQ3S_MT1` による IQ3_S の単一 token AVX2 経路では、この値が `0` のとき gather 条件が成立せず、`STRATA_IQ3S_MT1` の効果も抑止されます。未設定・空文字は `-1` なので、この条件だけでは抑止しません（`src/kernels/cpu/native_expert.cpp:124-140`）。

## 実行時の詳細

値は `iq256_gather_setting()` が最初に呼ばれた際に関数内の `static const int` へ保存されます。その後プロセス内で環境を変更しても値は再読込されません。自動判定では `cpu_gather_fast_here()` が実行スレッドごとにコア種別を thread-local に一度保存するため、同じプロセスの P-core と E-core で variant が異なる場合があります。明示的な `0` / 非ゼロ指定ではそのコア別差を使いません。

`iq256_variant()` はこの gather bit と、独立して判定する AVX-VNNI bit を組み合わせます。gate/up の AVX2 行計算は選ばれた variant を `iq256_gu_rows_v()` に渡し、`Fmt32<118>`, `<121>`, `<122>` の gather decode を使うか決めます。Native expert pool が gate/up 行処理を呼ぶ経路で適用されます（`src/kernels/cpu/iq_avx2.cpp:456-500`、`src/kernels/cpu/pool.cpp:705-708`）。IQ4_NL down 行は別カーネルであり、この gather 設定の対象ではありません（`src/kernels/cpu/native_expert.cpp:233-255`）。

通常の Strata 実行経路に、この設定の値を表示するログは見つかりませんでした。AVX2 parity 診断実行ファイルは環境値と選択 variant を表示しますが、診断用表示です（`src/kernels/cpu/iq_avx2_parity.cpp:533-541`）。

`docs/DETAILS.md:97-105` は `STRATA_IQ3S_MT1` と、未設定時の IQ3_S gather 自動選択に言及します。これは上記のコードと整合しますが、`STRATA_IQ256_GATHER` 自体の値判定や全フォーマットへの効果は同資料では説明されていません。

## 根拠

- 値の読み取り、空文字の扱い、`atoi`、static cache: `src/kernels/cpu/expert_layout.cpp:210-216`
- 自動時の Intel / AVX-VNNI 条件と P-core / E-core 判定: `src/kernels/cpu/expert_layout.cpp:219-257`
- gather 特殊化の対象と gather 命令: `src/kernels/cpu/iq_avx2.cpp:276-345`
- variant の選択と AVX2 行計算への適用: `src/kernels/cpu/iq_avx2.cpp:456-500`
- Native expert における AVX2 kernel の条件と `STRATA_IQ3S_MT1` との相互作用: `src/kernels/cpu/native_expert.cpp:124-190`
- Native expert pool から gate/up 行処理への呼び出し: `src/kernels/cpu/pool.cpp:705-708`
- down 行の別経路: `src/kernels/cpu/native_expert.cpp:233-255`
- 診断時の値・variant 表示: `src/kernels/cpu/iq_avx2_parity.cpp:533-541`
- 関連する利用者向け説明: `docs/DETAILS.md:97-105`
