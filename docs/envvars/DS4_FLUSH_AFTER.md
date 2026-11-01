# `DS4_FLUSH_AFTER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数動作は対象外です。

## 役割

DeepSeek V4 用の Metal runtime (`strata_ds4`) で、指定した kernel dispatch の直後に、それまで command buffer に溜めた dispatch を commit し、完了まで待ちます。カーネル名を列挙するデバッグ用フックです。通常の Metal `strata` ターゲットではこの runtime 分岐がビルドされず、この変数は読み取られません。

## 値と判定

値は数値・真偽値として parse されず、カンマ区切りの kernel 名リストとして扱われます。

| 状態・値 | 判定と動作 |
|---|---|
| 未設定 | 空文字列に置き換わり、どの kernel 名にも一致しない。 |
| 空文字列 | 一致対象なし。 |
| `,name1,name2,` | dispatch 名が `name1` または `name2` と完全一致する場合に一致する。 |
| `name1`（前後のカンマなし） | `,name1,` を検索するため一致しない。 |
| 空白、大文字小文字違い、余分な文字 | 正規化されない。検索文字列と dispatch 名が一致しなければ一致しない。 |

コードは `std::string::find("," + dispatch名 + ",")` を使います。部分名一致ではなく、コンマ区切り要素の完全一致です。複数名は先頭・末尾にもコンマを付けて列挙します。空文字列、`0`、`1` も特別な boolean 値ではなく、カンマで囲まれた dispatch 名に一致しない限り効果はありません。

## 有効になる条件

- `metal/src/mtl_rt.mm` が `STRATA_DS4_RUNTIME` 定義付きでコンパイルされる DeepSeek V4 Metal runtime が対象です。CMake は同ファイルの専用 object を `strata_ds4` にリンクします (`metal/CMakeLists.txt:151-169`)。
- `Context::run()` が `ds.size() == 1 && reps == 1 && !barrier_between` の経路を通る必要があります。それ以外はこの判定をせず、先に `flush_runs()` して通常の command buffer 経路へ進みます。
- dispatch 名は `ds[0].p->name` で比較されます。値に列挙した名前と完全一致した dispatch のたびに適用されます。
- 同じ経路で `DS4_PROF` が設定されていると、prof 分岐が先に `flush_runs()` して return するため、この変数による個別判定には到達しません。`DS4_FLUSH_EACH` も有効なら、名前一致に関係なく各 dispatch 後に flush します。
- CLI 引数、他の設定値による値の上書きはありません。

## 実行時の詳細

`DS4_FLUSH_AFTER` の値は `Context::run()` 内の function-local `static const std::string` として最初にこの判定経路を通った時に読み取られ、その後はプロセス内でキャッシュされます。プロセス起動後に環境を書き換えても再評価されません (`metal/src/mtl_rt.mm:902-903,907-908,948-953`)。

一致時は、まず `ds4_gpu_sync_all_streams_weak` が存在する場合に呼び、その後 `flush_runs()` を呼びます。`flush_runs()` は encoder を終了し command buffer を commit し、in-flight buffer があれば完了まで待ちます (`metal/src/mtl_rt.mm:953-956,855-895`)。この分岐自体は有効化ログを出しません。flush 中に deferred command buffer が失敗していた場合は stderr に `mtl: deferred command buffer failed: ...` を出し、`DS4_ERRINFO` も設定されていれば追加で held dispatch 名を出します。この deferred failure 経路はこの箇所ではプロセスを終了しません (`metal/src/mtl_rt.mm:892-895`)。通常の即時実行 command buffer 経路の失敗は stderr に `mtl: command buffer failed: ...` を出し、終了コード 5 で終了しますが、これは `DS4_FLUSH_AFTER` の個別 flush 経路とは異なります (`metal/src/mtl_rt.mm:973-978`)。

## 根拠

- 候補一覧には `DS4_FLUSH_AFTER` が記載されています (`docs/envvars/000_envvers.md:190`)。Strata 所有ソースでの完全一致参照は `metal/src/mtl_rt.mm:951` の読み取り 1 箇所です。
- 値のキャッシュ、kernel 名照合、`DS4_FLUSH_EACH` / `DS4_PROF` との分岐順: `metal/src/mtl_rt.mm:902-957`。
- `flush_runs()` の commit・wait・deferred failure ログ: `metal/src/mtl_rt.mm:855-895`。
- DeepSeek V4 専用 runtime の build 条件とリンク先: `metal/CMakeLists.txt:151-169`。
