# `DS4_CONCURRENT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや Metal driver 自身が読む環境変数の動作は対象外。

## 役割

DeepSeek v4.1 向け Metal runtime の deferred dispatch 経路で、compute encoder を作る際に渡す dispatch type を選びます。未設定なら Strata は `MTLDispatchTypeSerial`、設定されていれば `MTLDispatchTypeConcurrent` を渡します。Strata が行うのはこの値の選択までであり、Metal 側の実行特性や性能への効果はここでは断定しません。

## 値と判定

| 環境変数の状態 | Strata が選ぶ値 |
|---|---|
| 未設定 | `MTLDispatchTypeSerial` |
| 設定あり（空文字を含む） | `MTLDispatchTypeConcurrent` |

文字列内容は読まず、`getenv("DS4_CONCURRENT")` の null / non-null だけを判定します。`1` である必要はなく、`0`、`false`、空文字を含むどの設定値も同じ扱いです。数値変換、範囲検査、無効値時の fallback はありません。

## 有効になる条件

- `metal/CMakeLists.txt` は macOS 以外では Metal build を停止し、`strata_ds4` 用の `mtl_rt.mm` を `STRATA_DS4_RUNTIME=1` でコンパイルします。したがって、この環境変数の読み取りを含む分岐は DeepSeek v4.1 向け Metal runtime のビルドに限られます。
- `Context::run()` が `ds.size() == 1 && reps == 1 && !barrier_between` の deferred 分岐に入った場合に読み取ります。この分岐では引数 `concurrent` の値によらず、この環境変数で encoder type を決めます。
- それ以外の `Context::run()` 経路ではこの変数を読みません。そこでは `concurrent` 引数に従い encoder を作ります。`run_graph()`、`run_graph_seg()`、`run_icb()` など別 API の concurrent encoder 作成も、この変数を参照していません。

## 実行時の詳細

値は `Context::run()` の呼び出しごとに encoder 作成時点で取得し、関数内の static cache には保存しません。最初の deferred command buffer を作るときに必ず読み、既存 command buffer 内では `DS4_ENC_EACH` または timeline が有効な場合に dispatch ごとに encoder を作り直して再読します。したがって、プロセス起動後の環境変更も、その後の encoder 作成には反映されます。すでに作成済みの encoder の dispatch type は変わりません。

通常の `Context::run()` 呼び出し（例: `metal/src/engine/ds4_finish.cpp` の `g_cx->run({d})`）は既定引数の `concurrent=false` を使いますが、上記 deferred 分岐では `DS4_CONCURRENT` が未設定なら serial、設定ありなら concurrent を選択します。`DS4_ENC_EACH` が設定されているか timeline が有効な場合も、再作成される各 encoder の type を同じ判定で選びます。

この分岐の command buffer は後で `flush_runs()` により commit されます。完了時に失敗状態なら `mtl: deferred command buffer failed: ...` を stderr に出し、`DS4_ERRINFO` も設定されていれば kernel 名一覧も出します。ここでは終了処理は行いません。一方、同期的な `Context::run()` 経路は失敗時に `mtl: command buffer failed: ...` を stderr に出して終了コード 5 で終了しますが、その経路では `DS4_CONCURRENT` は参照されません。この変数固有のログや警告はありません。

## 根拠

- 変数の全参照と deferred encoder 選択、`DS4_ENC_EACH` による再生成: `metal/src/mtl_rt.mm:902-945`（完全一致参照は 925 行と 944 行）。
- deferred command buffer の失敗ログ: `metal/src/mtl_rt.mm:869-895`。
- `Context::run()` の同期経路は引数 `concurrent` を使い、失敗時に終了コード 5: `metal/src/mtl_rt.mm:959-979`。
- API の既定引数と意味: `metal/src/mtl_rt.h:112-123`。
- Metal が macOS 専用であること、および `strata_ds4` が `STRATA_DS4_RUNTIME=1` 付きで runtime を組み込むこと: `metal/CMakeLists.txt:14-17,151-165`。
- 呼び出し例: `metal/src/engine/ds4_finish.cpp:99-111`。
