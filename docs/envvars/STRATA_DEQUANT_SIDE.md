# `STRATA_DEQUANT_SIDE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の prompt prefill で、GEMM 用の dense weight を FP16 に dequantize する処理を compute stream ではなく side stream に送り、2 個の scratch を交互に使います。side stream の dequantize と、先行する compute stream の kernel を重ねるための opt-in です。GEMM の計算自体は compute stream に残ります。

これは Strata が値を読み取る環境変数です。HIP では常に無効、Metal では `gemm_dequant_side()` が false を返すため、設定値は機能を有効にしません。

## 値と判定

CUDA 実装は値全体を parse せず、最初の文字だけを `'1'` と比較します（`src/prefill/gemm.cu:630-637`）。

| 状態・値 | CUDA の判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みだが `v[0]` は `\0`） |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 有効 |
| それ以外（例: `0`, `true`, ` 1`, `-1`） | 無効 |

大文字小文字、数値としての妥当性、後続文字は検査されません。既定値は無効です。CLI 引数や別の設定値による上書きは実装にありません。判定結果は関数内の `static const bool` に保存され、プロセス中の最初の呼び出し後に環境を変更しても再評価されません。最初の呼び出しは prompt buffer のサイズ計算または初期化から起こり得ます（`src/prefill/prefill.cpp:1728-1735, 2528-2549`）。

## 有効になる条件

- CUDA build であり、prompt prefill が `Prefill` の GEMM 経路を使うこと。Metal の `Prefill::init` は別の window 経路へ戻り、Metal stub の `gemm_dequant_side()` は常に false です（`src/prefill/prefill.cpp:1538-1547`, `metal/src/engine/stubs_0145.cpp:163-165`）。
- `Gemm::native()` が dense weight を通常の native dequant/GEMM 経路で処理し、`N*K <= scratch_elems_` であること。scratch に収まらない行分割では dequantize と GEMM を順に行い、side stream は使いません（`src/prefill/gemm.cu:1426-1458`）。
- 2 個目の scratch を確保でき、side stream とイベントを作成できること。設定が有効だと `Prefill` の借用 buffer の計算・割当てに GEMM scratch 1 個分が追加されます（`src/prefill/prefill.cpp:1731-1735, 1896-1900, 2539-2549`）。

CUDA 以外の backend では無効です。HIP では `__HIPCC__` 分岐が無条件に false を返します。また、HIP の MMQ/padded GEMM 固有経路にこの side-stream 機能を適用する実装はありません（`src/prefill/gemm.cu:630-637, 1393-1395`; `include/strata/prefill/gemm.hpp:148-151`）。

同じ CUDA GEMM で `STRATA_PF_W16_CACHE_MIB` が有効でも `side_scratch_` があると weight cache 経路を通らず、side-stream dequant 経路へ進みます（`src/prefill/gemm.cu:1396-1424`）。

## 実行時の詳細

`Prefill` は有効判定時に 2 個目の `GEMM_SCRATCH` を buffer layout に加え、`Gemm::set_dequant_side()` に渡します。関数は side stream と、scratch ごとの ready/free event を一度作成し、compute stream 上で両 scratch の初期 free event を記録します（`src/prefill/prefill.cpp:1728-1735`, `src/prefill/gemm.cu:705-735`）。borrowed layout を組み直す場合も、判定結果に合わせて scratch を取り直し、`set_dequant_side()` を呼びます（`src/prefill/prefill.cpp:1876-1901`）。

scratch に収まる `Gemm::native()` 呼び出しでは、前回の GEMM が scratch を読み終える free event を待って side stream で dequantize し、ready event の後に compute stream の GEMM を実行します。読み取り完了を free event で記録してから次の scratch に切り替えます（`src/prefill/gemm.cu:1440-1454`）。コードのコメントとヘッダーは、serial 形式と同じ kernel/product 値になる設計と記載しています（`src/prefill/gemm.cu:1441-1445`, `include/strata/prefill/gemm.hpp:70-75`）。この調査では build や GPU 実行による照合はしていません。

side stream または event の作成に失敗すると、`set_dequant_side()` はエラー文を返し `side_scratch_` を null に戻します。呼び出し元は stderr に `prefill: STRATA_DEQUANT_SIDE=1 not taken (%s): the dense weights are dequantized in front of their GEMMs` を出し、serial 経路に戻ります（`src/prefill/gemm.cu:709-728`, `src/prefill/prefill.cpp:1735,1900`）。2 個目の scratch を含む buffer が収まらない場合は初期化が `prefill: GEMM scratch does not fit` で失敗し、後続の chunk buffer 配置失敗では空きメモリ等を含む `prefill: device buffers ... do not fit` が返されます（`src/prefill/prefill.cpp:1731-1735,1749-1755,1896-1909`）。

## 根拠

- 読み取りと parse、HIP 条件: `src/prefill/gemm.cu:630-637`。
- 2 個目の scratch、初期化、再 layout、サイズ計算: `src/prefill/prefill.cpp:1728-1735,1876-1901,2539-2549`。
- side stream の初期化と失敗処理: `src/prefill/gemm.cu:705-735`。
- GEMM の side-stream / serial 分岐と oversized scratch の分割: `src/prefill/gemm.cu:1426-1458`。
- Metal の無効 stub: `metal/src/engine/stubs_0145.cpp:163-165`。
- `docs/DETAILS.md:1535-1546` は CUDA の opt-in prompt switch として挙げ、`STRATA_DEQUANT_SIDE=1` を含む 4 変数の組み合わせについて prompt が +2.2% から +2.6% と記しています。これは資料に記載された複合条件の値で、この変数単独の効果や別環境での性能を示す値ではありません。
