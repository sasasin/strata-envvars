# `STRATA_QIL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA verify window 内で、投影入力の Q8_1 量子化と interleaved copy の作成を一つのカーネル起動にまとめる経路を選びます。通常経路は `native_quantize_q8_1` で量子化し、interleaved matvec が必要なら後で `native_q8_1_interleave` を呼びます。まとめた経路は `native_quantize_q8_1_il` を呼び、同じ Q8_1 データと interleaved copy を作って後続の interleaved matvec に渡します。コードコメントは Turing 系での既定選択と起動数削減を記していますが、設定値による明示的な有効化は GPU 世代に限定されません。`engine/src/core/verify.cpp:1832-1846,1848-1857`

## 値と判定

`quant_in` 内の関数ローカル `static` が `std::getenv("STRATA_QIL")` を一度読み、設定されていれば `std::atoi` で変換します。文字列全体の検証はなく、空文字・数値で始まらない文字列・`0anything` は `0`、`1anything` は `1` になります。先頭空白や符号は `atoi` の規則で処理されます。変換結果が負なら未設定と同じく GPU 既定値へ進みます。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 非 HIP の verify window | `qil_env=-1`。compute capability 7.5 かつ `STRATA_SM75_PERF` が非ゼロなら既定 ON、それ以外は OFF | `atoi` 結果が正（例: `1`, `2`, `1tail`） | `atoi` 結果が 0（例: `0`, `0anything`, 空文字, `true`）は OFF。負値（例: `-1`, `-2`）は GPU 既定値に戻る |
| HIP build | この環境変数を読むコードが `#if !defined(STRATA_USE_HIP)` 内にないため、値にかかわらず通常の量子化経路 | 該当なし | 該当なし |

判定は `engine/src/core/verify.cpp:1835-1846`、Turing 既定値は `engine/src/core/verify.cpp:473-488` と `engine/include/strata/core/sm75_series.hpp:24-37` にあります。`STRATA_SM75_PERF` は同じヘッダーで一度読み、`atoi(e) != 0` なら Turing 系を既定有効にします。

## 有効になる条件

- `Verifier::record_window` の CUDA 経路で `quant_in` が呼ばれること。Metal は verifier 初期化時に専用 window 実装へ渡して戻るため、この `record_window` 経路を使いません。`engine/src/core/verify.cpp:978-993,1468-1473`
- 対象 window group の行数 `n` が 2〜4 であること。1 行および 5 行以上では通常量子化を使います。`engine/src/core/verify.cpp:1838-1846`
- `STRATA_MMVQ_IL` が interleaved 経路を許可すること。同変数は未設定なら ON、値の先頭文字が `'0'` なら OFF で、関数ローカル `static` に一度保存されます。OFF の場合 `STRATA_QIL` が正値でも合成量子化経路を使いません。`engine/src/core/verify.cpp:192-194,1838-1846`
- 後続の重み型・出力幅が `native_mmvq_il_supported` を満たす場合に限り、`mm` は interleaved matvec を実行します。満たさない場合は通常の `native_mmvq` へ進むため、合成経路で用意した interleaved copy が利用されないことがあります。`engine/src/core/verify.cpp:1848-1857`
- GDN/QSA の一部入力量子化は既存の Q8_1 出力を再利用するときにスキップされます。GDN 入力は `q8_attn` が真ならスキップし、GDN 出力は `STRATA_QFUSE` が有効かつ batch でないときスキップします。`engine/src/core/verify.cpp:1905-1906,2009-2013,2059-2061`

## 実行時の詳細

`STRATA_QIL` はプロセス起動時ではなく、その verifier 内で最初に `quant_in` が呼ばれた時点で評価され、関数ローカル `static` にキャッシュされます。その後の環境変更はこの verifier の判定に反映されません。未設定または負値の場合に使う `device_is_sm75()` は device ごとに compute capability 判定をキャッシュし、Turing 既定値には `STRATA_SM75_PERF` が必要です。`engine/src/core/verify.cpp:1835-1839,473-488`; `engine/include/strata/core/sm75_series.hpp:24-37`

`quant_in` は GDN の mixer 入力・出力と QSA の attention query 入力・出力の量子化から呼ばれます。QIL 経路を選ぶと `xq_` と `xil_` の双方を生成し `il_ready` を立てます。続く `mm` は、対象形式で interleaved matvec が対応していればこの copy を使い、まだ用意されていない場合だけ別途 interleave を生成します。通常経路では Q8_1 の値そのものは従来の量子化関数が作り、必要に応じて後続で interleave します。`engine/src/core/verify.cpp:1835-1857,1905-2013,2059-2061,2278-2288,2328-2340,2592-2606`

CLI 引数による上書きはありません。既定選択との優先順位は、非負の `STRATA_QIL` 変換値が GPU 既定値に優先し、負値または未設定は GPU 既定値を使います。GPU 既定値は compute capability 7.5 かつ `STRATA_SM75_PERF` が非ゼロの場合だけ ON です。interleaved matvec 自体の可否には別途 `STRATA_MMVQ_IL` とカーネル対応形式が関与します。`engine/src/core/verify.cpp:1837-1839,1848-1857`; `engine/include/strata/core/sm75_series.hpp:24-43`

## ログと測定値

`STRATA_QIL` の値や選択経路を直接表示するログはありません。`quant_in` の呼び出し元を含む verify layer 処理で例外が発生すると `err` に `verify layer <番号>: <例外文字列>` を設定して失敗を返します。`engine/src/core/verify.cpp:2608-2610`。

`docs/DETAILS.md:1340-1346` は変数名を Turing opt-in 一覧に含めていますが、実装上は `STRATA_QIL=1` が非 HIP build で Turing 以外にも明示有効化できます。`terminal/data/settings-register.json:40297-40305` は backend を `cuda-hip` と記録していますが、実際の読み取り箇所は `#if !defined(STRATA_USE_HIP)` 内です。`docs/DETAILS.md:1810` の decode `+1.8%` は `STRATA_GRAPH_PRIO=1` の列にある値であり、QIL 単独の測定値ではありません。ソースコメント `engine/src/core/verify.cpp:1832-1834` の「+0.5..+1 % decode」「GDN/QSA layer あたり二起動減」は測定条件を示していないため、ここでは一般的な性能値として扱いません。

## 根拠

- `engine/src/core/verify.cpp:1832-1857` — 値の読み取り、判定、量子化経路、interleaved matvec の利用条件。
- `engine/src/core/verify.cpp:473-488`、`engine/include/strata/core/sm75_series.hpp:24-43` — GPU 既定値と `STRATA_SM75_PERF`。
- `engine/src/core/verify.cpp:978-993,1905-2013,2059-2061,2278-2288,2328-2340,2592-2610` — Metal 初期化分岐、呼び出し箇所、Q8_1 再利用、例外経路。
- `terminal/data/settings-register.json:40297-40305` — settings register の backend 記録。
- `docs/DETAILS.md:1340-1346,1810` — 資料との照合。
