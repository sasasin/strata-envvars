# `STRATA_GR_Q8_PFS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Q8_0 hyper-connection の multi-token fused read において、down 側 fast kernel の staging load 配置を切り替えます。有効で、かつ `STRATA_TSUM` も有効な場合、`gr_down_q8_fast_kernel<T, 4, true>` を起動します。この特殊化は全 token の `R` / normalization weight / 適用時の bias をまとめて読み、staging を行います。無効時は同じ fast kernel の PFS なし特殊化、または従来 kernel を選びます（`src/kernels/cuda/fused_gr.cu:2582-2590,2331-2332,2363-2413`）。

## 値と判定

カーネルの最初の呼び出し時に `std::getenv()` の値を `std::atoi()` で整数変換し、0 以外なら有効と判定します。文字列全体の妥当性検証はありません。`atoi` の通常の規則により、先頭空白や符号の後の整数部分を読み、整数以降の文字は無視します。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効。ただし AMD gfx12 向け起動時既定値が適用された場合は `1` が設定され、有効になる |
| 空文字、整数に変換できない文字列 | `atoi` が 0 を返すため無効 |
| `0` や `0tail` | 変換結果 0 のため無効 |
| `1`、負でない非ゼロ整数、負の非ゼロ整数 | 変換結果が 0 以外のため有効。例: `1tail` は先頭の整数 `1` で有効、`-1` も有効 |

数値変換の境界外入力に対する `atoi` の結果は実装上保証されないため、利用可能な値として扱いません。明示設定値は architecture default より優先されます。既定値適用時は設定有無だけを見るため、空文字や `0` も利用者の値として保持されます（`src/kernels/cuda/fused_gr.cu:2586`, `src/core/arch_defaults.cpp:226-229`）。

## 有効になる条件

- 実際に `fused_gr_read_multi()` が Q8_0 の hyper-connection weights (`q8_down` と `q8_up`) を受け取り、`launch_q8()` に進む必要があります。Verifier は attention などの hyper-connection weights から Q8 pointers を設定して multi-token read に渡します。Q8 weights がない読み取りではこの選択箇所を通りません（`src/core/verify.cpp:1587-1609`; `src/kernels/cuda/fused_gr.cu:2812-2823,2838-2845`）。
- `STRATA_TSUM` の先頭文字が `1` であることが追加条件です。`STRATA_GR_Q8_PFS` が有効でも `STRATA_TSUM` が無効なら、PFS 特殊化は選ばれません。`STRATA_TSUM` は同じ関数で別途 static cache されます（`src/kernels/cuda/fused_gr.cu:2584-2589`）。
- Strata の HIP 起動時 architecture defaults は、AMD gfx1200/gfx1201（gfx12）で `STRATA_TSUM=1` と `STRATA_GR_Q8_PFS=1` を既定設定します。ただし `STRATA_GFX12_DEFAULTS` が `0` で始まる場合は gfx12 defaults 全体が空になり、`STRATA_DEFAULTS=026` の場合も prompt 側のみの表で早期 return するため、この既定値は追加されません。利用者が対象変数を何らかの値で設定済みなら上書きしません（`src/core/arch_defaults.cpp:27-61,185-190,221-229`; 呼び出しは `src/program/generate.cpp:3702-3719`）。
- それ以外の backend / architecture にはこの起動時既定値はありません。ただし `STRATA_TSUM=1` と対象変数の有効値を明示すれば、コンパイルされた Q8 fast-kernel 経路で PFS 分岐の条件を満たします。

## 実行時の詳細

`launch_q8_t<T>()` 内の `pfs` は関数ローカルの `static const bool` です。したがって値はプロセス内の最初の同関数呼び出し時に一度だけ読み取られ、その後の環境変更は反映されません。architecture default の注入は生成処理の早い段階で行われ、コメント上も engine が各 switch を初めて読む前に実施されます。

PFS 特殊化は down kernel 内で全 token の staging load をまとめて発行し、計算値と演算順序は通常経路と同じとコードコメントに記されています。その後の up 側 kernel 選択は `STRATA_TSUM` のみで決まり、この変数では変更しません（`src/kernels/cuda/fused_gr.cu:2363-2395,2582-2606`）。コード上、この変数自体の警告や状態ログはありません。Q8 fused read の kernel launch が失敗した場合は `fused_gr_read_multi q8: <CUDA error text>` を stderr に出して `exit(1)` しますが、これは一般の launch error 処理であり PFS 固有の失敗報告ではありません（`src/kernels/cuda/fused_gr.cu:2838-2844`）。

## 根拠

- 対象名の実読み取りと kernel 分岐: `src/kernels/cuda/fused_gr.cu:2582-2589`。
- PFS 特殊化の staging 処理と演算: `src/kernels/cuda/fused_gr.cu:2331-2337,2363-2413`。
- Q8 weights による呼び出し条件と失敗経路: `src/kernels/cuda/fused_gr.cu:2812-2845`。
- gfx12 既定値と適用条件: `src/core/arch_defaults.cpp:27-61,185-190,221-229`; startup 呼び出し `src/program/generate.cpp:3702-3719`。
