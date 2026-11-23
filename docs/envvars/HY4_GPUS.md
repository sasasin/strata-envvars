# `HY4_GPUS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の HIP/CUDA 実行ファイルと SYCL 実行ファイルで、メイン GPU と Section 4 の expert を配置する追加 GPU を選ぶ。単一の GPU インデックス、GPU 数、または GPU インデックスの CSV を指定する。環境変数自体は GPU を列挙せず、読み取った文字列を実行ファイル内で解釈する。HIP/CUDA 側は `hy4_main.hip.cpp`、SYCL 側は `sy_main.cpp` が読み取り元である（`engine/src/hy4flash/run/hy4_main.hip.cpp:357-362`, `engine/src/hy4flash/sycl/sy_main.cpp:93-95`）。

## 値と判定

どちらの実行ファイルも `getenv` が null のとき空文字列を使う。空文字列は「指定なし」として GPU 列挙・指定値の解析を行わず、既定 GPU（通常 index 0。`--gpu` 指定時はその index）を使う。値は数値として厳密に検証されず、`atoi` による先頭数値の変換が使われる。したがって `2x` は `2`、`true` や空白で始まる非数値は `0` として扱われる。大文字小文字比較はない（HIP/CUDA: `engine/src/hy4flash/run/hy4_main.hip.cpp:361,514-542`; SYCL: `engine/src/hy4flash/sycl/sy_main.cpp:94,199-214`, `engine/src/hy4flash/sycl/sy_common.h:115-151`）。

| 実行経路・形式 | 未設定 / 空文字 | 有効な例 | 無効値・境界の扱い |
|---|---|---|---|
| HIP/CUDA: 区切りなしの整数 | GPU 指定なし。`--gpu` または index 0 | `0` は GPU 0。`1` は GPU 1。`2` 以上は、列挙成功かつ可視 GPU が2台以上なら GPU 0から指定数までを選び、台数で上限を丸める | `0anything` は 0。負数はそのまま GPU index として渡され、後段の HIP/CUDA API 呼び出しで失敗し得る。台数不足・列挙失敗時、`2` 以上も GPU index として扱う |
| HIP/CUDA: CSV | 指定なし | `0,1` は GPU 0 を主、GPU 1 を peer にする | 各要素を `atoi` で変換する。範囲検査や空要素の除去はこの箇所にない。先頭以外の重複 peer は除去され、主 GPU と同じ値は peer に加えない。負値や範囲外値は後続 API 呼び出しで失敗し得る |
| SYCL: 区切りなしの整数 | 指定なし。`--gpu` または index 0 | `2` は主 GPU に加えて最大2台、すなわち合計2台を選ぶ | `atoi` の結果を `[1, 可視 GPU 数]` に丸める。`0`、負数、非数値は1台扱い、過大値は全可視 GPU 扱い |
| SYCL: CSV | 指定なし | `0,1` は GPU 0 を主、GPU 1 を peer にする | 空要素は無視。各要素を `atoi` で変換し、有効範囲外は無視して stderr に `[gpu] ignoring out-of-range device index %d (visible GPUs: %d)` を出す。重複は除去。全要素を無視した場合は `--gpu` または index 0 が残る |

HIP/CUDA の数値指定は「GPU 数」か「単一 index」かを値と `hipGetDeviceCount` の結果で切り替える一方、SYCL の数値指定は常に台数として扱う。CSV の有効範囲検証も両経路で異なる（`engine/src/hy4flash/run/hy4_main.hip.cpp:516-542`, `engine/src/hy4flash/sycl/sy_common.h:116-151`）。

## 有効になる条件

