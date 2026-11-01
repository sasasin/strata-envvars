# `DS4_DBG_ROWS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DSV41 の埋め込み処理で、処理対象の入力行ポインタとその先頭4個の `uint16_t` 値を標準エラーへ出す診断フラグです。埋め込み計算の選択や値は変更しません。候補一覧にはありますが、通常の CUDA/HIP/SYCL 経路ではなく、`STRATA_METAL` でコンパイルする Metal の DSV41 経路だけで読み取られます。

## 値と判定

値の文字列や数値は parse せず、`std::getenv("DS4_DBG_ROWS")` が null かどうかだけを判定します。

| 状態 | 判定と結果 |
|---|---|
| 未設定 | 無効。診断用の `host_view()` 呼び出しと `DBG rows_in` 出力を行わない |
| 設定あり | 有効。値が空文字、`0`、`false`、その他のどの文字列でも同じ出力処理を行う |

`static` 等への保存はなく、`embed_addr()` が呼ばれるたびに判定します。実行中に環境変数を変更した場合、その後の呼び出しでの反映可否はプロセス環境を変更する方法に依存します。

## 有効になる条件

- `metal/CMakeLists.txt` が定義する macOS 向け `strata_ds4` ターゲットをビルドし、`STRATA_METAL=1` を付けた経路であること。CMake は非 Apple 環境を拒否し、DS4 のソース群に `src/dsv41/ds4_kernels.cu` と `metal/src/engine/ds4_host.cpp` を組み込みます。
- DSV41 の `embed()` が呼ばれ、`metal_host::embed_addr()` が実行されること。`embed_addr()` は `STRATA_METAL` 条件下から呼ばれ、成功時は埋め込み後に戻ります。失敗時は次に Metal の `embed()` を試し、それも失敗すれば通常の CUDA 互換カーネルを起動します。

CLI 引数や別環境変数による優先順位・上書きはありません。`embed_addr()` はまず GPU stream を同期し、その後にこの環境変数を確認します。この同期はフラグの有無にかかわらず行われます。

## 実行時の詳細

フラグが設定されていると `strata::gpu::host_view(rows)` を取得し、標準エラーに次の形式で1行を出します。

```text
DBG rows_in: ptr=%p view=%p first=%04x %04x %04x %04x
```

`ptr` は渡された `rows`、`view` は `host_view()` の戻り値です。`view` が null の場合、4個の値はそれぞれ `0000` として出力されます。非 null の場合は view の先頭4個を16進数で表示します。この診断ブロックの後も `embed_addr()` は通常どおりライブラリと `ds4_embed_j` pipeline を確認して dispatch し、成功すれば `true` を返します。デバッグ出力自体は失敗を返さず、警告や終了も発生させません。

## 根拠

- `metal/src/engine/ds4_host.cpp:195-204`: `embed_addr()` 内の無条件 stream 同期、設定有無判定、`host_view()` の取得と stderr 出力。`205-251` は以後の pipeline/dispatch と戻り値。
- `src/dsv41/ds4_kernels.cu:2186-2194`: `embed()` が Metal ビルドで `embed_addr()` を先に呼び、失敗時に `embed()` または通常カーネルへ進む。
- `metal/CMakeLists.txt:16-18,135-146,165-171`: macOS 条件、DS4 ソース構成、`STRATA_METAL=1` を付ける `strata_ds4` ターゲット。
- Strata 全体での完全一致検索では、環境から値を読む箇所は `metal/src/engine/ds4_host.cpp:198` のみでした。`docs/DETAILS.md` にこの変数の記載は見つかりませんでした。
