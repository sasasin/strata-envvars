# `STRATA_P4_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

layer split を使った pipelined batch の各 GPU stage について、window の launch と完了時刻をファイルへ記録する診断用 trace です。計算方法や batch の選択を変える設定ではありません。環境変数が未設定なら trace file は開かれず、この目的の clock 読み取りも行われません（`include/strata/program/pipe_probe.hpp:31-49`）。

## 値と判定

値全体を真偽値として parse するのではなく、出力先パスとして扱います。

| 環境変数の状態 | 出力先・結果 |
|---|---|
| 未設定 | trace を開かない。既定で無効 |
| 空文字 | `strata-p4-trace.csv` |
| 文字列がちょうど `1` | `strata-p4-trace.csv` |
| その他の文字列 | その文字列をパスとして使用（例: `0`, `true`, `01`, `/tmp/run.csv`） |

`fopen(path, "w")` で開くため、相対パスはプロセスの current working directory を基準とし、同名ファイルがあれば切り詰めます。ディレクトリ作成やパスの検証は行いません。開けなければ stderr に `strata p4: cannot write the trace <path>` と出します。trace pointer は null のままなので、`STRATA_P4_TIMING` も無効なら trace は記録されず、ここでプロセスを終了させる処理もありません（`include/strata/program/pipe_probe.hpp:34-40,46`）。

## 有効になる条件

`--batch` が正、`--batch-groups` が 1 より大きく、layer split により `stages.size() + 1` が 1 より大きいときに pipelined 経路になります。その経路で `PipeProbe` が生成され、`STRATA_P4_TRACE` が読み取られます。これらの条件を満たさない通常の batch / 非 split 経路では、この `PipeProbe` の読み取りと trace は実行されません（`src/program/generate.cpp:13012-13016,13245-13246`）。

## 実行時の詳細

環境は `PipeProbe` の各インスタンス生成時に読み取られ、インスタンスの寿命中に再読込されません。値は `static` cache されていないため、同じプロセスでも後続のインスタンス生成前に環境が変われば、そのインスタンスでは新しい値が評価されます（`include/strata/program/pipe_probe.hpp:31-40`）。CLI 引数や他の環境変数によるパス上書きはありません。`STRATA_P4_TIMING` は別設定で、trace path を選ぶ優先順位には関与しません。

ファイルにはヘッダーなしで、stage の開始時に `L <stage> <time_us> <group>`、完了時に `D <stage> <time_us> 0` を1行ずつ出します。stage と group は 0 始まりです。時刻は `steady_clock` の時刻を microseconds にした値で、暦時刻ではありません。出力は行ごとに flush されます。正常なスコープ終了時にはファイルを閉じます（`include/strata/program/pipe_probe.hpp:26-29,34-42,81-102,131-132`）。実際の hook は window 完了後の `done` と、stage の batch launch 成功後の `launched` です（`src/program/generate.cpp:13274-13280,13417-13427`）。

`STRATA_P4_TRACE` だけを設定し、出力先を開けた場合は trace file が書かれますが、`STRATA_P4_TIMING` 用の集計行は出ません。後者が設定されているときは、pipelined batch が idle になったタイミングで `strata p4: ...` の集計を stderr に出します（`include/strata/program/pipe_probe.hpp:46-48,104-120`; `src/program/generate.cpp:13459-13475`）。

## 根拠

- 全参照の確認では、候補名の本番コード読み取りは `include/strata/program/pipe_probe.hpp:34` の `std::getenv` です。`src/program/generate.cpp:13245` は説明コメント、`src/core/window_limits_test.cpp:36` はテスト内での unset のみです。
- `include/strata/program/pipe_probe.hpp:34-40` は値判定、ファイル open と失敗ログを定義します。
- `src/program/generate.cpp:13012-13016,13245-13246` は pipelined 経路の条件と probe の生成を示します。
- `include/strata/program/pipe_probe.hpp:81-102` と `src/program/generate.cpp:13274-13280,13417-13427` は trace event の記録を示します。