- `strata-hy4` の HIP/CUDA ビルド、または `strata-hy4-sycl` の起動経路で読み取られる。これは通常エンジンの一般 GPU 分割設定とは別の Hy4-Flash 固有の選択処理である（`engine/src/hy4flash/run/hy4_main.hip.cpp:334-362`, `engine/src/hy4flash/sycl/sy_main.cpp:79-95`）。
- 非空値の場合、HIP/CUDA は `--info` の早期 return より後に値を GPU 選択へ適用する。SYCL は CLI 引数を読み終えた後、GPU device/queue に触れる前に適用する（`engine/src/hy4flash/run/hy4_main.hip.cpp:507-518`, `engine/src/hy4flash/sycl/sy_main.cpp:199-214`）。
- `--gpus VALUE` と `--devices VALUE` は同じ設定文字列を上書きし、複数回指定すれば最後に処理した値が残る。CLI で空文字を渡すと環境変数の値を消して指定なしになる。`--gpu N` は単一 GPU の既定主 index を指定する。CSV は主 GPU をその先頭の有効 index に置き換える。数値形式では、HIP/CUDA は「2以上かつ複数 GPU が列挙できる場合」に台数指定として主 GPU を含む選択を作り、それ以外は値を主 index とする。SYCL は台数指定なので、`--gpu` が主 GPU index として使われる（`engine/src/hy4flash/run/hy4_main.hip.cpp:360-405,514-542`, `engine/src/hy4flash/sycl/sy_main.cpp:94-95,130-136,199-214`）。
- SYCL の可視 GPU リストは `enum_gpu_devices()` で作られ、`HY4S_BACKEND=opencl` の場合は OpenCL、そうでなければ Level Zero を優先して絞り込む。優先 backend がない場合は列挙結果の最初の device の backend に fallback する（`engine/src/hy4flash/sycl/sy_main.cpp:85-92`, `engine/src/hy4flash/sycl/sy_common.h:94-112`）。
- 指定した GPU を peer expert として使うには、選択先で Hy4-Flash の Section 4 expert 配置・実行処理に到達する必要がある。HIP/CUDA では追加 GPU の peer 配置処理がビルド条件 `HY4_CUDA || HY4_HIP_PEERS` の下にある。SYCL では `peer_devs` が expert setup に渡され、peer cache の初期化が行われる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-899`, `engine/src/hy4flash/sycl/sy_main.cpp:245-246,298-309`, `engine/src/hy4flash/sycl/sy_graph.h:144-153`）。
- モデルの expert が主 GPU の cache に収まる場合など、追加 GPU に割り当てる expert がないと peer 指定による推論処理は実質発生しない。SYCL の peer expert 実行は decode 時に cache が有効で、`T <= SyPeerExperts::MAX_DEC_T` の経路などの条件で呼ばれる（`engine/src/hy4flash/sycl/sy_graph.h:1151-1168`）。
- SYCL の `--load-only` でも expert setup は実行されるが、その後の token decode は行わない（`engine/src/hy4flash/sycl/sy_main.cpp:298-319`）。

## 実行時の詳細

値は各 `main()` のローカル文字列初期化で一度読み取られ、プロセス実行中に再読込・cache 更新するコードはない。環境変数の変更は次のプロセス起動から反映される。子プロセスへの転送処理はこの設定について見つからなかった（`engine/src/hy4flash/run/hy4_main.hip.cpp:334-362`, `engine/src/hy4flash/sycl/sy_main.cpp:79-95`）。

HIP/CUDA は選択した主 GPU を `hipSetDevice` に渡し、peer index 群とともに serve options または `GpuModel` に保存する。モデルロード時に peer の VRAM 予算を見積もり、Section 4 expert を配置する。peer の空き VRAM が必要 reserve 以下なら、その GPU には expert を置かず `[load] peer GPU%d free ... placing 0 experts ...` を stderr に出す。P2P が使えない場合は host-pinned bounce に fallback する経路がある（`engine/src/hy4flash/run/hy4_main.hip.cpp:543-574,640-659`, `engine/src/hy4flash/run/hy4_gpu_model.hip.h:886-905,1144-1156`）。

SYCL は GPU を列挙して `parse_gpu_spec()` を実行し、主 index を `primary_gpu_index` に設定する。`Q()` は初回呼び出し時に static queue を生成し、その時点の主 GPU index を使う。`peer_devs` は serve options または `setup_experts_unified()` に渡され、初期化時に GPU 0 cache にない expert を peer GPU に割り当てる。queue 作成失敗は `[peer-sycl] skipping GPU%d (%s): queue creation failed (%s)` を stderr に出してその peer を飛ばす（`engine/src/hy4flash/sycl/sy_main.cpp:199-214,245-248,298-309`, `engine/src/hy4flash/sycl/sy_common.h:154-176`, `engine/src/hy4flash/sycl/sy_peer.h:231-260`, `engine/src/hy4flash/sycl/sy_graph.h:144-153`）。

## ログと測定値

SYCL の CSV index が範囲外のときは前節記載の `[gpu] ignoring out-of-range device index ...` を stderr に出す。peer queue 作成失敗時のログ、および HIP/CUDA の peer 予算不足ログも上記のとおりである。HIP/CUDA 側の無効 index はこのパーサーで検査されず、後続の HIP/CUDA 呼び出しが失敗し得る。Hy4-Flash の `HY4_GPUS` 自体に成功時の選択ログは見つからなかった。Strata の資料にこの環境変数の測定値は見つからなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:334-405,507-542,543-574,640-659`
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:877-905,1144-1156`
- `engine/src/hy4flash/sycl/sy_main.cpp:79-95,130-136,199-214,245-248,298-319`
- `engine/src/hy4flash/sycl/sy_common.h:94-112,115-176`
- `engine/src/hy4flash/sycl/sy_peer.h:231-260`
- `engine/src/hy4flash/sycl/sy_graph.h:144-153,1151-1168`
