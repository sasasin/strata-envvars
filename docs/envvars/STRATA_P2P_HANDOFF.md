# `STRATA_P2P_HANDOFF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

層分割 (`--layer-split`) の各段間で使う hand-off バッファの置き場所を切り替える opt-in です。`--layer-split` と `--split-device` が段と GPU を決め、この変数自体は層分割を開始しません。条件を満たす場合、バッファを次段 GPU の VRAM に確保し、前段 GPU から peer access で書き込みます。未設定または切替条件を満たさない場合は、従来どおり portable な mapped pinned host memory を使います。対象は層分割の verify hand-off であり、変数によってモデル層の計算や hand-off の内容を選ぶ分岐はありません（`engine/src/program/generate.cpp:4778-4804,13223-13235,13262-13270`）。

前段が次段へ渡すのは残差 `R`、最後の層の保留 write `bo`、inject `inj2` です。次段はそれらを自身の verify 入力へ読み込みます。変数の効果はその共有バッファの配置です（`engine/src/core/verify.cpp:1642-1651,3003-3013`）。

## 値と判定

関数ローカルの `static const bool` を初期化するとき、`getenv` が null でなく、値の先頭バイトが NUL でも ASCII `0` でもない場合に true です。文字列全体の数値・真偽値 parse、trim、大文字小文字の正規化はしません。先頭以降の文字は判定に使いません（`engine/src/program/generate.cpp:13232-13235`）。

| 条件 | unset | hand-off の P2P 確保を試みる値 | 試みない値 |
|---|---|---|---|
| 共通の値判定 | false | 空でなく先頭が `0` 以外。例: `1`, `true`, `FALSE`, ` 0`, `x`, `10` | 空文字、先頭が `0`。例: `0`, `00`, `0anything`, `01` |

したがって `1` だけが有効なのではありません。たとえば `false` や先頭に空白のある ` 0` も true、`01` は false です。空文字は「設定済み」ではあっても false になります。この判定は後述の GPU・確保条件を満たすことまでは保証しません。

## 有効になる条件

- `--serve` で `--layer-split` による複数段が構成され、少なくとも一つの段間 hand-off がある必要があります。層分割の設定と段数・デバイスは `engine/src/program/generate.cpp:4778-4804,4835-4848` で検証され、hand-off 確保は `n_stages > 1` の中で行われます（同 `13177-13179,13211-13228`）。
- 各段間で送信元と受信先が異なる GPU である必要があります。`--split-device 0` の同一 GPU 分割では P2P 確保を試みません（`engine/src/program/generate.cpp:13227-13236`）。
- 送受信の両方向について `cudaDeviceCanAccessPeer` が成功し、両方の結果が true で、両方向の `cudaDeviceEnablePeerAccess` が成功する必要があります。すでに有効な peer access は成功として扱います（`engine/src/program/generate.cpp:13236-13250`）。CUDA/HIP の互換ヘッダーではこの2 APIを HIP API に対応づけています（`engine/include/strata/hip_compat/cuda_runtime.h:28-29`; `engine/include/strata/platform/hip_compat/strata_hip.h:98-99`）。
- 受信先 GPU での `cudaMalloc` とゼロ初期化 `cudaMemset` の両方が成功した場合にだけ P2P バッファとして採用します。どの条件に失敗しても pinned host memory の確保へ進みます（`engine/src/program/generate.cpp:13251-13270`）。
- 二方向の peer enable の片方だけ成功してもう片方が失敗した場合も pinned host fallback になります。この分岐内では、先に成功した側の peer access を無効化する処理はありません（`engine/src/program/generate.cpp:13240-13262`）。
- Metal の Strata runtime は peer access の照会時に `0` を返すため、この P2P 分岐には進まず pinned host memory 側になります（`engine/metal/src/gpu/runtime.cpp:380-381`; API の接続は `engine/metal/include/metal_compat/cuda_runtime.h:133-134`）。SYCL 実行ファイルでこの CUDA 名 API がどう解決されるかは、ソース調査だけでは確認できていません。ビルドは行っていません。
- `--pipeline-windows` では通常の `hand` バッファとは別に、もう一方の window parity 用 `hand_b` が常に mapped pinned host memory に確保されます。したがって有効な設定でも pipeline の全 hand-off が P2P になるわけではありません（`engine/src/program/generate.cpp:13352-13373`）。

