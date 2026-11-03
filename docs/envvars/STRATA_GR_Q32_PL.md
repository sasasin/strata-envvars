# `STRATA_GR_Q32_PL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP（gfx906 互換ビルドを除く）の fused hyper-connection 読み取りで、Q8 重み用の Q32 上向きカーネルに先読み版を選びます。先読み版は次の重みグループを現在のグループの計算前にロードし、正規化・部分和フェーズの前にも最初のグループをロードします。カーネル内のコメントは、各行の演算を変えず出力は bitwise 同一としています。CUDA と gfx906 互換ビルドでは、この変数を使う分岐がコンパイルされません。

## 値と判定

`std::getenv()` で取得し、`std::atoi(v) != 0` を真として判定します。文字列全体の検証はなく、`atoi` が先頭から読める整数部分を使います。

| 値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | `atoi("") == 0` となり無効 |
| 数値変換結果が 0 | 無効（例: `0`, `false`, 数字で始まらない文字列） |
| 数値変換結果が非 0 | 有効（例: `1`, `-1`, `2`, `1tail`, ` 1`） |

値の範囲制限や無効値時の fallback はありません。無効なら通常の Q32 上向きカーネルを使います。有効でも、別の条件を満たさなければ先読み版は選ばれません。

## 有効になる条件

次の条件を満たすときに限り、値が有効なら先読みテンプレート版 `gr_up_q8_q32_kernel<..., ..., true>` を選びます。

- HIP の非 gfx906 ビルドである。`STRATA_GR_FAST_BUILD` は通常の HIP で 0、CUDA と gfx906 互換では 1 になり、この選択部は `#if !STRATA_GR_FAST_BUILD` 内にあります。
- fused GR の multi-read が Q8 down/up 重みを持ち、`launch_q8()` に到達する。
- `qfuse_hc_local()` が真で、かつ `m.a[0].q8_mixed != nullptr`。`qfuse_hc_local()` は `STRATA_QFUSE_HC_LOCAL` 未設定時に真、設定時は `atoi(...) != 0` です。上位の `fused_gr_read_multi_slice()` はこの条件等から Q8 出力を使うか判定します。

`STRATA_GR_Q32_G` は同じ分岐内で `G` を選びます。未設定時は 1、変換結果が 2 / 4 / 8 のときはその値、それ以外は 1 です。先読み版では 2 / 4 / 8 の設定も 1 に fallback し、`STRATA_GR_Q32_PL` は先読みフラグだけを切り替えます。無効時の通常版では、`G` が 2 / 4 / 8 のいずれかならその値を使います。

## 実行時の詳細

値の判定は `launch_q8_t<T>()` 内の関数ローカル `static const bool` です。`m.a[0].q8_mixed != nullptr && qfuse_hc_local()` が真となってこの箇所へ到達したとき、各 `T` のテンプレート特殊化ごとに初回だけ読みます。その後の環境変更は、既に判定済みの特殊化には反映されません。CLI 引数や設定ファイルによる優先順位変更はこの分岐にはありません。

先読み版は各 warp の重み、残差・正規化値などを次グループ分まで交互バッファへロードしてから計算し、Q8_1 出力グループをカーネル内で生成します。`PL=false` の通常版は先読みを行いません。環境変数専用のログや警告はありません。カーネル起動エラーがあれば呼び出し元が `fused_gr_read_multi q8: <CUDA/HIP runtime error>` を stderr に出して `exit(1)` します。

## 根拠

- `src/kernels/cuda/fused_gr.cu:38-43` — CUDA / gfx906 と通常 HIP の `STRATA_GR_FAST_BUILD` の定義。
- `src/kernels/cuda/fused_gr.cu:1536-1540` — `STRATA_QFUSE_HC_LOCAL` の未設定時既定値と判定方法。
- `src/kernels/cuda/fused_gr.cu:2182-2201,2229-2263` — Q32 Q8 カーネル、`PL` 版のグループ先読み。
- `src/kernels/cuda/fused_gr.cu:2824-2845` — Q8 出力条件、`launch_q8()` 呼び出しと起動失敗時のログ・終了。
- `src/kernels/cuda/fused_gr.cu:2582-2606` — `STRATA_GR_Q32_G` と `STRATA_GR_Q32_PL` の読み取り、カーネル選択、および通常版への fallback。
