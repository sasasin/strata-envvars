# `STRATA_GDN_REC_WARP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

実験的 CUDA build の Volta (compute capability 7.0) 向け GDN prompt recurrence で、既定の pipelined kernel の代わりに warp-reduction kernel または chain-split kernel を選ぶ opt-in 変数です。`2` は `gdn_rec_cols_pipe_fast_kernel`、`1` 以外の非ゼロ値は `gdn_rec_cols_warp_kernel` を選びます。後者はコードコメントで pipelined kernel と bit-exact、前者は和の順序が変わり bit-exact ではない FP32-level の差と説明されています。いずれも recurrence の出力 `y` と状態を計算し、通常の出力付き呼び出しでは続けて `gdn_out_norm_kernel` が `y16` を書きます。通常の Strata 起動で使う CLI 引数による上書きは見つかりませんでした。

この dispatch 部分は `engine/src/prefill/kernels.cu` の `gdn_recurrence_impl` にあり、通常の GDN prompt 経路から `gdn_recurrence` 経由で呼ばれます（`engine/src/prefill/kernels.cu:3145-3184, 3286-3294`; 呼び出し元 `engine/src/prefill/prefill.cpp:5203-5210, 9339-9343`）。

## 値と判定

実装は `std::getenv` の結果が null または空文字なら `0`、それ以外は `std::atoi` で整数化します。文字列全体の妥当性確認や値域チェックはありません。従って先頭に空白や符号がある数値は `atoi` の変換に従い、数値の後ろの文字も検証されません。`2tail` は `2`、`1x` は `1`、`true` や `x1` は `0` になり、`0anything` も `0` です。大文字小文字の判定はありません。

