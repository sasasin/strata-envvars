# `STRATA_METAL_WRAP_PLE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal エンジンがモデルの GGUF ファイルを Metal バッファへ関連付けるとき、PLE tensor のある領域を別範囲として除外する処理を無効にします。値が厳密に `1` なら、PLE 領域を含むファイル全体を `Context::wrap()` に渡します。これはバッファのラップ方法を選ぶ設定であり、PLE tensor の読み取り値や計算を直接変更する分岐ではありません（`engine/metal/src/engine/window.cpp:745-765`）。

対象コードは macOS の Metal ビルドにあり、Metal エンジンの CMake オプションは既定で有効です（`engine/metal/CMakeLists.txt:1-2,14-20,103-107,152-168`）。

## 値と判定

`Window::init()` の非ストリーミング経路で、PLE tensor からラップ対象範囲を作った後に環境値を調べます。`getenv()` が非 null で、値全体が文字列 `"1"` と一致するときだけ範囲分割を無効にします。数値変換や真偽値の parse、空白除去、先頭文字だけの比較はありません（`engine/metal/src/engine/window.cpp:740-758`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 非ストリーミングで `ranges` が空でなく、各範囲が `maxBufferLength` 以下 | PLE 領域を除く範囲ラップを行う | `1`（全体一致）: 範囲ラップを無効化 | 空文字、`0`、`01`、`1x`、`true`、` 1`、`1 ` など: 範囲ラップを無効化しない |
| ストリーミング、`ranges` が空、またはいずれかの範囲が `maxBufferLength` 超 | この判定による変更なし | 同左 | 同左 |

空文字は未設定と同じく無効です。`ranges` が空でなければ値判定自体は行われますが、いずれかの範囲がデバイスの `maxBufferLength` を超える場合も、その後 `split` を false にします。その場合、この変数の値にかかわらず全体ラップ側へ進みます（`engine/metal/src/engine/window.cpp:748-760`）。

## 有効になる条件

- macOS 向け Metal エンジンで `Window::init()` が実行されること。CUDA / HIP / SYCL ビルドにはこの読み取り経路はありません（`engine/metal/CMakeLists.txt:1-2,18-20`; `engine/src/core/verify.cpp:978-985`）。
- エキスパートをストリーミングする経路ではないこと。`stream_` が true の場合はストリームを開く分岐に入り、対象の `ranges` 作成と環境変数の判定を通りません（`engine/metal/src/engine/window.cpp:738-747`）。
- PLE tensor `per_layer_token_embd.weight` が存在してサイズが正で、ファイル内にその前後どちらかの非空範囲があること。これを満たさず `ranges` が空なら `split` は false となり、値に関係なく全体ラップ側です（`engine/metal/src/engine/window.cpp:748-758`）。
- `ranges` があり、そのいずれの範囲も `maxBufferLength` を超えない場合に限り、値が `1` 以外なら範囲ラップが選ばれます（`engine/metal/src/engine/window.cpp:749-760`）。
- `STRATA_METAL_WRAP_PLE` を上書きする CLI 引数や設定ファイルの処理は、この読み取り箇所にはありません。全体ラップ側では別変数 `STRATA_METAL_WRAP_SPLIT` が、ファイルが Metal の最大バッファ長を超える際のチャンク化を制御します（`engine/metal/src/mtl_rt.mm:321-335`）。

## 実行時の詳細

共有 `Verifier::init()` の Metal 分岐が `window_init()` を呼び、初回初期化では `Window::init()` に進みます（`engine/src/core/verify.cpp:978-985`; `engine/metal/src/engine/window.cpp:3627-3638`）。モデルをストリーミングしない場合、初期化は PLE tensor のページ境界に合わせ、PLE 前後の非空範囲を `ranges` に追加します。デフォルト（未設定・空文字・`1` 以外）では `split` が true のままなら、各範囲に `MADV_WILLNEED`、PLE 領域に `MADV_RANDOM` を指定し、`wrap_ranges()` で範囲だけをラップします（`engine/metal/src/engine/window.cpp:744-765`）。

値が `1` の場合や分割できない場合は、ファイル全体に `MADV_WILLNEED` を指定してから `Context::wrap()` に渡します。チャンク分割が必要なサイズなら同関数が重なり合う複数バッファを作ります。重なり幅は PLE tensor を除く tensor 群から計算し、PLE 自体はその幅に含めません（`engine/metal/src/engine/window.cpp:766-785`; `engine/metal/src/mtl_rt.mm:321-353`）。

環境値は `Window::init()` のこの分岐に到達したときに都度読みます。関数内 `static` などの cache はありません。ウィンドウの初期化完了後は `ready()` によって同じプロセスの通常の再初期化では `Window::init()` を呼ばないため、初期化後に環境を変更しても既存ウィンドウには反映されません。ウィンドウを破棄して新たに初期化する経路では再評価されます（`engine/metal/src/engine/window.cpp:3627-3638`）。

## ログと測定値

この環境変数の値そのものに対するログ、警告、無効値エラーはありません。`wrap_ranges()` が成功すると `mtl: wrapped %.2f GB as %zu separate ranges (of %.2f GB)` を stderr に出します（`engine/metal/src/mtl_rt.mm:356-380`）。全体ラップでサイズ超過によりチャンク化すると `mtl: wrapped %.2f GB as %zu overlapping buffers (maxBufferLength %.2f GB, overlap %.2f GB)` を出します。単一バッファの全体ラップでは成功ログはありません（`engine/metal/src/mtl_rt.mm:321-353,383-398`）。

バッファ作成に失敗した場合、`mtl_rt.mm` は `mtl: wrap range ... failed`、`mtl: wrap ... failed`、または `mtl: wrap chunk ... failed` を stderr に出して終了コード 4 で終了します。チャンク化に必要な範囲が足りない場合も `mtl: wrap %zu: a tensor of %zu bytes does not fit the chunks` を出して終了コード 4 です。`wrap_ranges()` 後に handle が null の場合は `Window::init()` が `metal window: cannot wrap <shard>` を設定して失敗を返します（`engine/metal/src/mtl_rt.mm:321-340,356-389`; `engine/metal/src/engine/window.cpp:784-786`）。

この変数による性能や正確性の測定値は、調査対象コードと関連資料で確認できませんでした。

## 根拠

- 値判定・範囲作成・分岐・`madvise`・ラップ呼び出し: `engine/metal/src/engine/window.cpp:740-785`
- Metal ビルドの適用範囲: `engine/metal/CMakeLists.txt:1-2,14-20,103-107,152-168`
- Metal verifier からの初期化呼び出しと初期化済み判定: `engine/src/core/verify.cpp:978-985`; `engine/metal/src/engine/window.cpp:3627-3638`
- 全体・範囲ラップ、関連ログと失敗経路: `engine/metal/src/mtl_rt.mm:321-398`
