# `STRATA_PIPELINE_THETA`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの動作は対象外。

## 役割

`--pipeline-windows 2` の pipelined decode で、直前の speculative window が丸ごと受理される推定確率 `p_on` を使い、次の window を stage 0 で先行実行するか決めるしきい値です。既定値は `0.2` です。値を変えると先行実行と prestage の対象が変わります。トークンの受理判定や確率推定そのものを変更する変数ではありません。

この変数は `src/program/generate.cpp` と同梱 SYCL 実装の `sycl/src/program/generate.cpp` にあります。どちらも共通の `pipe_dbg_env()` を通して読む、開発・診断向けの調整フックです。

## 値と判定

`STRATA_PIPELINE_THETA` 自体は文字列全体の検証や範囲制限をせず、C/C++ の `std::atof()` で `float` に変換します。

| 状態 | `pl_theta` |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効、または `STRATA_PIPELINE_THETA` が未設定 | `0.2` |
| デバッグが有効で `STRATA_PIPELINE_THETA` が設定済み | `atof()` の結果を `float` 化した値 |

`atof()` は数値として読める先頭部分を使うため、たとえば `0.35junk` は `0.35`、空文字や数値で始まらない文字列は `0` になります。負数や `1` より大きい値も clamp されません。したがって通常の `p_on`（確率推定値）との比較では、しきい値を負数にすると比較を通りやすく、1 より大きくすると通りません。NaN 等を含む入力もコードで検査・拒否していません。

デバッグゲート `STRATA_PIPELINE_DEBUG` は設定有無だけでなく先頭文字を検査します。未設定、空文字、先頭が `0` の文字列は無効、それ以外の非空文字列（例 `1`, `true`, `false`）は有効です。これは `pipe_dbg_env()` 内の `static const bool` に初回評価時点で保存されます。プロセス内で初めてこの helper が呼ばれた後に `STRATA_PIPELINE_DEBUG` を変更しても判定は更新されません。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が上記の規則で有効であること。無効なら `STRATA_PIPELINE_THETA` は読み取られず、既定値 `0.2` が使われます。
- パイプライン実行が使えること。コードでは `pipe` が有効で `pl_pw >= 2`、かつ GDN snapshot の準備ができた場合に pipelined decode loop を走らせます。通常は `--serve` の layer split で `--pipeline-windows 2` を使う経路です。未対応条件などで `--pipeline-windows` が無効化された場合、この変数は実行結果に影響しません。
- 値の読み取りと適用は request 処理の中にあります。CUDA と SYCL の両実装に同じ helper としきい値判定があります。

同じ debug helper を使う `STRATA_PIPELINE_SWITCH` が設定されていて、ファイルを開けた場合、各 request でそのファイル内の `theta=<値>` が `pl_theta` を上書きします。ファイル中の値も `atof()` で変換され、範囲制限はありません。よってこの switch 値が環境変数の値より優先します。`STRATA_PIPELINE_SWITCH` のパス自体は helper の初回参照時に得た環境文字列へのポインターとして static 保存されますが、指定先ファイルの内容は request ごとに読み直されます。

## 実行時の詳細

各 request のパイプライン初期化時に環境値（または既定 `0.2`）を読み、同じ request の `STRATA_PIPELINE_SWITCH` ファイルが読めたときはその `theta=` 値で置き換えます。`p_on` は drafter の確率などから作られる「前の window が全体受理される」という chain の推定値です。

CUDA 実装では、次の window `B` が ready で、`B.p_on >= theta` であり、context 上限を超えない場合に、stage 0 の speculative launch に進めます。`B.p_on >= theta` は stage 0 の prestage の条件にも使われます（prestage 自体の設定条件も必要です）。後続 stage (`st > 0`) の speculative launch 条件にはこのしきい値比較がありません。そのため、しきい値を超えない場合でも後続 stage の実行条件によっては先行処理されることがあります。

`--dec-timing` の出力では最後に使った `theta` が `strata pipeline: ... below the gate (theta %.2f)` として表示されます。switch ファイルを開けた場合は別途 stderr に `strata pipeline switch: ... theta=%.3f ...` を出します。専用の起動時警告や無効値エラーはありません。

## 根拠

- `src/program/generate.cpp:251-257`: `STRATA_PIPELINE_DEBUG` の判定規則と初回 static cache、および debug 無効時に環境変数を無視する `pipe_dbg_env()`。
- `src/program/generate.cpp:10655-10679`: `STRATA_PIPELINE_THETA` の `atof()`、既定値、switch ファイルからの `theta=` 上書き、stderr の switch ログ。
- `src/program/generate.cpp:11350-11352,11722-11725,11748-11758`: request の値をしきい値に使う箇所、prestage と stage 0 / 後続 stage の条件差。
- `src/program/generate.cpp:11937-11942`: `--dec-timing` の pipeline summary にしきい値を出す箇所。
- `src/program/generate.cpp:7471-7475,7695-7728,11305-11325`: pipeline の適用条件と decode loop の開始条件。
- `sycl/src/program/generate.cpp:293-298,9905-9929,10514-10516`: SYCL 実装の helper、値の読み取りと switch 上書き。ソース上の判定は CUDA 実装と同じ。
- `docs/DETAILS.md:173-179`: pipeline windows と適応 tier の一般説明はありますが、`STRATA_PIPELINE_THETA` の値や効果の説明はありません。この文書では性能値や精度への独自の主張をしていません。
