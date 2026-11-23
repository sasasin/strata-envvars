# `STRATA_HIP_SWIGLU_FUSED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

gfx906 向け grouped expert decode の SwiGLU と q8_1 量子化を、別々の二段階カーネルから一つのカーネルへ切り替える opt-in です。gate/up の計算方法は変えず、SwiGLU の結果を q8_1 に格納する処理を同じカーネル内で行います。ソースコメントは fused カーネルが別々の処理と bitwise 同一としていますが、この調査では実行・再測定していません。CUDA 実装と SYCL ポートの `native_expert_grouped` が読み取ります（`engine/src/kernels/cuda/iq_kernels.cu:7319-7336`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7880-7945`）。

## 値と判定

両実装とも `env_on` を使い、値の先頭文字だけを確認します。未設定、空文字、先頭が `0` の値は false、それ以外の非空値は true です。文字列全体の parse、数値変換、空白除去、大文字小文字変換はありません（CUDA: `engine/src/kernels/cuda/iq_kernels.cu:3689-3692`、SYCL: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3930`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `STRATA_HIP_GFX906` 定義あり | 無効（既定は別カーネル） | `1`, `true`, `false`, ` 0`, `1anything` | 空文字, `0`, `0anything`, `0.1` |
| `STRATA_HIP_GFX906` 定義なし | 読み取り箇所なし。この変数による切替なし | 該当なし | 該当なし |

## 有効になる条件

- `STRATA_HIP_GFX906` を定義してビルドしたエンジンであること。この CMake 選択肢は gfx906 を HIP で CUDA 互換層経由でビルドし、`STRATA_HIP_GFX906=1` をコンパイル定義します（`engine/CMakeLists.txt:97-103,233-240`、`engine/cmake/backends/hip.cmake:7-23`）。通常の CUDA、wave32 HIP（RDNA）ビルドではこの環境変数を読む分岐がコンパイルされません。
- `native_expert_grouped` が SwiGLU 段階まで到達すること。空の group/entry 数などで関数が先に戻る場合はこの分岐を通りません（`engine/src/kernels/cuda/iq_kernels.cu:7085-7089,7316-7323`）。
- 診断用 `g_exp_phase == 3`（gate/up のみ）の経路は SwiGLU ブロックより前に return するため、この変数を読みません（`engine/src/kernels/cuda/iq_kernels.cu:7316-7318`）。ほかにも関数内の早期 return が選ばれる呼び出しでは、SwiGLU ブロックに到達しません。
- grouped-v1 が無効であること。実効条件は `sw_v1 = v1 || !sw_fused` で、`v1` が true ならこの変数を有効にしても別カーネルのままです。通常の初期値は `STRATA_GROUPED_V1` を `env_on` で読んだ `g_grouped_v1` ですが、カーネル API `native_grouped_set_v1` からも変更できます（`engine/src/kernels/cuda/iq_kernels.cu:6831-6833,6891,7184-7185,7322-7325`、SYCL: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7761-7765,7791`）。
- `L.had_block == 0` であること。Hadamard-folded down weights では、変換後の `h` が必要なため、変数が有効でも別カーネル経路を使います（`engine/src/kernels/cuda/iq_kernels.cu:7327-7335`、SYCL: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7893-7944`）。

## 実行時の詳細

環境値は `native_expert_grouped` 内の関数ローカル `static const bool` に初回到達時に読み込まれ、同じプロセス内で保持されます。初回読み取り後に環境を書き換えても再評価されません（CUDA: `engine/src/kernels/cuda/iq_kernels.cu:7322`、SYCL: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7888`）。CLI 引数や設定ファイルからこの変数を別途解釈する処理は見つかりません。

切替が無効、または上記の条件により fused を使わないときは、`swiglu_entries_kernel` で float の SwiGLU 結果 `h` を作り、必要なら `hadamard_rows` を実行し、続いて `quantize_q8_1_kernel` を起動します。有効で条件を満たすときは `swiglu_q8_1_entries_kernel` が SwiGLU 値を直接 q8_1 ブロックへ格納します。どちらもこの後の down 計算へ `hq` を渡します（CUDA: `engine/src/kernels/cuda/iq_kernels.cu:2382-2388,3090-3116,7327-7337`、SYCL: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7893-7946`）。

この変数専用の有効・無効ログはありません。CUDA 側は後続の `check("native_expert_grouped/swiglu")` が直前の GPU エラーを検査し、エラー時には stderr に `<what>: <CUDA error text>` を出して終了コード 1 で終了します（`engine/src/kernels/cuda/iq_kernels.cu:47-50,7337`）。SYCL 側にも同名の `check` 呼び出しはありますが、その関数は生成コード上のダミー実装でエラーコードを検査していません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:72-84,7946`）。

## ログと測定値

`docs/DETAILS.md` にこの変数の記載や、この切替に対応する測定値は見つかりませんでした。`docs/AMD_HIP.md` の speed switches 表にも本変数は載っていません（同表: `docs/AMD_HIP.md:296-315`）。性能向上や実機での出力同一性はここでは断定しません。ソースコメントは別々の SwiGLU/q8_1 と fused カーネルの bitwise 同一性を述べています（`engine/src/kernels/cuda/iq_kernels.cu:3090-3096`）。

## 根拠

- 判定 helper と gfx906 専用分岐: `engine/src/kernels/cuda/iq_kernels.cu:3689-3692,7319-7337`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3930,7880-7946`
- ビルド条件: `engine/CMakeLists.txt:97-103,233-240`、`engine/cmake/backends/hip.cmake:7-23`
- grouped-v1 の初期化と更新: `engine/src/kernels/cuda/iq_kernels.cu:6831-6833,6891,7184-7185`
- エラー確認: `engine/src/kernels/cuda/iq_kernels.cu:47-50,7337`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:72-84,7946`
