# `HY4_VIT_GELU`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

画像 vision encoder の各層にある FFN の活性化を切り替える。値が未設定なら `VitCfg::gelu_tanh_ffn` の既定値 `true` に従い tanh GELU、値が設定され文字列が厳密に `erf` と一致すると erf GELU、それ以外の設定値では tanh GELU を使う。これは HIP/CUDA、Metal、SYCL の vision 実装にあり、テキストだけの実行では encoder を読み込まないため参照されない。HIP/CUDA では低 VRAM 時の CPU fallback にも同じ設定が適用される。`HY4_VIT_GELU` は adapter の projector にある別の GELU を切り替えない。(`engine/src/hy4flash/run/hy4_vision.h:38-44`, `engine/src/hy4flash/run/hy4_vision.hip.h:604-610,784,989,997`, `engine/src/hy4flash/metal/hy4_metal_vision.h:92-100,252,259`, `engine/src/hy4flash/sycl/sy_vision.h:390-395,506,513`)

## 値と判定

各実装で `getenv` / `std::getenv` の戻り値が null でない場合にだけ `std::string(g) != "erf"` を評価し、その真偽値で既定値を上書きする。文字列全体の大文字小文字を区別する完全一致であり、数値・真偽値としての parse、空白除去、範囲検査はない。(`engine/src/hy4flash/run/hy4_vision.hip.h:609-610`, `engine/src/hy4flash/metal/hy4_metal_vision.h:97-98`, `engine/src/hy4flash/sycl/sy_vision.h:393-394`)

| 実装経路 | unset | tanh GELU になる設定値 | erf GELU になる設定値 |
|---|---|---|---|
| HIP/CUDA、Metal、SYCL | `VitCfg::gelu_tanh_ffn` の既定値 `true` により tanh | `erf` 以外すべて。例: 空文字、`0`、`1`、`true`、`false`、`ERF`、` erf ` | 厳密に `erf` のみ |

`erf` 以外の設定値は「無効値」として拒否されず、すべて tanh を選ぶ値として扱われる。未設定と空文字は異なり、空文字は設定済みなので tanh を明示する。(`engine/src/hy4flash/run/hy4_vision.h:38-44`, `engine/src/hy4flash/run/hy4_vision.hip.h:609-610`, `engine/src/hy4flash/metal/hy4_metal_vision.h:97-98`, `engine/src/hy4flash/sycl/sy_vision.h:393-394`)

## 有効になる条件

