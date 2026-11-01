# `DS4_NO_TOUCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更は表示されなかった。調査対象は Strata 所有コード。外部ライブラリ・GPU driver の環境変数動作は対象外。

## 役割

Metal 上の DeepSeek DS4 実装が量子化行列を Metal 用に展開する前に行う、ホストメモリのページ先読みを省略します。通常は `dequant_rows()` が入力行列の範囲を 4096 byte 間隔で読み、`DS4_NO_TOUCH` が環境に設定されている場合はその読み取りループを通りません。GPU の計算方法や出力変換自体を切り替える変数ではありません。

## 値と判定

| 環境変数の状態 | 判定と処理 |
|---|---|
| 未設定 | ページ先読みループを実行する |
| 設定あり（空文字を含む） | ページ先読みループを省略する |

`std::getenv()` の非 null 判定だけを使います。`1` などの値への限定、文字列比較、数値変換はありません。`DS4_NO_TOUCH=0` や空文字も「設定あり」として扱われます。関数呼び出しごとに判定され、static cache はありません。

## 有効になる条件

- `metal/CMakeLists.txt` では `ds4_finish.cpp` を `strata_ds4` のソースに含め、`strata_ds4` を Metal backend 用に構成しています。したがって、この読み取りは Metal の DS4 実行経路に属し、通常の `strata` ターゲット全般に適用される設定ではありません。
- 呼び出し元 `src/dsv41/ds4_gguf.cu::rows()` は `STRATA_METAL` 定義時に Metal 側 `dequant_rows()` を試します。ただし `bf16 == false` かつ `m.raw != nullptr` の場合に限ります。対象 `kind` は GGUF 型 `m.K`、Q8_0 の `8`、BF16 の `0` です。
- Metal 側関数は `n <= 0` または `k <= 0` なら先に成功を返し、`ensure()`、型・寸法検査、`host_view()` も先行します。これらの経路では `DS4_NO_TOUCH` を読みません。

## 実行時の詳細

`dequant_rows()` は対応型を BF16 行列へ展開する入力範囲 `wbytes` を計算し、`DS4_NO_TOUCH` が未設定の場合、`hw` を先頭から `o = 0, 4096, 8192, ...`（`o < wbytes`）の位置で volatile byte 読み取りします。その後 `hw` と出力 `ho` を Metal buffer に wrap し、型に応じた `ds4_dq_*` pipeline を dispatch します。環境変数が設定されている場合は、この先読みだけを省略して、同じ buffer wrap と dequantize dispatch に進みます。コードコメントは、入力行列が未読の file-backed page を含み得ることをこの touch の理由として記しています。

読み取りは `dequant_rows()` を呼ぶたびに行われます。Strata のこのコードにログ出力や警告、終了処理はありません。buffer wrap に失敗した場合や pipeline 取得例外などでは関数が `false` を返し、呼び出し元は続く形式別経路へ進みます。`rows()` は GGUF 型なら `iq::dequant_rows()` を試し、それが失敗すると `fail("rows: a low-bit type not covered")`、その他の不正形式なら `fail("rows: not a BF16 or Q8_0 matrix")` に進みます。これらは `DS4_NO_TOUCH` の値自体による分岐ではありません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:2334-2370` — `dequant_rows()` の早期 return、対応型、`wbytes`、設定有無判定、volatile 先読み、Metal buffer 作成と dispatch。
- `src/dsv41/ds4_gguf.cu:1328-1348` — Metal 条件付き呼び出し、対象型・入力条件、失敗時の後続経路。
- `metal/CMakeLists.txt:132-169` — DS4 の Metal ソース構成と `strata_ds4` ターゲット。
- `metal/include/metal_compat/ds4_metal_host.h:58` — `dequant_rows()` のホスト側宣言。
