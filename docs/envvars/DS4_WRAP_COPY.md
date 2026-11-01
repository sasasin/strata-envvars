# `DS4_WRAP_COPY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`DS4_WRAP_COPY` が設定されていると、DeepSeek 用 Metal runtime の `mtl::Context::wrap()` は、渡された CPU address 範囲が `strata::gpu` の既存 allocation 内にあるかを調べて既存 `MTLBuffer` を使う経路を飛ばします。そのまま通常の wrap 処理へ進み、渡された範囲に対して `newBufferWithBytesNoCopy` を呼びます。環境変数名に `COPY` とありますが、この分岐で Strata が明示的なデータコピーを行う処理はありません。

この分岐は `STRATA_DS4_RUNTIME` を定義してビルドした `strata_ds4` 用実装に限られます。通常の `strata` など、その macro がない実装ではこの変数を読みません（`metal/CMakeLists.txt:151-165`, `metal/src/mtl_rt.mm:615-667`）。

## 値と判定

値の内容は比較・変換されず、`std::getenv` が null を返すかどうかだけを見ます。

| 値の状態 | 動作 |
|---|---|
| 未設定 | `ds4_gpu_buffer_for_cpu` が利用可能なら既存 runtime buffer の検索を試みる。範囲が見つかればそれを返し、見つからなければ fallback する。 |
| 設定済み（空文字を含む） | 既存 runtime buffer の検索を行わず、fallback する。 |

したがって `0`、`1`、その他の文字列に数値・真偽値としての違いはありません。CLI 引数や別の環境変数との優先順位もありません。設定値を cache する `static` 変数はなく、`Context::wrap(void*, size_t)` が呼ばれるたびに設定有無を読みます。プロセス起動後に環境が変わった場合も、その後の呼び出しでは新しい状態が参照されます（`metal/src/mtl_rt.mm:623-635`）。

## 有効になる条件

- `STRATA_DS4_RUNTIME` が有効な `mtl_rt.mm` が実行されること。CMake はこの macro を `ds4_rt_mm` と `ds4_rt_gpu` に付け、両 object を `strata_ds4` に組み込みます（`metal/CMakeLists.txt:151-165`）。
- その実装で `Context::wrap(p, bytes)` が呼ばれること。呼び出し例には DeepSeek 側の host view / 出力 buffer の wrap があります（`metal/src/engine/ds4_host.cpp:47-52`, `metal/src/engine/ds4_finish.cpp:142-149`）。
- 変数が未設定のときに既存 buffer を使うには、weak import された `ds4_gpu_buffer_for_cpu` が利用可能で、helper が指定範囲全体を一つの runtime allocation 内に見つける必要があります。helper は範囲の開始・終了を検査し、外に出る範囲や未登録の範囲では null を返します（`metal/src/mtl_rt.mm:615-628`, `metal/src/gpu/runtime.cpp:418-428,839-842`）。

OS や GPU 世代による値判定の違いはありません。Metal の DS4 runtime ビルド条件が適用範囲を決めます。

## 実行時の詳細

未設定で helper が範囲を見つけた場合、Strata は返された buffer を `Buffer.handle` に、helper が返した offset を `Buffer.bias` に入れて返します。見つからない場合、または `DS4_WRAP_COPY` が設定されている場合は、Strata は渡された pointer と長さを使って `newBufferWithBytesNoCopy` を呼びます（`metal/src/mtl_rt.mm:623-667`）。

この fallback で buffer の作成に失敗すると、stderr に `mtl: wrap %zu failed` を出し、終了コード 4 でプロセスを終了します。`DS4_WRAP_LOG` も設定されている場合は fallback に入るたびに stderr へ `mtl: wrap FALLBACK p=%p bytes=%zu alloc_remaining=%zu` を出します。`DS4_WRAP_COPY` 自体に対応するログや警告はありません（`metal/src/mtl_rt.mm:637-667`）。

## 根拠

- 候補名の全参照検索では、環境変数の読み取りは `metal/src/mtl_rt.mm:625` の一箇所です。`000_envvers.md` に載った候補名が実際に読まれていることを確認しました。
- runtime buffer の範囲検索と wrap の分岐: `metal/src/mtl_rt.mm:615-667`, `metal/src/gpu/runtime.cpp:418-428,839-842`。
- DS4 runtime 専用の build macro とリンク先: `metal/CMakeLists.txt:151-165`。
- `docs/DETAILS.md` には `DS4_WRAP_COPY` の記述が見つかりませんでした。