- 画像を含む入力で vision encoder の `load` が実行されること。HIP/CUDA の offline runner は画像レコードがある場合に読み込み、HIP/CUDA・Metal・SYCL の server は画像を含むリクエストの処理時に読み込む。テキストのみの経路では環境変数を評価しない。(`engine/src/hy4flash/run/hy4_main.hip.cpp:718-727`, `engine/src/hy4flash/run/hy4_serve.hip.h:431-445`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`, `engine/src/hy4flash/metal/hy4_metal_serve.h:365-373`, `engine/src/hy4flash/sycl/sy_serve.h:393-406`)
- 使用する backend に対応した Strata vision 実装が実行されること。HIP/CUDA 共通コードは `engine/src/hy4flash/run/hy4_vision.hip.h`、Metal は `engine/src/hy4flash/metal/hy4_metal_vision.h`、SYCL は `engine/src/hy4flash/sycl/sy_vision.h` にある。いずれも vision shard の `load` 内で設定する。(`engine/src/hy4flash/run/hy4_vision.hip.h:604-610`, `engine/src/hy4flash/metal/hy4_metal_vision.h:92-100`, `engine/src/hy4flash/sycl/sy_vision.h:390-395`)
- `--vision` は読み込む shard の指定に関係するが、GELU 判定の優先順位を変える CLI 引数はコード上にない。直接参照はこの3箇所で、他の環境変数による上書きもない。未設定時に使う `VitCfg` の値は `true`。(`engine/src/hy4flash/run/hy4_main.hip.cpp:448-449`, `engine/src/hy4flash/run/hy4_vision.h:38-44`)

## 実行時の詳細

各 encoder は shard の probe が成功した後、重みを読み込む前に `gelu_tanh_ffn` を設定する。HIP/CUDA は `VisionEncoder::load`、Metal は `VitMetal::load`、SYCL は `VisionEncoder::load` の各回で環境を読み取る。設定値は encoder オブジェクトの bool に保持され、各 ViT 層の `mlp.dense_h_to_4h` の GEMM に渡る。HIP/CUDA の GPU 経路では tanh/erf の epilogue を選び、同じファイルの CPU fallback では `gemm_cpu` の activation selector `2`/`3` を選ぶ。Metal は GEMM の epilogue `1`/`2`、SYCL は `EPI_GELU_TANH`/`EPI_GELU_ERF` を選択する。いずれも adapter の `vit.perceive.proj.0` は別途 erf を指定している。(`engine/src/hy4flash/run/hy4_vision.hip.h:604-610,784,989,997`, `engine/src/hy4flash/metal/hy4_metal_vision.h:92-100,252,259`, `engine/src/hy4flash/sycl/sy_vision.h:390-395,506,513`)

`load` がすでに成功している encoder は早期 return し、環境を再読しない。そのため同じ encoder の実行中に環境値を変えても設定済み bool には反映されず、次の実ロードまで切り替わらない。HIP/CUDA server は VRAM 条件などにより encode 後に `unload` する経路があり、その後の画像リクエストで再ロードすれば再評価される。Metal/SYCL の `load` にも loaded 状態の早期 return がある。(`engine/src/hy4flash/run/hy4_vision.hip.h:604-610`, `engine/src/hy4flash/run/hy4_serve.hip.h:446-450`, `engine/src/hy4flash/metal/hy4_metal_vision.h:92-98`, `engine/src/hy4flash/sycl/sy_vision.h:390-394`)

## ログと測定値

この変数の値や GELU 選択を示す専用ログ、警告、無効値エラーはない。通常の load 成功ログは backend ごとに出るが、環境変数の値は含まれない。shard の probe・ファイル読み込み等が失敗した場合は `load` が失敗し、offline runner は `images: <error>`、server は `ERR image: <error>` を出す経路がある。これは `HY4_VIT_GELU` 固有の失敗ではない。(`engine/src/hy4flash/run/hy4_vision.hip.h:607-610,629-648`, `engine/src/hy4flash/metal/hy4_metal_vision.h:96-125`, `engine/src/hy4flash/sycl/sy_vision.h:392-405`, `engine/src/hy4flash/run/hy4_main.hip.cpp:721-727`, `engine/src/hy4flash/run/hy4_serve.hip.h:436-445`, `engine/src/hy4flash/metal/hy4_metal_serve.h:366-372`, `engine/src/hy4flash/sycl/sy_serve.h:394-405`)

## 根拠

- 候補名の全参照は上記の HIP/CUDA、Metal、SYCL 各 `load` 内の3箇所。いずれも Strata 所有ソースによる直接の環境読み取り。
- 未設定時の値と役割: `engine/src/hy4flash/run/hy4_vision.h:38-44`。
- 値を各 backend の FFN と adapter に渡す箇所: `engine/src/hy4flash/run/hy4_vision.hip.h:784,989,997`, `engine/src/hy4flash/metal/hy4_metal_vision.h:252,259`, `engine/src/hy4flash/sycl/sy_vision.h:506,513`。
- 呼び出し条件と再利用: `engine/src/hy4flash/run/hy4_main.hip.cpp:718-729`, `engine/src/hy4flash/run/hy4_serve.hip.h:431-450`, `engine/src/hy4flash/metal/hy4_metal_main.cpp:1773-1782`, `engine/src/hy4flash/metal/hy4_metal_serve.h:365-373`, `engine/src/hy4flash/sycl/sy_serve.h:393-406`。
- `docs/DETAILS.md` にこの変数または当該 FFN GELU 切替の説明は見つからなかった。ソースのコメントが参照する `phaseA-tests/hy4/HY4-VISION-DESIGN.md` はこの checkout で見つからず、設計資料との照合はできなかった。
