# `STRATA_METAL_SPIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal ランタイムの `Context::run_graph()` が GPU command buffer の完了を待つとき、最大 20 ms 間状態をポーリングしてからブロッキング待機に移るかを選びます。既定はポーリングを有効にする動作で、厳密に `0` を指定するとポーリングを省きます。対象は Metal の単一 command buffer graph 実行経路です。`Window::run_ds()` などから呼ばれる通常の Metal engine 経路と、同ランタイムを使う graph 呼び出しに影響します（`metal/src/mtl_rt.mm:995-1018`、`metal/src/engine/window.cpp:1546-1548`）。

## 値と判定

値は `std::getenv()` で取得し、得られた文字列全体を `std::string` として `"0"` と厳密比較します。数値変換や真偽値 parse はありません。

| 設定 | `spin` | `run_graph()` の待機 |
|---|---:|---|
| 未設定 | 有効 | command buffer の状態を最大 20 ms ポーリングし、未完了ならブロッキング待機 |
| 空文字 | 有効 | 同上。空文字は `"0"` と一致しない |
| `0` | 無効 | ポーリングせず、未完了なら直ちにブロッキング待機 |
| その他すべて（例: `1`, `00`, `0x`, `false`, 空白を含む値） | 有効 | 未設定時と同じ |

判定式は `!(getenv(...) && string(getenv(...)) == "0")` です。したがって `0` 以外の先頭が `0` の値もポーリングを有効にします（`metal/src/mtl_rt.mm:997-998`）。

## 有効になる条件

- Metal ランタイムの `Context::run_graph()` が呼ばれること。Strata の Metal `Window::run_ds()` は `stream_` が無効ならこの経路に入り、有効なら `run_graph_seg()` を使います（`metal/src/engine/window.cpp:1546-1548`）。別の実行箇所にも `run_graph()` の呼び出しがあります（例: `metal/src/engine/dflash2.inc:693-703`）。
- Metal ランタイム自体がビルドに含まれること。Metal CMake 設定は `metal/src/mtl_rt.mm` から `mtl_rt` ライブラリを構成し、Metal engine のビルドを制御します（`metal/CMakeLists.txt:33-38,73-75`）。
- CLI 引数や別の Strata 環境変数による上書きは、この判定箇所にはありません。

`run_graph_async()` は commit 後に token を返し、完了待ちは `wait_async()` が行いますが、これらの関数には `STRATA_METAL_SPIN` 判定がありません（`metal/src/mtl_rt.mm:1022-1045`）。`STRATA_DS4_RUNTIME` の deferred dispatch が使う `wait_spin()` も別の `DS4_NO_SPIN` を参照するため、この変数の対象外です（`metal/src/mtl_rt.mm:830-842`）。

## 実行時の詳細

`spin` は関数内の `static const bool` であり、プロセス内の最初の `run_graph()` 呼び出し時に一度だけ初期化されます。その後の環境変更は再評価されません。環境変数が未設定または `"0"` 以外なら、command buffer を commit した後に `cb.status` が完了状態に達するか、経過時間が 20 ms に達するまで空ループで確認します。まだ完了していなければ `[cb waitUntilCompleted]` を呼びます。`STRATA_METAL_SPIN=0` ではこの空ループだけを省き、同じブロッキング待機を行います（`metal/src/mtl_rt.mm:1007-1013`）。

この変数固有のログや警告はありません。待機後も command buffer が成功状態でなければ、stderr に `mtl: command buffer failed: ...` を出し、終了コード 5 でプロセスを終了します。これは `spin` の値にかかわらず同じです（`metal/src/mtl_rt.mm:1013-1017`）。実装コメントには M5 Max の Q2_0 decode で同一 token のまま +5% tok/s だった測定が記されていますが、測定条件の詳細な裏付けはこの実装箇所にないため、一般的な性能効果としては扱いません（`metal/src/mtl_rt.mm:996-998`）。

## 根拠

- 値の読み取り、既定値、キャッシュ、20 ms ポーリング、ブロッキング待機、失敗処理: `metal/src/mtl_rt.mm:995-1018`。
- Metal engine からの `run_graph()` / `run_graph_seg()` 選択: `metal/src/engine/window.cpp:1546-1548`。
- 同梱 Metal engine build 設定: `metal/CMakeLists.txt:33-38,73-75`。
- async 経路と DS4 deferred wait の相違: `metal/src/mtl_rt.mm:830-842,1022-1045`。
- `docs/DETAILS.md` には、この変数についての追加説明や測定条件の詳細を確認できませんでした。
