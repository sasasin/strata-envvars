# `DS4_HOSTVIEW`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DeepSeek V4.1（DS4）の埋め込み処理で、fallback の `embed` dispatch が入力 `rows` と出力 `h` をどのポインタで wrap するかを選びます。未設定なら元の device pointer、設定されていれば `strata::gpu::host_view()` が返す host view を使います。

この分岐に到達する前に `embed_addr()` が先に試され、成功すればそこで処理を終えます。そのため通常の `embed_addr()` 成功経路では `DS4_HOSTVIEW` は参照されず、同関数が利用できない場合の fallback に限って効果があります（`src/dsv41/ds4_kernels.cu:2186-2193`）。

## 値と判定

`std::getenv("DS4_HOSTVIEW") != nullptr` という設定有無だけの判定です。文字列の内容は parse しません。

| 状態 | `use_hv` | fallback が wrap するポインタ |
|---|---:|---|
| 未設定 | false | 元の `rows` と `h` |
| 空文字を含め、何らかの値が設定済み | true | `host_view(rows)` と `host_view(h)` |

従って `DS4_HOSTVIEW=0`、`false`、空文字も有効扱いです。既定値は fallback における元ポインタの使用です。CLI 引数や他の環境変数との優先順位・上書きはありません。根拠: `metal/src/engine/ds4_host.cpp:105-110`。

## 有効になる条件

- `strata_ds4` の Metal build で DS4 の埋め込み経路を実行すること。Metal の CMake 定義は `strata_ds4` に `STRATA_METAL=1` を付け、`ds4_kernels.cu` をその実行ファイルへ含めます（`metal/CMakeLists.txt:135-146,165-171`）。
- `embed_addr()` が成功せず、続く `metal_host::embed()` fallback が呼ばれること。`embed_addr()` は共有 MSL library がない場合、または `ds4_embed_j` pipeline の取得で例外になった場合に `false` を返します。成功すれば dispatch・flush 後に `true` を返すため、`embed()` の host-view 分岐は通りません（`metal/src/engine/ds4_host.cpp:195-223,251`; 呼び出し順は `src/dsv41/ds4_kernels.cu:2186-2193`）。

CUDA/HIP ではこの Metal host 実装の呼び出しが `STRATA_METAL` guard 内にありません（`src/dsv41/ds4_kernels.cu:2186-2193`）。候補名の完全一致検索では、この読み取り以外に Strata の参照はありません。CLI・モデル形式などによる追加の条件分岐はこの変数の読み取り箇所にはありません。

## 実行時の詳細

DS4 のモデル処理は `embed(...)` を呼び、Metal build では最初に `metal_host::embed_addr()`、失敗時に `metal_host::embed()` を試します（例: `src/dsv41/ds4_model.cu:7767-7772`）。fallback 内では呼び出しごとに `getenv` を評価し、結果を static cache しません。従って初回評価後の環境変更を固定する仕組みはありません。Strata 内でこの変数を変更するコードは見つかりませんでした。

host-view fallback は選んだポインタのアドレスを 16 KiB 境界へ切り下げ、必要 byte 数を 16 KiB 単位に切り上げて Metal buffer に wrap します。その後 `ds4_embed` pipeline を実行します（`metal/src/engine/ds4_host.cpp:115-143`）。`host_view()` がいずれかで null を返した場合は `dsv41 metal: embed has no host view` を stderr に出して `false`、buffer handle が無効なら `dsv41 metal: embed wrap failed` を出して `false` を返します。pipeline 取得の例外はログなしで `false` を返します（同:111,121,125）。これらの失敗時には呼び出し側が通常の `embed_kernel` dispatch を試します（`src/dsv41/ds4_kernels.cu:2188-2193`）。

この fallback 関数は環境変数の設定有無そのものについてログを出しません。`embed_addr()` が失敗する場合、上記とは別に共有 library のコンパイル失敗ログが出る経路があります（`metal/src/engine/ds4_host.cpp:78-84`）。

## 根拠

- 全候補名参照と fallback の選択: `metal/src/engine/ds4_host.cpp:105-143`。
- 先行する raw-address 経路と失敗条件: `metal/src/engine/ds4_host.cpp:195-223,251`。
- 呼び出し順と通常 dispatch fallback: `src/dsv41/ds4_kernels.cu:2186-2193`。
- Metal build 条件と DS4 実行ファイルへのソース組み込み: `metal/CMakeLists.txt:135-146,165-171`。
- 実際のモデル経路からの呼び出し例: `src/dsv41/ds4_model.cu:7767-7772`。
