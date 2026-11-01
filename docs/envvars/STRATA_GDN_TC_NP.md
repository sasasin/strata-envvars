# `STRATA_GDN_TC_NP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の GDN（DeltaNet recurrence）prefill で、通常の tensor-core scan が失敗した後に試す split scan の pass 数を選びます。Strata の通常の CUDA 自動 dispatch が対象で、`STRATA_GDN_TC` が有効、かつ入力 token 数が 128 以上であることに加え、最初の非 split tensor-core scan が失敗した場合にだけ値が参照されます。既定は 3 pass です。これは実験用の fallback 選択であり、通常の成功経路や明示的に probe で強制された経路は変えません。

## 値と判定

値は `std::getenv` で読み、`std::atoi` で整数変換した後、結果が `1` または `2` のときだけ採用します。それ以外は `3` にします。文字列全体の妥当性検証はしません。

| 環境値 | 採用される pass 数 |
|---|---:|
| 未設定 | 3 |
| 空文字 | 3（`atoi("")` は 0） |
| 先頭から整数変換した結果が 1 | 1 |
| 先頭から整数変換した結果が 2 | 2 |
| その他（0、3、負値、整数に変換できない文字列など） | 3 |

`atoi` のため、たとえば `1abc` や `1.5` は変換結果が 1 となり 1 pass、`2anything` は 2 pass になります。先頭の空白や符号も `atoi` の変換規則に従います。数値変換可能範囲を超える文字列の結果は、この実装では保証されません。

## 有効になる条件

- CUDA の `src/prefill/kernels.cu` にある通常の自動 dispatch が使われること。tensor-core の自動経路は `#if !defined(__HIPCC__)` 内です。HIP の recurrence 分岐ではこの変数を読みません。
- `STRATA_GDN_TC` が設定され、`atoi` の結果が 0 以外であること。
- recurrence の token 数 `T` が 128 以上であること。
- `GdnProbe` が別経路を強制していないこと（probe はテスト用）。
- 通常の非 split tensor-core scan が失敗し、その後の split scan fallback に到達すること。

通常 scan が成功すればこの変数は読み取られず、split scan の pass 数には影響しません。通常 scan が失敗して split scan も失敗した場合は、利用可能なら `STRATA_GDN_CHUNKED` の経路を試し、そこも選ばれなければ `STRATA_GDN_PIPELINE` による key-head / pipelined columns / columns の既定 recurrence に進みます。`T < 128` では tensor-core 自動経路自体を試しません。CLI 引数による上書きはこの実装にありません。

## 実行時の詳細

`gdn_recurrence_impl()` の自動 CUDA dispatch は `STRATA_GDN_TC` と `T >= 128` を確認して、まず `gdn_rec_tc(..., split=false)` を呼びます。これが成功すればその経路を選択し終了します。失敗したときだけ関数内 static local の `tc_np` が初期化され、環境値を一度読みます。したがって評価はプロセス起動時とは限らず、最初の該当 fallback 時です。その初期化後に環境値を変えても同一プロセスでは再評価されません。該当 fallback に一度も到達しなければ読み取りも起きません。

採用値は `gdn_rec_tc(..., split=true, np=tc_np, ...)` に渡されます。split scan は値に応じて `gdn_tc_scan_kernel` の `NPV=1`、`NPV=2` または既定の 3 pass 版を起動します。split scan が成功すれば `kGdnTcSplit` を選び、通常の後段 norm を融合できる条件では融合し、そうでなければ別の norm kernel を実行します。実装コメントは 1/2 pass を「experiment, not a default」としていますが、性能や出力への影響をこの調査で新たに測定していません。

通常 scan はデバイス属性が取得できない、compute capability が 8 未満、SM 数が不足、必要な shared memory が不足、または scratch allocation が失敗した場合などにエラーを返し得ます。split scan も失敗し、chunked path も使えない場合は通常 recurrence に戻ります。自動 dispatch の probe がある場合、失敗理由や選択 path は probe の記録欄に入り得ますが、Strata の通常利用者向けログとしてこの環境変数の値や選択結果を出力する箇所は見つかりませんでした。GPU kernel launch error は共通 `check()` が `prefill <処理名>: <CUDA error>` を stderr に出し、終了コード 1 で終了します。

## 根拠

- `src/prefill/kernels.cu:2878-2883,2982-2999` — recurrence dispatch、HIP 分岐と非 HIP の CUDA dispatch、tensor-core の opt-in 判定。
- `src/prefill/kernels.cu:935` — tensor-core 自動経路の最小 `T=128`。
- `src/prefill/kernels.cu:3027-3057` — 通常 scan の試行、失敗後に限る `STRATA_GDN_TC_NP` の読み取り、split scan、失敗時の後続 fallback。
- `src/prefill/kernels.cu:1308-1368` — tensor-core scan のデバイス条件と `np` に応じた split kernel 選択。
- `src/prefill/kernels.cu:103-104,3068-3071` — CUDA error の stderr 出力と終了。
- `src/prefill/prefill.cpp:3824-3831,6953-6957` — prefill GDN recurrence の呼び出し箇所。
