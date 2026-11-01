# `STRATA_PF_W16_CACHE_MIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数は対象外。

## 役割

CUDA の GPU prefill で `Gemm::native()` が量子化された GGUF 重みを FP16 に dequantize した後、その device 上の FP16 重みを予算内で保持します。同じ重み・型・形状を再度処理すると dequantize を省いて FP16 GEMM を実行します。既定値は無効（0 MiB）です。ソースコメントは cached / uncached の FP16 値と積が bit 単位で同じとしています。

この環境変数を実行時に読む箇所は `src/prefill/gemm.cu` の一箇所です。候補一覧以外の参照は、ヘッダーと実装のコメント、および `tools/par/variants/stack_s1.txt` の実験プロファイルにあります。これらは追加の読み取り経路ではありません。

## 値と判定

`Gemm::native()` の初回呼び出し時に `std::getenv()` で取得し、`std::atoll()` の結果に `2^20` を掛けてバイト予算にします。値全体の妥当性確認や clamp はありません。

| 値 | 実装上の結果 |
|---|---|
| 未設定 | 0 MiB。キャッシュしない |
| 空文字 | `atoll("")` が 0 となり、キャッシュしない |
| 10 進数の整数 | その値 MiB を予算にする。先頭空白・符号は `atoll` の変換規則に従い、数値の後ろにある変換不能な文字列は検査されず、数値部分が使われる（例: `2tail` は 2 MiB） |
| 数字で始まらない文字列 | 変換結果 0 となり、キャッシュしない |
| 0 または負数 | 変換後の予算が正ではないため、キャッシュしない |

値の数値変換範囲を超える入力や MiB から byte への乗算 overflow に対する検査はありません。したがって、その場合の結果は有効な設定値として保証されません。

## 有効になる条件

- `src/prefill/gemm.cu` の HIP 用 `#ifndef STRATA_USE_HIP` 節にあるため、このキャッシュ処理は HIP build では実行されません。CUDA の `Gemm::native()` 経路が対象です。
- GPU prefill が量子化 GGUF の native projection を実行するときに `Gemm::native()` へ到達します。`native_proj()` は `native_data` がなければ `--native` を使うようエラーを返すため、native GGUF blocks を使わない経路では対象の処理に入りません。
- 環境値が正でも、`side_scratch_` が設定されているとキャッシュ分岐を通りません。CUDA で `STRATA_DEQUANT_SIDE` の先頭文字が `1` のとき、初期化時に別 scratch が確保できれば side dequant 経路が設定されます。別 scratch が取れない場合は警告を出して side dequant を使わないため、他の条件が合えばキャッシュ分岐に進めます。
- キャッシュはプロセス全体の共有 pool ではなく `Gemm` インスタンスごとの予算・entry vector です。各 entry は元の device pointer、GGML type、`N`、`K` で照合されます。CLI 引数による予算上書きや、別の予算用環境変数はこの読み取り箇所にはありません。

## 実行時の詳細

各 `Gemm` の `w16_budget_` は初期状態 `-1`（未読）です。そのインスタンスで最初にキャッシュ分岐へ来た `native()` 呼び出しが環境値を読み、以後は変数を読み直しません。したがって、その後の環境変更は同じインスタンスに反映されません。値が未設定または 0 以下なら、後続呼び出しもキャッシュを試しません。

各重みの必要量は `N * K * 2` bytes です。既存 entry があれば FP16 device pointer を使って `f16()` を実行します。entry がなく、使用量と必要量の合計が予算以下の場合に限り、新しい allocation を試します。さらに `cudaMemGetInfo()` が成功し、空き VRAM が必要量に 2 GiB を足した量より大きい場合に `cudaMalloc()` します。成功時は重み全体を `dequant_f16()` で cache allocation に変換して entry を追加し、同じ呼び出しの GEMM にもその pointer を使います。

entry がなく予算に収まらない場合は、その重みを cache に追加せず scratch への通常の dequantize と GEMM に進みます。空き VRAM 条件を満たさない、または allocation が失敗した場合は、現在の使用量を予算として残す（まだ entry がなければ 0 にする）ため、それ以後の新規追加を止めます。既存 entry の再利用はこの判定より先に行われます。cached allocation は `Gemm` の destructor で `cudaFree()` されます。

この環境変数について専用のログ、警告、終了経路はありません。allocation を得られない場合も、この機能固有の失敗にはせず通常の scratch 経路を続けます。通常経路の scratch が `K` の行を一つも格納できない場合などには、別条件として `prefill gemm: scratch too small for K=...` を stderr に出して終了します。

## 根拠

- `src/prefill/gemm.cu:1397-1424` — CUDA 側の環境値の読み取り、予算判定、entry 検索・allocation・dequantize、cache GEMM、通常経路への fallback。
- `include/strata/prefill/gemm.hpp:96-102` — CUDA opt-in キャッシュの目的、pointer と形状による key、インスタンスごとの状態。
- `src/prefill/gemm.cu:639-664` — `Gemm` destructor による cache allocation の解放。
- `src/prefill/gemm.cu:630-637,705-735`; `src/prefill/prefill.cpp:1728-1740` — `STRATA_DEQUANT_SIDE` 判定、side scratch の設定と、設定時にキャッシュ分岐を外れる条件。
- `src/prefill/prefill.cpp:989-1000,1734-1740,2694-2699` — `Prefill::Impl` の `Gemm` 所有、初期化、native projection から `Gemm::native()` への呼び出し。
- `src/prefill/prefill.cpp:2694-2698` — native GGUF blocks がない場合は `--native` を要求して projection を失敗させる。
- `tools/par/variants/stack_s1.txt:2` — 候補名のプロファイル記録例（実装や測定結果の根拠にはしていない）。
