# `DS4_IO_STATS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 エンジンの `IoQueue` が処理した読み取りジョブの数、キュー待ち時間、読み取り時間、読み取り後のコピー時間、およびジョブあたりのバイト数を集計し、キュー破棄時に `stderr` へ一行出力する診断用スイッチです。読み取り方法やスケジューリングを変更しません。

対象名の全参照をソース全体で検索したところ、実際の環境読み取りは `src/dsv41/ds4_pool.hpp` の2箇所（処理集計の有効判定と破棄時の出力判定）だけでした。他の箇所はコメント中の記載です。

## 値と判定

| 状態 | 集計 | 破棄時の出力 |
|---|---|---|
| 未設定 | 無効 | 出力しない |
| 空文字を含む何らかの値を設定 | 有効 | 対象ジョブが1件以上集計されていれば出力 |

両方の判定は `std::getenv("DS4_IO_STATS") != nullptr` です。値を数値や文字列として parse しません。したがって `DS4_IO_STATS=0`、`false`、空文字も設定ありとして扱われます。CLI 引数や別変数による上書き・優先順位はありません。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` でビルドされた `strata-dsv41` が対象です。CMake ではこのターゲットは CUDA または HIP backend の構成内にあり、`STRATA_HIP_GFX906` の場合は作られません。オプションの既定値は OFF です（`CMakeLists.txt:906-920`）。
- 実行時に `IoQueue` が作られる必要があります。ソース上では、MXFP4 の DeepSeek-V4.1 prompt streaming 経路で flow が有効な device chunk（`src/dsv41/ds4_model.cu:3054-3100`）、または条件を満たす RAM expert store（`src/dsv41/ds4_model.cu:5410-5413,5485-5492`; 生成時の queue は `src/dsv41/ds4_store.hpp:73-97`）が該当します。
- streaming の queue は `DS4_FLOW`、フォーマット、tensor-parallel 時の `DS4_FLOW_TP` などで作成されない場合があります。RAM store の queue は store サイズ、GGUF、MXFP4、file experts、初期化成功などに依存します。これらの条件が満たされない実行では、この変数を設定しても集計行は出ません。

## 実行時の詳細

`IoQueue::push()` は投入時刻を各ジョブへ記録します。worker はジョブ開始から読み取り処理終了までを計り、環境変数を最初に評価した時点の結果を関数内 `static const bool stats` に保存します。そのため、最初のジョブ処理後にプロセス内で環境を変更しても集計の有効状態は変わりません（`src/dsv41/ds4_pool.hpp:150,169-179,190-204,214-255`）。

集計対象は `j.mem == nullptr && j.cancel == nullptr` のジョブです。ディスクからの需要読み取りは対象になります。メモリからのコピーは除外され、キャンセル可能な speculative/prefetch 読み取りも除外されます。ファイル読み取りが失敗した場合も、成功判定 `ok` を条件にせず時間と `len` を集計します。カウンターは `IoQueue` インスタンスごとに保持されます。

出力は各 queue のデストラクタで、その queue の対象ジョブが1件以上あり、かつデストラクタ実行時にも変数が設定されている場合に行います。したがって、集計が有効だった場合でも破棄時に unset なら出力されず、逆に破棄時に設定があっても集計時に unset だった場合は対象ジョブがなく出力されません（`src/dsv41/ds4_pool.hpp:155-160,246-255`）。出力形式は次のとおりです。

```text
io stats: N jobs, mean queue wait Q ms, read R ms, copy C ms, B MB a job
```

`Q` は投入時刻から worker の処理開始まで、`R` は読み取り処理区間、`C` はその後 `keep` 領域へ複製する区間を含む時間の平均です。`B` は `len` の平均を MB 単位で示します。いずれもジョブ単位の平均で、ファイル読取り失敗時にもそのジョブは件数・時間・バイト数に含まれます。

この診断コード自体は警告、終了コード変更、失敗時 fallback を起こしません。読み取り失敗の伝達は別の `bad` フラグ経路で行われます（`src/dsv41/ds4_pool.hpp:260-266`; RAM store では `src/dsv41/ds4_store.hpp:514-525`）。

## 根拠

- 全参照と設定有無判定、統計出力・時刻集計: `src/dsv41/ds4_pool.hpp:150-160,169-179,190-204,214-266,275-276`
- RAM store の queue 作成と需要 / speculative read の分類: `src/dsv41/ds4_store.hpp:73-97,485-506`
- prompt streaming の queue 作成条件と生成時の read job: `src/dsv41/ds4_model.cu:3054-3100,3978-4073`
- エンジンのビルド条件: `CMakeLists.txt:906-920`