| 条件（build / 実行経路） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_EXPERIMENTAL_SM60` を有効にした CUDA build、かつ下記の Volta dispatch 条件を満たす | `warp_env=0`: 既定の pipelined recurrence | `atoi` 結果 `2`: chain-split kernel。その他の非ゼロ整数（例 `1`, `-1`, `3`）: warp-reduction kernel | `atoi` 結果 `0`（例 `0`, 空文字, `true`, `0tail`）: 既定の pipelined recurrence |
| 上記以外の build / GPU / recurrence 条件 | 同じ既定経路 | dispatch されず無視 | dispatch されず無視 |

未設定時と空文字は同じく `0` です。`atoi` の返り値が `2` かどうかだけを特別扱いし、それ以外の非ゼロ整数をまとめて `1` 相当の kernel に送ります（`engine/src/prefill/kernels.cu:3161-3163, 3173-3182`）。

## 有効になる条件

- `engine/src/prefill/kernels.cu` の `STRATA_EXPERIMENTAL_SM60` compile guard 内にある dispatch が build に含まれること。この macro は CUDA build 設定で既定 OFF、ON の場合に compile definition として追加されます（`engine/cmake/backends/cuda.cmake:28, 76-80`）。HIP は対象外です。
- 実行中の GPU が compute capability 7.0 であること。`gdn_chunk_available()` はこの build 以外や HIP では false、実験的 CUDA build では現在デバイスの CC が 70 のとき true を返します（`engine/src/prefill/gdn_chunk.cu:525-530`）。sm_60、sm_86、sm_120 等では warp kernel の分岐は選ばれません（`docs/GDN_CONTRACT.md:71-72` はこの条件を記載）。
- `STRATA_GDN_REC_HEADS` が設定されていないこと。値の内容ではなく `getenv(...) != nullptr` を関数内 static に保存しており、空文字でも設定されていれば serial 経路となり warp dispatch を抑止します（`engine/src/prefill/kernels.cu:3087, 3163`）。
- `STRATA_GDN_CHUNK` により chunked recurrence が選ばれていないこと。実験的経路ではこの変数を各呼び出しで `atoi` し、0 以外の非負整数なら `chunked` になります。その場合 `warp_rec` は false です（`engine/src/prefill/kernels.cu:3150-3164`）。chunked 側は `T >= 64` のとき先に実行され、短い残りは pipelined recurrence で処理されます（同 `3164-3172`）。
- recurrence の token 数 `T` が正であること。`T <= 0` では warp 分岐に入りません（`engine/src/prefill/kernels.cu:3163-3164`）。

GPU 条件の `volta` は `static const bool` なので、プロセスで最初に `gdn_recurrence_impl` がこの箇所に到達したときのデバイス判定が保持されます。一方、対象変数自体は static に保存されず、warp dispatch に到達するたびに読み直されます。複数 GPU を使う場合、最初の判定後に別 GPU へ切り替えた際の `volta` 再判定は行われません（`engine/src/prefill/kernels.cu:3152, 3161-3163`）。

## 実行時の詳細

通常の prefill 処理で GDN recurrence に到達すると、実験的 CUDA build では `STRATA_GDN_CHUNK` と `STRATA_GDN_REC_WARP` をその呼び出しで読みます。serial / chunked / `T > 0` / `volta` を組み合わせて `warp_rec` を決め、`warp_env == 2` のときは 4 accumulator の chain-split kernel、それ以外の非ゼロ値では warp-local reduction kernel を起動します。どちらも state を更新し、recurrence 出力 `y` を作ります。`with_out` が真なら後続の norm kernel で `y16` も生成します。warp dispatch が選ばれない場合は後続の標準 recurrence dispatch に進み、`STRATA_GDN_PIPELINE` 等の別条件が通常 kernel を選びます（`engine/src/prefill/kernels.cu:3161-3188`）。

この変数について CLI 引数、設定ファイル、子プロセスへの転送、起動時の engine 側設定は確認できませんでした。実行中に環境値を変更した場合は次の recurrence 呼び出しから値の読み直しが反映されます。ただし build macro と一度だけ評価される `volta` / `serial` 条件は変わりません。

失敗時、kernel launch 後の CUDA エラーは `check("gdn_recurrence")` が `cudaGetLastError()` で検出し、`strata::core::exit_device_error` に渡します。対象変数固有の警告や fallback ログはありません（`engine/src/prefill/kernels.cu:110-116, 3273-3279`）。

## ログと測定値

本番 recurrence dispatch は、この値の選択や選択 kernel をログ出力しません。CUDA launch error があれば上記の共通エラー経路に進みます。開発用 `gdn_harness` は設定されていれば環境値を `env STRATA_GDN_REC_WARP=<値>` の形式で表示しますが、これは harness の診断出力です（`engine/src/prefill/gdn_harness.cu:450-452`）。

`docs/NVIDIA_V100.md` は `STRATA_GDN_REC_WARP=2` について recurrence の `+6-9%` と記載し、同資料の opt-in 表では FP32 summation order を変えるとしています（`docs/NVIDIA_V100.md:79, 128-138`）。この測定表には当該行のモデル、量子化、prompt 長、試行回数等の条件が示されていないため、この値は資料上の報告としてのみ扱い、一般的な速度向上とは断定できません。

## 根拠

- 値読み取り、分岐、起動、norm: `engine/src/prefill/kernels.cu:3145-3184`
- recurrence の通常呼び出し: `engine/src/prefill/prefill.cpp:5203-5210, 9339-9343`
- build macro: `engine/cmake/backends/cuda.cmake:28, 76-80`
- CC 判定: `engine/src/prefill/gdn_chunk.cu:498-530`
- serial gate と一度だけの評価: `engine/src/prefill/kernels.cu:3083-3088, 3152-3163`
- kernel の演算差: `engine/src/prefill/kernels.cu:553-597, 759-820`
- 共通 CUDA error 経路: `engine/src/prefill/kernels.cu:110-116, 3273-3279`
- harness の環境値表示: `engine/src/prefill/gdn_harness.cu:450-452`
- 設計上の適用条件と測定表: `docs/GDN_CONTRACT.md:71-72`, `docs/NVIDIA_V100.md:79, 128-138`
