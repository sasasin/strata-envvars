# `DS4_DBG_EMBWRITE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal 版 DeepSeek V4.1 の旧 embedding dispatch 経路で、embedding dispatch 後の入力行と出力バッファ先頭を stderr に表示する診断用環境変数です。モデル計算の分岐や値を変える処理ではありません。

この経路は、Metal の `embed_addr()` が成功しなかった後に呼ばれる `embed()` のフォールバックです。`embed_addr()` が成功すると呼び出し元がそこで戻るため、通常の raw-address 経路ではこの環境変数のログは出ません（`src/dsv41/ds4_kernels.cu:2186-2193`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効。ログ処理を行わない |
| 設定済み | 値の内容を問わず有効。空文字も有効 |

`std::getenv("DS4_DBG_EMBWRITE")` の null 判定だけを使い、文字列の parse、`1` との比較、数値変換はありません。関数呼び出しごとに dispatch 後に環境を読み、static cache はありません。CLI 引数や別環境変数による値の上書きも、この判定箇所にはありません。

## 有効になる条件

- `metal/CMakeLists.txt` は macOS 以外で構成を失敗させ、この環境変数を読む `ds4_host.cpp` は `strata_ds4` の Metal エンジンソースとして組み込まれます（`metal/CMakeLists.txt:1-18,110-112,132-169`）。CUDA、HIP、SYCL の経路でこの読み取りはありません。
- DeepSeek V4.1 の `embed()` が呼ばれる必要があります。モデル内の呼び出し例は `src/dsv41/ds4_model.cu:7771,8628,8801,9782,9892` です。
- 呼び出し元はまず `embed_addr()` を試します。これが成功を返した場合は旧 `embed()` を呼ばずに終了します。`embed_addr()` がライブラリまたは pipeline を利用できず `false` を返した場合に限り、旧経路が試されます（`src/dsv41/ds4_kernels.cu:2186-2193`、`metal/src/engine/ds4_host.cpp:195-251`）。
- 旧 `embed()` が `ensure()`、host view の確認、buffer wrap、pipeline 取得のいずれかで失敗すると、ログ箇所に到達しません。成功して `run()` した後にだけ診断出力を行います（`metal/src/engine/ds4_host.cpp:31-42,102-143`）。
- 同じ関数の入力・出力ポインタ選択には `DS4_HOSTVIEW` が関係します。これも設定有無で判定され、設定されていれば `host_view()` のポインタ、未設定なら元のポインタを使います。この選択結果が本変数の表示内容に反映されます（`metal/src/engine/ds4_host.cpp:105-110,134-141`）。

## 実行時の詳細

旧 Metal embedding dispatch を実行した後、この変数が設定されていると `flush_runs()` を呼び、stderr に次の2行を出します。

- `DBG embwrite: h=... rows=... h_off=... rows_off=...` — dispatch に使った出力 `hh` と行列 `hrows` のポインタ、および各ポインタのページ内オフセット。
- `DBG embwrite: rows[0..3]=... h[0..3]=...` — `hrows` の先頭4個を16進数、`hh` の先頭4個を浮動小数点数で表示。

値を読む前に範囲や内容を検証する処理はありません。環境変数による追加処理はこの出力と dispatch 完了待ちの `flush_runs()` です。未設定時にはこの flush とサンプル読み取り、出力を行いません（`metal/src/engine/ds4_host.cpp:133-143`）。

ログ出力より前の失敗経路は本変数で変わりません。たとえば Metal init library の compile 失敗では `dsv41 metal: compiling ds4_init.metal failed`、embed の library 不在では `dsv41 metal: embed: no library`、host view 不在では `dsv41 metal: embed has no host view`、wrap 失敗では `dsv41 metal: embed wrap failed` を stderr に出すか false を返します。pipeline 取得の例外も false を返します（`metal/src/engine/ds4_host.cpp:78-84,102-125`）。この関数が false の場合、呼び出し元は Metal launch wrapper の経路へ続きます（`src/dsv41/ds4_kernels.cu:2190-2193`）。

## 根拠

- 環境変数の唯一のソース参照と診断出力: `metal/src/engine/ds4_host.cpp:134-143`。
- 旧 embedding 関数の前処理、成功条件、dispatch: `metal/src/engine/ds4_host.cpp:102-143`。
- raw-address 実装から旧 embedding への呼び出し順: `src/dsv41/ds4_kernels.cu:2186-2193`。
- Metal 限定のビルド条件と `strata_ds4` への組み込み: `metal/CMakeLists.txt:1-18,110-112,132-169`。
- モデル側の embedding 呼び出し例: `src/dsv41/ds4_model.cu:7771,8628,8801,9782,9892`。
