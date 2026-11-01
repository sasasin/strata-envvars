# `DS4_WRAP_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 Metal runtime の `Context::wrap()` が runtime 所有 allocation の既存 `MTLBuffer` を再利用できず、入力 CPU アドレスに対する新しい no-copy wrapper を作る fallback に進んだとき、stderr に診断行を出します。ログを有効にするだけで、fallback の可否や wrapper の作り方を変えません。

この参照は `STRATA_DS4_RUNTIME` のビルド分岐内にあります。Metal の CMake はこの macro を DeepSeek engine の `ds4_rt_mm` object にだけ定義して `strata_ds4` に組み込みます。通常の `strata` / Qwen Metal runtime とテスト向け `mtl_rt` にはこの診断分岐がありません。

## 値と判定

| 値 | 判定と結果 |
|---|---|
| 未設定 | 無効。fallback の診断行を出さない |
| 空文字を含む任意の設定値 | 有効。`std::getenv("DS4_WRAP_LOG") != nullptr` 相当の存在判定なので、値の内容は調べない。`1`、`0`、`false` も設定されていれば有効 |

数値変換、文字列比較、範囲制限、無効値時の fallback はありません。CLI 引数・設定ファイルからこの値を上書きする経路も確認できません。

## 有効になる条件

- macOS の Metal runtime 内で `Context::wrap(void*, size_t)` が呼ばれること。
- `STRATA_DS4_RUNTIME` 付きの DeepSeek-V4.1 Metal runtime であること。CMake では `ds4_rt_mm` がこの macro 付きでコンパイルされ、`strata_ds4` にリンクされます。
- runtime allocation の既存 Metal buffer を再利用する分岐を通過すること。再利用関数 `ds4_gpu_buffer_for_cpu` が存在し、`DS4_WRAP_COPY` が未設定で、その関数が対象範囲の buffer を返した場合は既存 buffer を返してここには到達しません。`DS4_WRAP_COPY` は設定値の内容ではなく存在で判定され、設定時（空文字を含む）は再利用分岐をスキップします。

したがって `DS4_WRAP_LOG` が設定されていても、既存 buffer の再利用に成功すればログは出ません。再利用関数がリンクされていない場合、`DS4_WRAP_COPY` が設定されている場合、または lookup が対象 buffer を返さない場合には fallback に進み、`DS4_WRAP_LOG` の存在に応じてログが出ます。

## 実行時の詳細

`Context::wrap()` が fallback に進むたびに `std::getenv("DS4_WRAP_LOG")` を評価します。結果を static 変数などに cache しないため、同一プロセス内でも呼び出し時点の環境値が判定されます（通常の環境変数をプロセス外から変更した場合の反映までは、このコードからは保証されません）。値を読むのは診断分岐だけで、実際の buffer 再利用分岐には関与しません。

有効時の出力は次の形式です。

```text
mtl: wrap FALLBACK p=<pointer> bytes=<size> alloc_remaining=<size>
```

実際の format string は `mtl: wrap FALLBACK p=%p bytes=%zu alloc_remaining=%zu\n` です。`alloc_remaining` は弱参照の `ds4_gpu_alloc_remaining(p)` が使える場合の返り値で、関数が存在しなければ `0` を出します。このログの後も処理は続き、Metal の `newBufferWithBytesNoCopy` で buffer を作ります。作成に失敗した場合は別途 `mtl: wrap %zu failed` を stderr に出し、終了コード 4 で `std::exit(4)` します。この失敗経路自体は `DS4_WRAP_LOG` の値で変わりません。

## 根拠

- `metal/src/mtl_rt.mm:615-622`: `STRATA_DS4_RUNTIME` 内の弱参照関数宣言。
- `metal/src/mtl_rt.mm:623-640`: 既存 buffer 再利用と `DS4_WRAP_COPY` の条件、fallback 時の `DS4_WRAP_LOG` 判定および診断出力。
- `metal/src/mtl_rt.mm:641-654`: fallback 後の no-copy buffer 作成と成功時の戻り値。
- `metal/src/mtl_rt.mm:644-647`: buffer 作成失敗時の stderr 出力と終了コード。
- `metal/CMakeLists.txt:151-165`: `STRATA_DS4_RUNTIME` を `ds4_rt_mm` / `ds4_rt_gpu` に定義し、DeepSeek engine `strata_ds4` に組み込む構成。通常 Metal runtime の `mtl_rt` は同ファイル `:33-39` で macro なしに定義されています。
- `metal/src/engine/window.cpp:576-577,1953-1954`、`metal/src/engine/stream.cpp:458-462`、`metal/src/engine/ds4_finish.cpp` 内の `g_cx->wrap(...)` 呼び出し: engine 側から共通 `Context::wrap()` に至る呼び出し例。

`docs/DETAILS.md` などの設計資料には `DS4_WRAP_LOG` の説明は見当たりませんでした。この文書は上記 commit のソースで確認できる実装だけを記述しています。