## 実行時の詳細

値はプロセス起動時に一律で読むのではなく、複数段の hand-off 確保ループが初めてこの宣言へ到達したときに読みます。関数ローカル static のため、その後このプロセス内で環境を変更しても再評価されません（`engine/src/program/generate.cpp:13224-13235`）。

各段間のバッファサイズは、その実行で使う hand-off 行数 `hrows` と `Verifier::handoff_floats(g)` から計算されます。P2P の試行が成功すると受信 GPU を current device にして確保・初期化し、そのポインターを `Verifier::set_stage` に渡します。失敗時の mapped pinned host fallback も同じ `set_stage` に渡されます（`engine/src/program/generate.cpp:13218-13228,13251-13270,13296-13299`）。

前段 verifier は hand-off ポインターへ `R`, `bo`, `inj2` を書き、次段 verifier は同じ3領域を入力へコピーします。コピー kernel は source を読み destination に書くため、P2P 経路で受信 GPU に置いたポインターもこの hand-off に使われます（`engine/src/core/verify.cpp:1642-1651,3003-3013`; `engine/src/kernels/cuda/elementwise.cu:229-234,299-308`）。`Verifier::set_stage` の API コメントは hand-off を mapped pinned memory と記述していますが（`engine/include/strata/core/verify.hpp:199-205`）、本 commit の `generate.cpp` には追加で VRAM ポインターを設定する分岐があります。実際の選択は上記の生成側コードに従います。

## ログと測定値

P2P 確保の成功、peer capability 不足、peer enable 失敗、VRAM 確保失敗から pinned host fallback したことを個別に示すログはありません。起動時には通常の `strata serve: layer split: ... one hand-off per window` が出ますが、P2P の採用有無は表示しません（`engine/src/program/generate.cpp:13236-13270,13344-13350`）。

pinned host memory の確保または device pointer の取得にも失敗した場合は `strata serve: the layer-split hand-off allocation failed` を stderr に出して `return 1` します（`engine/src/program/generate.cpp:13262-13268`）。hand-off コピー kernel の起動エラーは `copy_from_mapped launch: <CUDA/HIP error>` の形式で stderr に出し、`std::exit(1)` します（`engine/src/kernels/cuda/elementwise.cu:122-127,299-308`）。

`docs/MULTI_GPU.md:115-127,139-178` は層分割と `STRATA_SPLIT_OVERLAP` を説明していますが、本変数の測定値や挙動は記載していません。この調査では性能値や実行結果の同一性を主張しません。

## 根拠

- 値の読み取り・判定、peer access、割り当てと fallback: `engine/src/program/generate.cpp:13223-13270`
- CLI による層分割の有効条件: `engine/src/program/generate.cpp:4778-4804,4835-4848,13177-13179`
- 段間 hand-off の接続: `engine/src/program/generate.cpp:13296-13299`; `engine/src/core/verify.cpp:1642-1651,3003-3013`
- pipeline windows の別 hand-off: `engine/src/program/generate.cpp:13352-13373`
- P2P API の HIP 対応: `engine/include/strata/hip_compat/cuda_runtime.h:28-29`; `engine/include/strata/platform/hip_compat/strata_hip.h:98-99`
- Metal runtime の peer 非対応: `engine/metal/src/gpu/runtime.cpp:380-381`; `engine/metal/include/metal_compat/cuda_runtime.h:133-134`
- hand-off コピー kernel と失敗時ログ: `engine/src/kernels/cuda/elementwise.cu:122-127,229-234,299-308`
- 関連資料との照合: `docs/MULTI_GPU.md:115-127,139-178`
