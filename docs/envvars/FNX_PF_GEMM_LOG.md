# `FNX_PF_GEMM_LOG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

split engine の prompt prefill が呼び出す `pf_gemm()` について、行列形状を診断目的で stderr に出します。計算方法の選択や GEMM の結果は変更しません。読み取り箇所は `src/split/src/prefill.cu` の1箇所で、候補一覧にある名前が実際に Strata の環境から読まれています。

## 値と判定

`std::getenv("FNX_PF_GEMM_LOG")` の戻り値が null でないかだけを判定します。

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | この診断ログを出さない |
| 設定あり（空文字を含む） | `pf_gemm` の各形状について、プロセス内で初めての呼び出し時にログを出す |

値の文字列、数値、大文字小文字は調べません。したがって `0`、`false`、空文字も、設定されていれば有効です。CLI 引数や他の環境変数による上書き・優先順位はありません。

## 有効になる条件

このコードは `STRATA_BUILD_SPLIT` で追加される split engine の `prefill.cu` にあります。CMake 設定では split engine は Linux 上の CUDA または HIP 向けで、ビルド対象が作られない構成ではこの読み取り箇所は実行ファイルに入りません（`CMakeLists.txt:2946-2949`; `src/split/CMakeLists.txt:4,64-80,92-120`).

実行時には split engine の prompt prefill が `pf_gemm()` に到達した場合に限りログが出ます。通常の decode window はこの箇所を通りません。`pf_gemm()` は Q8 split-layout の dense 行列および hyper-connection read から呼ばれ、さらに prefill の shared expert 行列積からも呼ばれます（`src/split/src/prefill.cu:429-438,451-456,982-1036,1293-1297`）。

## 実行時の詳細

各 `pf_gemm()` 呼び出しで環境変数を再確認し、設定されている場合は `(rows, cols, C, ldo)` をキーにした `static std::set` に登録します。同じ4値の組み合わせは一つのプロセス内で一度だけ stderr に出力されます。別の形状はそれぞれ一度ずつ出ます。環境変数の判定自体は static cache されていませんが、既に記録した形状は環境値を後から変更しても再出力されません。

出力形式は `pf_gemm: rows %d cols %d C %d ldo %d\n` です。ログ判定は `p.f16acc` 分岐と cuBLAS 呼び出しより前に行われます。その後の f16 accumulate 経路と f32 accumulate 経路の選択、および cuBLAS 呼び出しは `p.f16acc` によるもので、この環境変数では変わりません。環境変数による警告、エラー、終了経路もありません。GEMM 実行時のエラー処理は既存の `ckb(...)` によります。

## 根拠

- `src/split/src/prefill.cu:410-427` — 唯一の環境読み取り、形状ごとの重複抑制、stderr 出力、およびログ後に行う GEMM の分岐。
- `src/split/src/prefill.cu:429-438,451-456,1293-1297` — `pf_gemm()` の呼び出し元。
- `src/split/src/prefill.cu:982-1036` — prompt prefill の入口と chunk 処理。
- `src/split/src/engine_common.cu:328-339`; `src/split/tools/fnx_run.cpp:155-162` — warm-up と実行ドライバーから prefill が呼ばれる例。
- `CMakeLists.txt:2946-2949`; `src/split/CMakeLists.txt:4,64-80,92-120` — split engine のビルド条件と CUDA/HIP ソース設定。
