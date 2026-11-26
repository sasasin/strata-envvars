# `STRATA_DENSE_F32`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の実験的 `STRATA_EXPERIMENTAL_SM60` ビルドで、条件に合う大きな FP16 dense prefill GEMM を、FP16 入力のまま行う `cublasGemmEx` から、FP16 operand を FP32 に変換して行う `cublasSgemm` に切り替える opt-in 変数です。Strata が環境変数を読むのは `engine/src/prefill/gemm.cu` の `dense_f32_on()` です。重み・活性値は FP16 のまま保持され、対象 GEMM の前に FP32 の scratch へ変換されます。通常の decode や条件に合わない GEMM を切り替える設定ではありません。`Gemm::f16` が prefill の gate/up・down projection 等から呼ばれます（`engine/src/prefill/prefill.cpp:7465-7480, 8903-8910`、切替本体は `engine/src/prefill/gemm.cu:1329-1356`）。

## 値と判定

環境変数は `std::getenv` で取得し、未設定かどうかを調べたうえで `std::atoi(v) != 0` とします。文字列全体の妥当性検査や `1` との等値比較はありません。`atoi` が先頭の空白後に整数として読める接頭辞を変換するため、`1abc` は有効、`0anything` は無効、`true` や空文字は 0 になります。負数を含む非ゼロ整数は有効です。数値への変換ができない文字列も 0 です。数値範囲の検証・clamp はありません（`engine/src/prefill/gemm.cu:995-1004`）。

| 条件（build / device） | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA、`STRATA_EXPERIMENTAL_SM60` 定義あり、実行 device が compute capability 6.x | off | `1`, `2`, `-1`, `1abc` | 空文字, `0`, `0anything`, `true`, `false`, `abc` |
| 上記 build だが device が 6.x 以外 | off | `atoi` が非ゼロでも切替経路では off | どの値でも切替なし |
| `STRATA_EXPERIMENTAL_SM60` なし、または HIP build | この読み取り・切替コードがコンパイルされない | 該当なし | 該当なし |

既定は off です。CLI 引数や設定ファイルによる上書きはこの実装にはありません。`gemm_set_dense_f32()` は parity 用の API で、通常の Strata 実行経路からの呼び出しは見つかりません。`gemm_f32_parity` は比較のため `0` / `1` を強制し、最後に `-1` で環境変数判定に戻します（`engine/src/prefill/gemm.cu:1020-1024`、`engine/src/prefill/gemm_f32_parity.cu:89-92, 108-126`）。

## 有効になる条件

- CMake の CUDA build で `STRATA_EXPERIMENTAL_SM60=ON` が指定されている必要があります。このオプションは Pascal / Volta 向けの実験的 build で、CUDA 12.x toolkit が必要とされています（`engine/cmake/backends/cuda.cmake:28, 47-57, 76-80`）。HIP は対象外です（`engine/src/prefill/gemm.cu:1020-1024, 1329-1329`）。
- `dense_f32_on()` が使う現在 device の compute capability が 6.0 以上 7.0 未満である必要があります。よって Volta 7.x では、この環境変数が非ゼロでも通常経路になります。compute capability の取得結果は device ごとに cache されます（`engine/src/prefill/gemm.cu:928-945, 1003-1005`）。
- `Gemm::f16` が呼ばれ、`beta == 0.0f` である必要があります（`engine/src/prefill/gemm.cu:1329-1332`）。
- GEMM の `(N, K)` が次のいずれかで、`T` が下限以上である必要があります（`engine/src/prefill/gemm.cu:1006-1016, 1331-1332`）。

  | N | K | 最小 T |
  |---:|---:|---:|
  | 10240 または 12288 | 2560 | 256 |
  | 6144 | 2560 | 512 |
  | 2560 | 6144 または 4096 | 4096 |

- shape が条件を満たしても、FP32 変換用 CUDA buffer の確保に失敗すれば FP16 `cublasGemmEx` に進みます（`engine/src/prefill/gemm.cu:960-967, 1332-1356`）。
- 他の環境変数による上書き条件はありません。`STRATA_DENSE_F32` の読み取り箇所はこの CUDA 実装だけです。

## 実行時の詳細

環境値は `dense_f32_on()` 内の関数ローカル `static const bool` で初回評価時に一度だけ読みます。通常実行では、最初に対象 shape の `Gemm::f16` が判定に達した時点が初回評価です。その後プロセス内で環境を変更しても反映されません。parity 用 setter は環境値より優先しますが、通常の production 呼び出し経路で setter は使われていません（`engine/src/prefill/gemm.cu:995-1005, 1020-1024`）。

切替経路では FP16 の重み全体と、最大 16M 要素単位の活性値 slice を FP32 scratch に変換し、slice ごとに `cublasSgemm` を呼びます。成功すれば通常の FP16 GEMM 呼び出しを返し、確保できなければ FP16 `cublasGemmEx` に fallback します。切替経路に入って最初に buffer 確保が成功したとき、stderr に次の文言を一度出します（`engine/src/prefill/gemm.cu:969, 1332-1356`）。

```text
prefill gemm: the dense projections' FP16 GEMMs run as cublasSgemm on FP32 copies (STRATA_DENSE_F32=1; gemm_f32_parity checks the bits against this cuBLAS)
```

このログが出るのは該当経路が実際に選ばれて buffer 確保も成功した場合だけです。切替した `cublasSgemm` が失敗すると `ck()` が stderr に `prefill gemm: cublasSgemm (FP16 operands, STRATA_DENSE_F32): cuBLAS status <番号>` を出し、終了コード 1 でプロセスを終了します（`engine/src/prefill/gemm.cu:160-165, 1349-1352`）。

## ログと測定値

`gemm.cu` のコメントは Tesla P40（sm_61）と cuBLAS 12.4.5.8 での測定として、指定した projection shape / chunk size では FP32 route と FP16 call の出力が bitwise 一致したと記しています。また、T が小さい一部 shape では cuBLAS が別 kernel family に切り替わり bit が異なるため、この変数の経路を適用しない、と説明しています。これは当該測定条件についてのソースコメントであり、別 GPU・別 cuBLAS build での一致保証ではありません（`engine/src/prefill/gemm.cu:972-986, 1006-1015`）。性能値はここでは一般化しません。

## 根拠

- 値の読み取り・cache・device 判定・shape 閾値: `engine/src/prefill/gemm.cu:995-1017`
- CUDA build 条件: `engine/cmake/backends/cuda.cmake:28-80`
- FP32 変換、切替、fallback、ログ、cuBLAS エラー: `engine/src/prefill/gemm.cu:960-967, 1329-1356, 160-165`
- 通常 prefill からの `Gemm::f16` 呼び出し例: `engine/src/prefill/prefill.cpp:7465-7480, 8903-8910`
- parity 用 setter: `engine/src/prefill/gemm.cu:1020-1024`、`engine/src/prefill/gemm_f32_parity.cu:89-127`
