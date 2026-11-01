# `STRATA_KVA_CAPTURE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

KVA の調査用 capture directory を指定します。prefill 中、設定した split 層以降の各層に入る実入力 residual を `L<layer>.bin` に書き出します。capture 中は近似実行せず、通常どおり正確な層計算を続けます。設定値はディレクトリのパスであり、`1` のような有効化フラグではありません。

## 値と判定

| 値 | 判定・動作 |
|---|---|
| 未設定 | capture しない。 |
| 空文字 | capture しない。`getenv` の結果が非 null でも、先頭が `\0` なら有効化されない。 |
| 空でない文字列 | その文字列をディレクトリとして保存先に使う。文字列比較、数値変換、空白除去、パス検証はない。 |

capture が有効なときだけ `STRATA_KVA_CAPTURE_FP32` も読み取られます。既定は bf16 保存で、同変数が有効なら fp32 で記録します（同変数の判定規則は `include/strata/prefill/kva.hpp:143-146,163-167`）。

## 有効になる条件

- `STRATA_KVA_CAPTURE` は `kva_config()` が作るプロセス共通設定に取り込まれます。`STRATA_KVA` の on/off は capture を止める条件ではありません。近似経路の判定は `decline()` で capture 時に断り、層ループの capture 判定は別に `kva.capture` を使うため、`STRATA_KVA` を unset または `0` にしても capture は行われます（`include/strata/prefill/kva.hpp:108-115,150-167,191-195`; `src/prefill/prefill.cpp:2947-2972,3621-3629,3689-3694`）。
- 層ループの capture 条件は `LB == 0`, `LE < 0` または `LE == g.n_layers`、かつ `l >= kva_split` です。したがって全 trunk を処理する単一 stage の prefill が対象で、layer split された stage では保存しません。split は `STRATA_KVA_SPLIT`（既定 36、実際のループでは 1 以上・層数以下に clamp）で決まり、CLI による別の capture パス指定はありません（`include/strata/prefill/kva.hpp:55-57,85,157-159`; `src/prefill/prefill.cpp:2946-2949,2965,3621-3629`）。
- capture の設定と tap は CUDA/HIP prefill 実装にあります。SYCL は別実装であり、`sycl/src/prefill/prefill.cpp` にこの capture hook はありません。KVA の資料も CUDA/HIP build を対象として記載しています（`CMakeLists.txt:819`; `sycl/CMakeLists.txt:266`; `docs/KVA.md:99-104,180-189`）。

## 実行時の詳細

`kva_config()` の `static const KvaConfig` が `kva_config_from_env()` の結果を保持するため、環境値は初回 `kva_config()` 呼び出し時に読み取られ、その後プロセス内で変更しても再読込されません。呼び出し元には起動時の `src/program/generate.cpp` と prefill の `run_impl()` があります（`include/strata/prefill/kva.hpp:150-195`; `src/program/generate.cpp:6263-6278`; `src/prefill/prefill.cpp:2947-2949`）。

各対象層で、その層へ入る device residual `R` を host にコピーし stream を同期した後、`<directory>/L<layer>.bin` に追記相当のレコードを書きます。初回 open は `"wb"` なので既存の同名ファイルは切り詰められます。1 行は `D` 個の値で、`D` は `hc * n_embd`、位置順です。既定の bf16 は float 値を round-to-nearest-even で 16 bit 化し、fp32 モードでは float 4 byte のまま保存します。ディレクトリ作成処理はありません（`src/prefill/prefill.cpp:2825-2850,2852-2887,3689-3694`; `docs/KVA.md:169-178`）。

冷たい読み込み（`pos0 == 0` かつ hand-in なし）の開始時に capture file を閉じ、次の capture で同じ `L*.bin` を上書きする状態に戻します。層ごとに次の期待位置を管理し、位置が連続しない場合は `kva capture: layer ... expects position ..., got ... (a capture needs one cold, in-order read)` をエラーにします（`src/prefill/prefill.cpp:2844-2850,2967-2972,2852-2860`）。

観測できる結果と失敗:

- prefill 完了時、stderr に `strata prefill: KVA off (capture): ...` と `, capturing the late layers' inputs` を含む診断行が出ます。`STRATA_KVA` を別途有効にしても capture 分岐が優先し、近似位置数は 0 のままです（`src/prefill/prefill.cpp:5820-5831`; `include/strata/prefill/kva.hpp:112-115`）。
- 層番号範囲外、期待位置との不一致、device residual の copy/sync 失敗、`fopen("wb")` 失敗では `write()` が false になり、`run_impl()` は `err` を設定して false を返します（`src/prefill/prefill.cpp:2852-2871,3691`）。呼び出し元へ伝わった後の CLI/サーバー表示は呼び出し経路に依存します。
- `fwrite()` と `fflush()` の戻り値は検査されていません。したがってディスク書き込みの完全性や容量不足時の明示エラーを、このコードからは保証できません（`src/prefill/prefill.cpp:2872-2886`）。

## 根拠

- 環境値の直接読み取りと値の保存: `include/strata/prefill/kva.hpp:91-93,163-167`。
- process cache と capture が近似を拒否する規則: `include/strata/prefill/kva.hpp:108-115,191-195`。
- capture 初期化・対象層条件・write 呼び出し: `src/prefill/prefill.cpp:2967-2974,3621-3629,3689-3694`。
- ファイル名、順序検査、copy/open/write と失敗文字列: `src/prefill/prefill.cpp:2825-2887`。
- KVA capture の正確な読み込みと出力形式の説明: `docs/KVA.md:119-120,169-178`。
