# `STRATA_DENSE_MMQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP コンパイラで `STRATA_PREFILL_MMQ` を定義してビルドした場合に、prompt の native GGUF block を使う dense GEMM を MMQ 経路へ切り替える opt-in です。通常の経路は重みを FP16 scratch に dequantize して GEMM を行います。設定が有効でも、MMQ のビルド状態・形式と行数の適合性・行列の K 寸法・scratch 容量・一時バッファ確保が条件を満たさない積は通常経路へ戻ります。`Gemm::native()` から呼ばれる分岐であり、同じ設定名は MMQ prompt kernels のない own-only build でも起動時通知に使われます（`engine/src/prefill/gemm.cu:1390-1406,1489-1538`、`engine/src/prefill/prefill.cpp:2124-2130`）。

## 値と判定

MMQ がある HIP 経路では `std::getenv()` の結果を関数内 `static` に一度保存し、先頭文字が `'1'` かだけを判定します。未設定・空文字・先頭が `1` 以外なら無効です。文字列全体の数値変換、空白除去、大文字小文字変換はしません（`engine/src/prefill/gemm.cu:1395-1399`。SYCL 配置ソースにも同じコードがありますが、同じ `STRATA_PREFILL_MMQ` / `__HIPCC__` の compile guard 内です。Intel Arc build でこの変数が読まれる根拠とはしません: `engine/sycl/src/prefill/gemm.dp.cpp:988-997`）。

MMQ がない own-only build の通知は別の判定です。`dense_mmq_notice()` は未設定、空文字、文字列全体がちょうど `0` のとき通知せず、それ以外は「効果なし」と stderr に出す文字列を返します（`engine/include/strata/prefill/dense_mmq_notice.hpp:10-15`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_PREFILL_MMQ` 定義、`__HIPCC__` 定義の GEMM | 無効 | 先頭が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `0anything`, `true`, ` 1`, `01` |
| `STRATA_PF_OWN_ONLY` の build における通知 | 通知なし | ― | 通知上は空文字と文字列全体が `0` のみ無通知。`0anything`, `false`, ` 0` などは「効果なし」の通知対象 |

## 有効になる条件

- MMQ を使う実行経路は、ソース上 `STRATA_PREFILL_MMQ` と `__HIPCC__` の両方が定義された build に限られます。また、呼び出し側で `beta == 0.0f` かつ入力 row stride が未指定または K と同じ場合にだけ `native_mmq()` を試します（`engine/src/prefill/gemm.cu:1390-1399,1536-1538`）。一方、現行 top-level CMake は llama.cpp の MMQ prompt kernels が tree にないと記しています。したがって macro 条件付き実装の存在だけから、通常の現行 build でこの切替が使えるとは判断できません（`engine/CMakeLists.txt:104-106`）。
- `native_mmq()` 内で MMQ が build 済みであり、対象 GGML type と N が `mmq::fits()` を満たし、K が 8192 以下かつ 256 の倍数で、scratch から算出する chunk row 数 R が 1 以上である必要があります。満たさなければ `false` を返し `Gemm::native()` の通常処理へ進みます（`engine/src/prefill/gemm.cu:1399-1411,1536-1538`）。
- MMQ 用 device buffer の初回確保に失敗した場合は `mmq_failed_` を立ててこの積を fallback し、同じ Gemm インスタンスでは後続も MMQ を試しません。割当失敗時に Strata 固有のエラー終了や警告文字列を出す分岐は確認できません（`engine/src/prefill/gemm.cu:1420-1425`）。
- `STRATA_PF_OWN_ONLY` build は MMQ kernels なしで、Dense MMQ の実行分岐とは別です。prompt expert layout に layer があるときの `mmq_plan()` 初期化中に設定値を読み、「効果なし」の通知を最大一度出します。該当する build でも layer 数が 0 以下ならこの通知ブロックには入りません（`engine/src/prefill/prefill.cpp:2026-2039,2099-2130`）。
- CLI 引数、設定ファイル、他の環境変数による優先順位や上書きはこの名前の読み取り経路にありません。`STRATA_DENSE_MMQ` は `STRATA_PREFILL_MMQ` とは別の変数です。

## 実行時の詳細

MMQ 対応経路では、最初に `Gemm::native_mmq()` に入った際に `enabled` を static 初期化します。その後、MMQ 適合条件を通った積の FP16 activation を FP32 に変換し、量子化して MMQ product を実行します。T 行は R 行以下の chunk に分けられます。最初の MMQ buffer 確保成功時に有効ログを一度出します。環境変数をプロセス起動後に変更しても、static 初期化済みの `enabled` には反映されません（`engine/src/prefill/gemm.cu:1395-1411,1420-1457`）。

MMQ がない own-only build では、`mmq_plan()` の static 初期化経路で通知判定が一度行われます。環境変数の変更を再読するリクエスト単位の処理ではありません（`engine/src/prefill/prefill.cpp:2026-2037,2124-2130`）。

## ログと測定値

- 有効な MMQ buffer を初めて確保したときの stderr: `prefill gemm: dense MMQ on (STRATA_DENSE_MMQ=1)`（`engine/src/prefill/gemm.cu:1420-1428`）。
- own-only build で値が未設定・空・ちょうど `0` 以外の場合の stderr: `strata: STRATA_DENSE_MMQ has no effect in this engine (it has no MMQ kernels): the dense projections of a prompt run on the FP16 path.`（`engine/include/strata/prefill/dense_mmq_notice.hpp:12-15`、出力箇所 `engine/src/prefill/prefill.cpp:2124-2128`）。
- 指定値を設定した結果として Strata が必ず終了するエラー経路はありません。MMQ 固有の適合条件や確保失敗で false が返ると通常経路が続きます（`engine/src/prefill/gemm.cu:1399-1410,1420-1425,1536-1538`）。
- 性能測定値は記載しません。リポジトリの `docs/AMD_HIP.md:273` は「0.2.16 以降 MMQ kernels がないため効果なし」と記載していますが、現行ソースには MMQ 有効時の `native_mmq()` 分岐と、MMQ 無し build で効果なしと通知する別経路があります。適用は当該 compile macro 条件に限定されるため、文書の旧記述を全 build に一般化しません（compile 条件 `engine/src/prefill/gemm.cu:1390-1391,1536-1538`）。

## 根拠

- `engine/src/prefill/gemm.cu:1390-1457` — MMQ build guard、値の読み取り、適合判定、buffer 確保、MMQ product と有効ログ。
- `engine/src/prefill/gemm.cu:1489-1538` — `Gemm::native()` の stride / beta 条件と fallback 呼び出し。
- `engine/sycl/src/prefill/gemm.dp.cpp:988-1052` — 同じ macro 条件下にある SYCL 配置ソースの MMQ GEMM 実装。
- `engine/include/strata/prefill/dense_mmq_notice.hpp:10-15` — MMQ 無し build の通知値判定と文言。
- `engine/src/prefill/prefill.cpp:2026-2039,2099-2130` — `mmq_plan()` 初期化、own-only 条件、通知の一度だけの出力。
