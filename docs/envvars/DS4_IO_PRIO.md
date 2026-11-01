# `DS4_IO_PRIO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows 上の DS4 I/O queue worker thread について、起動時に `SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST)` を呼び出すための設定有無スイッチです。DS4 の I/O queue はファイル読み取りおよび queue job のメモリコピーを処理します。変数はその worker thread の優先度設定 API を呼ぶかどうかを変えます。値を数値や文字列として選別する処理はありません。

## 値と判定

| 状況 | Strata の判定・処理 |
|---|---|
| 未設定 | 優先度設定 API を呼ばない。 |
| 設定あり（空文字を含む） | `std::getenv(...) != nullptr` が真になり、Windows では `SetThreadPriority` を呼ぶ。値の内容は参照しない。 |
| `0`、`false`、その他の文字列 | いずれも設定ありとして同じ処理。数値変換、文字列比較、範囲チェック、無効値 fallback はない。 |
| Windows 以外 | `_WIN32` のコンパイル条件外なので、この変数を読み取らず、ここでの優先度設定もしない。 |

CLI 引数、設定ファイル、別環境変数との優先順位はありません。Strata は API の戻り値を確認せず、失敗時の警告や fallback も実装していません。

## 有効になる条件

- `src/dsv41/ds4_pool.hpp` の `IoQueue::loop()` が実行されること。DS4 の `ExpertStore` は初期化成功時に `IoQueue` を作り、DS4 model の flow 経路も条件を満たすと別の `IoQueue` を作ります。
- Windows ビルドであること（`_WIN32`）。他 OS には同じ設定処理がありません。
- 対象は `IoQueue` が生成する worker thread です。キューを利用する caller thread にはこのコードから設定しません。

## 実行時の詳細

判定は各 worker thread が `loop()` に入った時に一度行われます。`std::getenv` の結果はキャッシュされませんが、既に起動した worker の優先度を後から更新する再判定もありません。したがって、worker 生成時点で環境変数が設定されていれば API 呼び出しの対象になり、起動後に環境を変更しても既存 worker には反映されません。

`IoQueue` は優先・通常の queue から job を取り出し、直接または buffered read を行い、必要に応じて staging buffer へコピーします。この環境変数自体は queue の順序、読み取り方法、ジョブ数、I/O の結果を変更しません。優先度 API の戻り値は捨てられるため、Strata のログや終了状態から設定成否を判別する出力経路はありません。

## 根拠

- 候補名の Strata リポジトリ全体検索では実装参照は `src/dsv41/ds4_pool.hpp:192` のみです。`_WIN32` guard、設定有無判定、および `SetThreadPriority` 呼び出しは同所にあります。
- I/O worker thread の生成と `IoQueue` の役割: `src/dsv41/ds4_pool.hpp:132-153,189-193`。
- worker が job を取り出し、direct/buffered read や memory copy を行う処理: `src/dsv41/ds4_pool.hpp:194-243`。
- DS4 store における queue 生成: `src/dsv41/ds4_store.hpp:82-97`。
- DS4 model の flow 経路における queue 生成: `src/dsv41/ds4_model.cu:3088-3101`。
