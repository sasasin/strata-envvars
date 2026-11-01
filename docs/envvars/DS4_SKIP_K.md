# `DS4_SKIP_K`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象リポジトリの作業ツリーは `main...origin/main` で未変更。外部ライブラリの環境変数は対象外。

## 役割

Metal の DeepSeek (`strata_ds4`) runtime で、指定した pipeline 名の dispatch を符号化せずに飛ばすデバッグ用フックです。実装コメントは用途を “timing only” としています。指定された kernel の計算が省略されるので、通常の推論・正答性を保つ設定ではありません。

## 値と判定

値を数値や真偽値として parse しません。`Context::run()` の最初の対象 dispatch に到達したとき、環境変数の値を前後にカンマを付けた文字列として `static const std::string` に保存します。その後はプロセス内で再読込しません。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | 保存文字列は空。dispatch はこの指定によって skip されない |
| 空文字 | 保存文字列は `,,` となるが、通常の pipeline 名とは一致せず skip されない |
| pipeline 名 `name` | `,name,` を含むため、その名前の dispatch を skip |
| 複数名 `name1,name2` | それぞれの名前に完全一致した dispatch を skip |
| 部分一致、余分な空白、別の大文字小文字 | 一致しない。トークンの trim・大小文字変換はない |

照合は `skipk.find("," + ds[0].p->name + ",")` です。したがって名前の部分文字列ではなく、カンマで区切られた名前との一致です。値を数値として扱わないため、数値境界や無効数値時の fallback はありません。

## 有効になる条件

- `STRATA_DS4_RUNTIME` が定義されたビルドであること。CMake ではこの macro を `strata_ds4` 用の `ds4_rt_mm` に付けています。
- `Context::run()` に渡される dispatch が 1 件、`reps == 1`、`barrier_between == false` であること。
- 上記条件を外れる呼び出しはこの skip 判定を通りません。`run()` の後続経路では dispatch を encode して command buffer を実行します。
- CLI 引数、設定ファイル、または別の環境変数による上書き・優先順位は、この実装にはありません。

## 実行時の詳細

対象条件を満たすと、runtime は pipeline 名を照合し、一致すれば `encode(impl_->enc_def, ds[0])` より前に `return 0.0` します。この呼び出しでは kernel を command encoder に追加せず、通常経路の dispatch カウンタ等も更新しません。ログ、警告、エラー終了はこの skip 分岐からは発生しません。

判定文字列の初期化は関数内 `static` なので、環境変数を変えても、最初の対象 `Context::run()` 呼び出し後には反映されません。先に対象外経路しか通っていなければ、まだ初期化されず、後の対象呼び出し時の値が使われます。

## 根拠

- `metal/src/mtl_rt.mm:902-910` — `Context::run()` の対象条件、値の取得とキャッシュ、pipeline 名照合、skip 時の早期 return。
- `metal/src/mtl_rt.mm:927-948` — 通常経路では `encode()` と dispatch 計数・トレースを行う位置。skip 分岐はこれらより前。
- `metal/src/mtl_rt.mm:959-979` — 対象条件外の通常経路で dispatch を encode、実行し、command buffer 失敗時には `mtl: command buffer failed: ...` を stderr に出して終了コード 5 で終了。
- `metal/src/mtl_rt.h:112-119` — `run()` の引数の既定値（`reps = 1`、`barrier_between = false`）。
- `metal/CMakeLists.txt:151-165` — `STRATA_DS4_RUNTIME` 付き runtime object を `strata_ds4` に組み込む構成。

`docs/envvars/000_envvers.md:287` に候補名があります。調査対象 commit では上記の Strata 所有 runtime が実際に値を読みます。ほかの直接参照は `rg` で見つかりませんでした。
