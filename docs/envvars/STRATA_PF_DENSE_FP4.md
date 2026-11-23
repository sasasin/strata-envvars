# `STRATA_PF_DENSE_FP4`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の NVFP4 dense prefill GEMM について、Blackwell の `mxf4nvf4` Tensor Core 経路を使うかを制御する。未設定時は有効扱いだが、実際に使われるにはビルド・GPU・形状の条件をすべて満たす必要がある。`STRATA_PF_DENSE_FP4=0` はこの経路を無効にする。環境変数は `dense_fp4_tc::enabled()` で評価され、`Gemm::native()` が NVFP4 (`ggml_type == 40`) の dense prefill を試す（`engine/src/prefill/dense_fp4_tc.cu:404-411`, `engine/src/prefill/gemm.cu:1539-1543`）。

この変数はモデル選択、NVFP4 のデコード経路、HIP の MoE 経路を切り替えない。条件に合わない場合や専用 GEMM が実行できない場合、`Gemm::native()` は後続の FP16 逆量子化 GEMM 経路を使う（`engine/src/prefill/gemm.cu:1646-1677`）。

## 値と判定

`std::getenv` の結果を関数内 `static const int` に一度だけ保存する。未設定 (`nullptr`) または空文字 (`v[0] == '\0'`) は有効扱い。その他は `std::atoi(v) != 0` で判定するため、文字列全体の妥当性検査はなく、先頭の空白・符号と数値接頭辞に従う。たとえば `1`, `2`, `-1`, ` 1x` は有効、`0`, `0anything`, `true`, `false`, `x1` は無効になる。`atoi` で数値に変換できない文字列は 0 として無効になる。数値範囲外の文字列に対する `atoi` の結果は文書化された設定値として扱えない（`engine/src/prefill/dense_fp4_tc.cu:404-410`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA 実装がビルドされている場合 | ON | `1`, `-1`, ` 1x` | `0`, `0anything`, `true`, 空白だけ |
| HIP または専用 CUDA カーネルなしのビルド | 効果なし（スタブが常に false） | なし | なし |

## 有効になる条件

- CUDA ビルドで、CUDA コンパイラが 13.0 以上かつビルド対象アーキテクチャに `120` または `121` が含まれ、専用 `.cu` カーネルがリンクされていること。該当しない場合は `dense_fp4_tc_absent.cpp` のスタブが使われる。HIP ビルドもスタブを組み込む（`engine/cmake/backends/cuda.cmake:101-131`, `engine/cmake/backends/hip.cmake:42`, `engine/src/prefill/dense_fp4_tc_absent.cpp:7-14`）。
- 実行中の CUDA デバイスの compute capability が sm_120 または sm_121 で、カーネルの occupancy 確認が成功して occupancy が 0 より大きいこと。デバイス番号が 0–31 の範囲外、デバイス属性取得失敗、別世代 GPU では利用不可（`engine/src/prefill/dense_fp4_tc.cu:364-402`）。
- 呼び出しが HIP でないビルドの `Gemm::native()` で、量子化 type が 40、入力 stride が未指定または `K` と一致すること（`engine/src/prefill/gemm.cu:1539-1543`）。
- GEMM の形状が `T >= 32`, `N >= 64`, `K >= 64` かつ `K` が 64 の倍数であること。満たさない場合は専用関数が `false` を返す（`engine/src/prefill/dense_fp4_tc.cu:413-418`）。
- 活性値 scratch の `cudaMalloc` が成功し、カーネル起動時の CUDA エラー確認が成功すること。割り当て失敗や起動エラーの場合は専用経路を使ったと報告せず、呼び出し元で通常経路に進む（`engine/src/prefill/dense_fp4_tc.cu:427-457`, `engine/src/prefill/gemm.cu:1540-1543`）。

OS、CLI 引数、サーバーモード、別の環境変数による追加条件は、この変数の実装・呼び出し経路には見つからない。

## 実行時の詳細

`enabled()` の初回呼び出しで環境値を process-wide に一度読み、以後の環境変更は反映されない。値が有効でも、そのたびに現在の CUDA デバイスを確認する。デバイスごとのアーキテクチャ・occupancy 判定は `g_checked[dev]` に保存され、再確認しない（`engine/src/prefill/dense_fp4_tc.cu:360-410`）。

対象の GEMM では、各デバイスに保持する活性値バッファを必要サイズに応じて確保し、FP16 活性を NVFP4 形式へ量子化してから dense Tensor Core カーネルを起動する。バッファはデバイスごとに保持され、容量不足時に解放・再確保される。出力は `Y = beta * Y + X @ W^T` の形式で更新する（`engine/src/prefill/dense_fp4_tc.cu:413-456`）。

専用関数が `false` を返すと呼び出し元はその場で終了せず、scratch 制約に応じた行スライス処理または通常の FP16 逆量子化後の `f16()` に進む。通常経路の scratch 不足で行数が 0 の場合は `prefill gemm: scratch too small for K=%lld` を stderr に出して `exit(1)` する（`engine/src/prefill/gemm.cu:1646-1677`）。

## ログと測定値

専用カーネル起動が成功したデバイスでは、`DevState::logged` がまだ false の場合に限り stderr に次を出す。

```text
strata prefill: Blackwell mxf4nvf4 Tensor Core dense NVFP4 GEMM active (STRATA_PF_DENSE_FP4=0 disables)
```

これはデバイスごとに一度で、環境値による無効化、未対応 GPU・形状、割り当て失敗、起動エラーの場合にはこのログは出ない（`engine/src/prefill/dense_fp4_tc.cu:457-464`）。この環境変数について `docs/DETAILS.md` に紐づく測定値は確認できなかった。

## 根拠

- `engine/src/prefill/dense_fp4_tc.cu:393-410` — ビルド済み・利用可能判定、環境値の変換と cache。
- `engine/src/prefill/dense_fp4_tc.cu:413-464` — 形状条件、scratch 確保、カーネル実行、ログ。
- `engine/src/prefill/gemm.cu:1539-1543,1646-1677` — 呼び出し条件と FP16 逆量子化経路。
- `engine/cmake/backends/cuda.cmake:101-131` — 専用 CUDA カーネルを含むビルド条件。
- `engine/cmake/backends/hip.cmake:42`, `engine/src/prefill/dense_fp4_tc_absent.cpp:7-14` — HIP および未ビルド時のスタブ。
