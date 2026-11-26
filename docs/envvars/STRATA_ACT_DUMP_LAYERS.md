# `STRATA_ACT_DUMP_LAYERS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_ACT_DUMP_LAYERS` は、CPU native-expert の量子化入口で second moment を集計する層番号のリストを指定する。これは診断用の出力であり、変数単独では有効にならない。別途 `STRATA_ACT_DUMP` に空でないファイル prefix が必要で、未指定なら収集処理は無効のままになる。値を読むのは `engine/src/kernels/cpu/native_expert.cpp` の `ActDump` である（同ファイル `:432-436,449-465`）。

対象の値は、gate/up 入力（token の hidden state）と down 入力（SwiGLU 出力）である。Hadamard-folded 層では expert の基底に合わせて回転した後、量子化する前のベクトルを集計する。出力は選択されたベクトルの各要素の二乗和と件数であり、`STRATA_ACT_DUMP_COV` が有効な場合は要素間の積和も加える。元のベクトルを変更する分岐ではなく、通常の量子化処理は続けて実行される（`engine/src/kernels/cpu/native_expert.cpp:488-505,514-537`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_ACT_DUMP` が未設定または空 | `STRATA_ACT_DUMP_LAYERS` の値にかかわらず無効 | prefix が非空で、リストから実在する層番号が選ばれる（例 `10,20`） | prefix が未設定または空なら、リストも読み取られず無効 |
| `STRATA_ACT_DUMP` が非空 | 空文字は設定済みとして読み取られるが、空リストなので無効 | カンマ区切り各要素の `std::atoi` 結果に一致する層（例 `10,20`） | 層番号と一致しない値、または実行経路で呼び出しがない場合は記録されない |

変数が未設定なら選択層はなく、空文字でもリストは空のままなので機能は有効にならない。パーサーは文字列をカンマで分け、各部分を `std::atoi` に渡す。文字列全体の妥当性検査はなく、先頭の整数として解釈できる部分が使われるため、`10tail` は `10`、`0anything` は `0` になる。先頭の空白と符号も `atoi` の規則で処理され、変換できない部分は `0` になる。たとえば `10,,20` は `10,0,20` 相当、`,10` は `0,10` 相当になる。大文字小文字は数値変換に関係せず、範囲検査・重複除去は明示的に行われない。末尾カンマの後ろには空要素を追加しない（`engine/src/kernels/cpu/native_expert.cpp:450-464`）。

番号は 0 始まりで、`NativeFmt.layer` に層配列の添字が設定される。したがって `10,20` は内部添字 10 と 20 を選ぶ（`engine/src/kernels/cpu/expert_layout.cpp:619`）。範囲外の値はパース時に拒否されず、実際に同じ番号で記録関数が呼ばれない限り何も記録しない（`engine/src/kernels/cpu/native_expert.cpp:488-490`）。

## 有効になる条件

- `STRATA_ACT_DUMP` が空でないこと。prefix がなければコンストラクターはそこで戻り、`STRATA_ACT_DUMP_LAYERS` を読み取らない（`engine/src/kernels/cpu/native_expert.cpp:449-455`）。
- 層リストが空でなく、通常の実行中に選択層の `native_quant_act` または `native_quant_h` が呼び出されること。両入口はそれぞれ gate/up と down のベクトルを記録する（`engine/src/kernels/cpu/native_expert.cpp:488-490,514-537`）。
- native experts を使う経路であること。`STRATA_NATIVE_EXPERTS` を無効にして native expert pack を読み込むと失敗し、対応コードも native experts 無効ビルドではスタブになる（`engine/src/kernels/cpu/expert_layout.cpp:488-498,512-514`）。通常の native expert pack では `native_quant_act` の呼び出し元に CPU expert dispatch と prefill がある（`engine/src/core/expert_source.cpp:5747-5757`, `engine/src/prefill/prefill.cpp:6277-6297`）。Qwen35 CUDA エンジンにも CPU 側の expert 行を用意する経路がある（`engine/src/qwen35/q36_engine.cu:3325-3353`）。
- Q2_0 専用の activation 量子化経路では `native_quant_act` を通らず `act_quant_any` を使う箇所があるため、その入力はこの診断集計の対象外（`engine/src/core/expert_source.cpp:5752-5757`, `engine/src/prefill/prefill.cpp:6281-6287`）。
- CLI 引数や設定ファイルによるこの層リストの上書きは、調査したソース内に見つからない。`STRATA_ACT_DUMP_COV` は別の任意設定で、値を `atoi` して非ゼロなら共分散を加算する（`engine/src/kernels/cpu/native_expert.cpp:453`）。

## 実行時の詳細

`ActDump` は `act_dump()` の関数内 static ポインターで初回アクセス時に一度だけ生成される。通常の呼び出し元では `native_quant_act` / `native_quant_h` に到達した時点で初めて読み込まれ、その後プロセス内で環境変数を変更しても prefix・層リスト・共分散設定は再評価されない（`engine/src/kernels/cpu/native_expert.cpp:449-471,514-537`）。

選択層で記録関数が呼ばれるたび、対象ベクトルの要素ごとの二乗を double で累積し、ベクトル件数を加算する。共分散が有効なら要素ごとの全組み合わせの積も累積する。データは `<prefix>_L<layer>_gu.bin` または `<prefix>_L<layer>_dn.bin` に書かれ、先頭から `int64 n`、`int64 count`、`double sum(x^2)[n]`、共分散有効時は `double sum(x*x^T)[n*n]` の順である。選択した層・種別に記録がないファイルは作られない（`engine/src/kernels/cpu/native_expert.cpp:473-505`）。

累積データは共分散なしでは記録 2,000 件ごと、共分散ありでは 400,000 件ごとに全 accumulator を flush し、終了時にも flush を登録する。書き込みは `.tmp` ファイルに行ってから最終名へ rename する。ファイルを開けないときはそのファイルを飛ばし、書き込み・rename の戻り値も検査しない（`engine/src/kernels/cpu/native_expert.cpp:465,473-486,506-509`）。

## ログと測定値

この処理に対応するログ・警告・失敗メッセージは実装にない。出力ファイルの open 失敗は黙ってスキップされる。Strata の測定値を記載する資料も見つからなかった（出力経路は `engine/src/kernels/cpu/native_expert.cpp:473-486`）。

## 根拠

- 環境変数の読み取り、リストの変換、static cache: `engine/src/kernels/cpu/native_expert.cpp:449-471`
- 記録対象と量子化入口: `engine/src/kernels/cpu/native_expert.cpp:488-537`
- ファイル形式、flush、終了時処理: `engine/src/kernels/cpu/native_expert.cpp:465,473-509`
- 0 始まりの層番号と native-expert build 条件: `engine/src/kernels/cpu/expert_layout.cpp:488-498,512-514,619`
- 通常実行での呼び出し例と Q2_0 の分岐: `engine/src/core/expert_source.cpp:5747-5757`, `engine/src/prefill/prefill.cpp:6277-6297`, `engine/src/qwen35/q36_engine.cu:3325-3353`
