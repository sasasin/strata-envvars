# `STRATA_NO_NVFP4_256`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CPU の native expert 経路で使う NVFP4 の AVX2（256-bit）行カーネルを無効にする設定である。未設定なら AVX2 対応 CPU で条件を満たした NVFP4 gate/up と down の行計算に専用カーネルを選び、設定されていれば通常の `traits(...).dot` 経路へ進む。GPU の NVFP4 処理を切り替える設定ではない。行関数は CPU expert pool から呼ばれる（`engine/src/kernels/cpu/pool.cpp:1290-1296`, `1418-1429`）。

## 値と判定

値の内容は parse せず、`std::getenv(...) == nullptr` かどうかだけを見る。したがって未設定だけが AVX2 カーネルを許可し、空文字を含む何らかの設定値はすべて無効化する。`1`、`0`、`true`、`false`、`0anything` の違い、大文字小文字、空白、数値としての妥当性は判定しない（`engine/src/kernels/cpu/native_expert.cpp:727-732`, `854-857`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| AVX2 条件を満たす CPU | 256-bit NVFP4 行カーネルの候補になる | なし | 空文字、`0`、`1`、`true`、`false`、任意の文字列すべて |
| AVX2 条件を満たさない CPU | AVX2 カーネルは使われない | なし | 値にかかわらず同じ |

AVX2 対応判定自体は CPU/OS の AVX 状態と AVX2・FMA・F16C を確認し、関数内で一度キャッシュする（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。

## 有効になる条件

- CPU backend の native expert 行計算がこの実装を使うこと。対象形式が NVFP4 であることが gate/up 側 `f.gu_type == kNvfp4Type`、down 側 `f.d_type == kNvfp4Type` で確認される（`engine/src/kernels/cpu/native_expert.cpp:729-731`, `854-857`）。
- AVX2 カーネルを実行できる CPU/OS であること（`engine/src/kernels/cpu/expert_layout.cpp:206-238`）。
- 寸法 `n` が NVFP4 のブロック幅の倍数で、ブロック数がカーネル上限以下であること（`engine/src/kernels/cpu/nvfp4_avx2.cpp:161`）。条件を満たさない場合は通常の dot 経路へ進む。
- AVX-512 NVFP4 カーネルが利用可能で、`STRATA_NO_NVFP4_512` が未設定、かつ寸法条件も満たす場合は、AVX2 判定より先に AVX-512 側が実行される。そのためこの変数を設定しても、その gate/up または down 計算の選択には影響しない。AVX-512 が使えない、無効化されている、または寸法条件を満たさない場合に、この変数の AVX2 判定まで到達する（`engine/src/kernels/cpu/native_expert.cpp:720-732`, `849-857`）。
- CLI 引数やモデル状態による別の上書きはこの分岐にはない。CPU ISA 対応、NVFP4 の形式・寸法、先行する AVX-512 分岐が適用可否を決める。

## 実行時の詳細

gate/up と down のそれぞれで、`native_gu_rows_impl` / `native_down_rows_impl` 内の関数ローカル `static const bool` として初回評価時に読み取る。これらはテンプレートの `NativeArithmetic` ごとに保持される。評価後にプロセス環境を書き換えても再評価されず、読み取り後の変更は反映されない（`engine/src/kernels/cpu/native_expert.cpp:560-561`, `727-732`, `793-794`, `854-857`, `898-915`）。

条件を満たして AVX2 カーネルに入ると gate/up は `nvfp4_256_gu_rows`、down は `nvfp4_256_rows` を実行して戻る。未設定でも AVX2 条件または寸法条件を満たさない場合、および設定済みの場合は `traits(f.gu_type).dot` / `traits(f.d_type).dot` の通常の行計算へ進む（`engine/src/kernels/cpu/native_expert.cpp:729-735`, `854-861`, `769-789`, `885-892`）。通常の dot の実体はビルドの `STRATA_OWN_CPU_QUANT` により Strata の量子化層または ggml-cpu の traits によって決まる（`engine/src/kernels/cpu/native_expert.cpp:19-21`, `734-739`, `859-864`; `engine/cmake/backends/cpu.cmake:370-373`）。

## ログと測定値

この分岐は設定値や選択結果を出力せず、無効値エラーや専用の終了経路もない。観測できる変化は、条件を満たす NVFP4 CPU expert 行計算が AVX2 専用カーネルを使うか通常の dot 経路へ進むかである（`engine/src/kernels/cpu/native_expert.cpp:727-735`, `854-861`）。ソースコメントには性能測定への言及があるが、本変数の実行時ログや再測定結果ではないため、ここでは測定値として扱わない。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:720-735` — gate/up の AVX-512 優先、AVX2 の環境変数判定、fallback。
- `engine/src/kernels/cpu/native_expert.cpp:847-861` — down の NVFP4 scale、AVX-512 優先、AVX2 の環境変数判定、fallback。
- `engine/src/kernels/cpu/native_expert.cpp:560-561`, `793-794`, `898-915` — 行実装と `Default` / `WindowInvariant` の呼び出し。
- `engine/src/kernels/cpu/expert_layout.cpp:206-238` — AVX2 実行可否の CPU/OS 判定と cache。
- `engine/src/kernels/cpu/nvfp4_avx2.cpp:161-195` — NVFP4 寸法条件と AVX2 gate/up・down カーネル。
- `engine/src/kernels/cpu/pool.cpp:1290-1296`, `1418-1429` — CPU expert pool から native gate/up 行関数への呼び出し。
