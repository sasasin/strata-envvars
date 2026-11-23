# `INK_HIP_FORCE_SK_TRANSCODE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP バックエンドで GGUF 由来の expert をロードするとき、HIP の native GGUF_RAW kernel が使える型であっても、S_K 形式への変換を選ばせる診断・経路選択用の環境変数です。未設定または `atoi` の結果が 0 なら、両方の投影型に HIP native kernel がある場合は元の GGUF_RAW データを保ちます。非ゼロなら、その native 経路を使わず S_K の codec とレイアウトに切り替えます。モデル選択や生成時の CLI 設定を変える変数ではありません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:937-962`）。

この読み取りは Inkling-2 の HIP backend にだけあります。backend factory は `INKLING_ENABLE_HIP` が定義され、CUDA / EP CUDA の先行分岐に入らない場合に HIP backend を選びます。`force_cpu` の場合は CPU backend になります（`engine/src/inkling2/ink_backend.h:131-168`）。HIP backend のビルド定義は HIP plugin の compile command に付与されます（`engine/src/inkling2/hip/CMakeLists.txt:74-82`）。

## 値と判定

`HipBackend::init()` 内で `std::getenv` の戻り値を `std::atoi` に渡し、結果が 0 でないかを判定します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-565,937`）。文字列全体の妥当性検査はなく、数値の先頭部分だけが変換に使われます。空白と符号を含む数値 prefix は `atoi` に従い、後続の非数値文字は無視されます。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP backend の初期化 | `force_sk_tc=false` | `1`, `-1`, `2abc`（`atoi` が非ゼロ） | 空文字、`0`, `0anything`, `true`, `abc`（`atoi` が 0） |

CLI 引数や設定ファイルによる上書きはありません。`atoi` の整数表現範囲外の入力について Strata 側に検査やエラー処理はありません。

## 有効になる条件

- 実行経路が Inkling-2 HIP backend の `init()` であること。CPU、CUDA、Metal、SYCL backend はこの変数を読みません。CUDA と HIP の両方がビルド有効なら factory は CUDA を先に選択します（`engine/src/inkling2/ink_backend.h:150-168`）。
- モデルが `ModelSourceKind::Gguf` で `model.gguf_adapter` を持つこと（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:941-942`）。`.strata` など他形式ではこの分岐に入りません。
- expert directory の項目で `gu_code_id` または `dn_code_id` の少なくとも一方が `CODE_GGUF_RAW` であること（同:944-947）。
- 各 expert の層番号が adapter の layer 範囲内にあること（同:947-949）。
- 投影型に対応した HIP native kernel が両方ともある場合、変数が数値として非ゼロなら native GGUF_RAW 維持を抑止して S_K レイアウトへ切り替えます。どちらかの型に native kernel がなければ、unset / 0 でも変換側に進むため、変数による追加の切り替えはありません（同:950-962）。
- `--force-cpu` 相当の経路では CPU backend が選ばれ、この変数の読み取り箇所に到達しません（`engine/src/inkling2/ink_backend.h:150-168`）。

## 実行時の詳細

変数は `HipBackend::init()` の GGUF expert 準備時に読み取られます。`static` cache はなく、初期化を呼ぶたびに評価されます。実行中に環境を変更して既に初期化済みの backend に反映する処理はありません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-565,937-962`）。Strata 内で子プロセスへ値を転送する処理も、この名前については見つかりませんでした。

各対象 layer の GGUF 型を使って `choose_sk_code_for_ggml()` が gu / down 投影の S_K codec を決め、expert directory の code ID、down offset、body size を更新します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:954-962`; codec 選択は `engine/src/inkling2/ink_gguf_transcode.h:84-113`）。その後、VRAM・peer GPU・RAM のロード対象は `read_expert_for_hip()` を経由し、raw expert body の読み込みと S_K 形式への変換が行われます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1104-1149,1152-1204,1206-1233,2611-2622`; 変換処理は `engine/src/inkling2/ink_gguf_transcode.h:404-448`）。変数はモデルファイルを書き換えず、backend が保持・転送する expert の表現を選びます。

HIP backend の初期化に失敗すると通常 CLI では `init: <理由>` を stderr に出して終了コード 1、serve 経路では `ERR init: <理由>` を protocol に返して終了コード 1 になります（`engine/src/inkling2/ink_main.cpp:564-569`）。変換処理には短い body、header magic 不一致、形状条件不成立、未対応 ggml 型、body 範囲外などのエラー経路があります（`engine/src/inkling2/ink_gguf_transcode.h:261-296,428-447`）。この環境変数自体に対する警告・有効化ログはありません。

## ログと測定値

`force_sk_tc` が false で、native GGUF_RAW kernel を使う expert が 1 件以上あると、stderr に次のログが出ます。したがって変数を非ゼロにして全対象を変換側へ送った場合、このログは出ません（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:950-967`）。

```text
[ink-hip] native lossless GGUF_RAW GPU kernels active for %zu/%zu experts (zero S_K transcode)
```

変数の有効・無効を直接示すログはありません。変換時に失敗すると、その理由が `init:` または `ERR init:` に続いて観測されます。Strata の資料にこの変数を使った性能測定値は見つかりませんでした。

## 根拠

- 直接の環境変数読み取り、GGUF / adapter 条件、native kernel 判定、S_K directory 更新、native 経路ログ: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:937-967`
- 読み取りを含む HIP backend 初期化: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:507-565`
- HIP / CPU / CUDA 等の backend 選択条件: `engine/src/inkling2/ink_backend.h:131-168`
- HIP backend の compile 定義: `engine/src/inkling2/hip/CMakeLists.txt:74-82`
- transcode codec 選択と GGUF_RAW expert の読み取り・変換: `engine/src/inkling2/ink_gguf_transcode.h:84-113,244-296,404-448`
- GPU/RAM 配置での変換呼び出しと実際の read/transcode helper: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1104-1233,2611-2622`
- 初期化エラーの出力と終了コード: `engine/src/inkling2/ink_main.cpp:564-569`
