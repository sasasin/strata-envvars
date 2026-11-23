# `HY4_RDNA2_1TERM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`HY4_RDNA2_1TERM` は、`HY4_RDNA2_BENCH_MODES` が定義された HIP ビルドで、RDNA2 用 GEMM の活性値量子化を通常の 2 項から 1 項に切り替えるベンチマーク用スイッチである。値が有効な場合、`linear_h_rdna2` は `dispatch_rdna2_gemm<false>` を呼ぶ。通常経路は `<true>` である（`engine/src/hy4flash/run/sk_rdna2.hip.h:390-402`）。

1 項経路では各 64 要素の活性値部分群について最大絶対値から `q_hi` と `d_hi` を作り、残差の量子化と低位項の積和をコンパイル時に省く。2 項経路では残差から `q_lo` と `d_lo` を作り、その積和も加える（`engine/src/hy4flash/run/sk_rdna2.hip.h:118-172, 275-302`）。これはこの GEMM の計算経路を変えるもので、Strata のコードから生成 token や最終品質の変化は断定できない。

## 値と判定

関数内 static の初回評価時に `getenv` で読み、`atoi(e) != 0` を有効条件とする。環境変数が未設定なら無効。空文字や整数として先頭から変換できない文字列は `atoi` が 0 を返すため無効となる。`atoi` は文字列全体の厳密な検証ではないため、先頭の空白と符号に続く10進数字を変換し、最初の非数字以降は判定に使わない。変換結果が 0 以外なら有効で、負数も有効となる（`engine/src/hy4flash/run/sk_rdna2.hip.h:363-370`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| `HY4_RDNA2_BENCH_MODES` 定義下で読み取りに到達 | `m=0`（2 項経路） | `1`, `-1`, ` 2tail`（変換結果が非ゼロ） | 空文字、`0`, `0anything`, `true`, `  `（変換結果が 0） |
| マクロ未定義 | 読み取り自体がコンパイル対象外 | 該当なし | 該当なし |

`atoi` の結果が `int` に収まらない場合の挙動はこのコードで検証・制限されていないため、範囲外入力については保証しない。CLI 引数や設定ファイルとの優先順位はなく、この名前の参照は当該 `getenv` だけである。

## 有効になる条件

- `HY4_RDNA2_BENCH_MODES` がビルド時に定義されていること。checkout 内ではこのマクロは `#ifdef` で使用されているが、定義箇所や CMake の定義設定は見つからなかった。そのため、この checkout の標準ビルドで当該分岐が有効かはソースから確認できない（`engine/src/hy4flash/run/sk_rdna2.hip.h:395-400`）。
- HIP の非 CUDA 経路で `linear_h_rdna2` に到達すること。RDNA2 の `HY4_RDNA2` 判定は gfx1030/1031/1032/1034/1035/1036 のコンパイル時 architecture macro で有効になる。非 RDNA2 側にも runtime の `gfx10` 判定経路がある（`engine/src/hy4flash/run/hy4_gpu.h:335-345, 399-410`）。
- `linear_h` からの通常呼び出しでは `M > 16` の RDNA2 経路に到達すること。`M <= 16` は先に GEMV 側へ進む。`HY4_MMA=0` の分岐では、より大きい `M` の fallback が `linear_h_rdna2` を呼ぶ（`engine/src/hy4flash/run/skhy4.hip.h:47-83`）。
- `linear_h_rdna2` において `fmt` が `FMT_Q8ROW` でなく、`K` が 256 の倍数であること。条件を満たさない場合は環境変数を調べず `linear_h_ref` に戻る（`engine/src/hy4flash/run/sk_rdna2.hip.h:390-394`）。
- さらに、実際に RDNA2 GEMM を使うには形式が `FMT_S1_25`, `FMT_S1_5`, `FMT_S2`〜`FMT_S6`, `FMT_S8` のいずれかであること。それ以外の形式は 1 項設定が有効でも `dispatch_rdna2_gemm` の default から `linear_h_ref` に進む（`engine/src/hy4flash/run/sk_rdna2.hip.h:372-384`）。

## 実行時の詳細

`rdna2_use_1term()` の関数内 `static int m` が最初の呼び出しでだけ環境を読み、結果をプロセス内でキャッシュする。したがって、その呼び出し後にプロセス環境を変更してもこの判定には反映されない。環境値を子プロセスへ渡す処理はこの名前の参照範囲にはない（`engine/src/hy4flash/run/sk_rdna2.hip.h:363-370`）。

判定が有効なら、対応する S 形式と形状で `TWO_TERM=false` の HIP kernel を起動する。`quant_x_sub_i8` は高位項のみを書き込み、`rdna2_sdot4_loop` は高位項との積和だけを加算する。無効、またはベンチマーク macro 未定義なら `TWO_TERM=true` の kernel を使う（`engine/src/hy4flash/run/sk_rdna2.hip.h:118-172, 275-302, 390-402`）。この変数専用のエラー、警告、ログ出力はない。

## ログと測定値

この変数についてのログ出力は実装にない。`docs/DETAILS.md` および RDNA2 の説明がある `docs/AMD_HIP.md` にも `HY4_RDNA2_1TERM` の記載や、この切り替えに対応する測定値は見つからなかった。従って速度・精度の測定値は記載しない。

## 根拠

- `engine/src/hy4flash/run/sk_rdna2.hip.h:118-172, 275-302, 363-402` — 値の読み取り、static cache、1 項/2 項の量子化・積和と dispatch。
- `engine/src/hy4flash/run/skhy4.hip.h:47-83` — RDNA2 linear dispatcher への呼び出し条件。
- `engine/src/hy4flash/run/hy4_gpu.h:335-345, 399-410` — RDNA2 architecture 判定。
- `docs/DETAILS.md`, `docs/AMD_HIP.md:502-519` — 関連説明との照合。対象変数の説明・測定値はなし。
