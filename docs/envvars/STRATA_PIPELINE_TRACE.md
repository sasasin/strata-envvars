# `STRATA_PIPELINE_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

パイプライン decode ループ内で記録したイベントを、指定ファイルに追記する診断用トレース先である。イベントにはループ開始からの経過ミリ秒、イベント名、sequence 番号、整数フィールドが入る。生成処理や pipeline の有効化をこの変数自体が制御するものではない。CUDA/HIP 共通側の `engine/src/program/generate.cpp` と SYCL 側の `engine/sycl/src/program/generate.cpp` に実装がある（それぞれ `:21930-21939,22567-22572`、`:11903-11912,12533-12538`）。

## 値と判定

`pipe_dbg_env("STRATA_PIPELINE_TRACE")` は、まず `STRATA_PIPELINE_DEBUG` を確認する。debug が有効なときに限り、対象変数を `std::getenv` で読み、その値をファイル名として使う。`STRATA_PIPELINE_DEBUG` は未設定・空文字・先頭文字が `'0'` の値（`0`、`0anything` など）なら無効。それ以外は有効（例: `1`、`true`、`false`、先頭が空白の値）であり、全体の数値・真偽値 parse、大文字小文字変換はしない（両実装の helper: `engine/src/program/generate.cpp:684-687`、`engine/sycl/src/program/generate.cpp:337-340`）。

debug が有効な場合、`STRATA_PIPELINE_TRACE` は設定有無だけで判定し、文字列の検証や変換はしない。空文字も unset ではなく空のパスとして扱われる。値は `std::fopen(path, "a")` に渡され、開けなければ書き込みを行わず、その失敗を示すログも出さない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_PIPELINE_DEBUG` が無効 | トレースなし | 該当なし。対象変数は helper から `nullptr` として見える | 設定されていても読まれず無視 |
| `STRATA_PIPELINE_DEBUG` が有効 | トレース先なし | 開けるファイルパス。相対パスもそのまま `fopen` に渡す | 対象変数としての無効値判定はない。空文字や開けないパスは設定済みだが、ファイルを開けず出力されない |

debug 判定は `pipe_dbg_env` 内の関数ローカル `static` bool に保存され、最初の呼び出し時に固定される。trace パスも pipeline decode ループへ初めて入った時点で `static` に保存されるため、その後の環境変更では切り替わらない（同上の helper と `engine/src/program/generate.cpp:21930-21932`、`engine/sycl/src/program/generate.cpp:11903-11906`）。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が helper の上記規則で有効であること。これは対象変数を読むための必須条件。
- `--pipeline-windows` などで pipeline 自体が有効で、**decode 側の 2-window loop** が実行されること。CUDA/HIP 共通側では `pipe`、`pl_pw >= 2`、snapshot が準備済みであることが必要（`engine/src/program/generate.cpp:13263-13267,21810-21822`）。SYCL 側も `pipe`、`pl_pw >= 2`、`pl_snap2[0]` が必要（`engine/sycl/src/program/generate.cpp:7712-7717,11783-11796`）。`--pipeline-windows 1` の prompt 用 pipeline だけでは decode trace は出ない。
- pipeline はサーバーの layer split などの対応条件を満たす必要がある。SYCL の自動選択は `--serve`、Battlemage の2 GPU split、MTP drafter などの条件に基づき、`STRATA_PIPELINE_AUTO=0` で無効化できる。明示指定時にも serve / GPU split / 2 stage / MTP といった検証条件がある（`engine/sycl/src/program/generate.cpp:3587-3618,3620-3634`）。CUDA/HIP 共通側は split の各 stage が独立 GPU であることを含む pipeline 条件を確認する（`engine/src/program/generate.cpp:13263-13267`）。
- `STRATA_PIPELINE_SWITCH` が debug helper 経由で設定され、pipeline が成立した場合、switch ファイル内の `pw=` が `pl_pw` を変更できる。`pw=2` は decode loop の条件を満たし得るが、snapshot・リクエスト状態など残る条件は引き続き必要（CUDA/HIP: `engine/src/program/generate.cpp:20245-20248,20284-20290,21810-21822`、SYCL: `engine/sycl/src/program/generate.cpp:11151-11169,11783-11796`）。
- 実際のリクエストが取消済みでなく、生成上限にも達していないこと。repetition penalty または coupled draft sampling の request は serial decode に切り替わる（CUDA/HIP: `engine/src/program/generate.cpp:21812-21822`、SYCL: `engine/sycl/src/program/generate.cpp:11784-11796`）。

したがって `STRATA_PIPELINE_TRACE` だけを設定しても pipeline は有効にならず、通常の serial decode では trace は作られない。

## 実行時の詳細

対象パスは `std::getenv` が返す文字列のまま保持され、パイプライン decode のイベント callback `tre` が呼ばれるたび、`"%.3f %s %d %d %d\n"` の形式でリクエスト内バッファへ蓄積する。時刻はその decode loop の `Clock::now()` 起点からのミリ秒である。イベント名には `F0` / `F1`（stage の処理完了）、`U`（rollback）、`V`（verify 判定）、`CL`（chain launch）、`CD`（draft/lookup の決定）、`L0` / `L1` / `CE` などがあり、個々の event の引数はイベント呼び出し側で異なる（CUDA/HIP: `engine/src/program/generate.cpp:21934-21939,21954,22103,22165,22183,22443,22509,22542`、SYCL: `engine/sycl/src/program/generate.cpp:11907-11912,11926,12107,12155,12183,12419,12485,12508`）。

ループを drain した後、バッファが空でなければファイルを append mode で開き、`# request p0=<prompt last-token index>` の行、イベント行を順に書いて閉じる。ファイルの open 成功・write 結果を検査せず、失敗ログもない。通常の drain 経路で書き込まれるため、ループ内エラーで早期 return したリクエストはこの書き出し箇所に到達しない（CUDA/HIP: `engine/src/program/generate.cpp:22556-22572`、SYCL: `engine/sycl/src/program/generate.cpp:12520-12538`）。各リクエストのループごとに記録バッファと時刻起点は作り直すが、debug 判定と trace path はプロセス内で cache される。

## ログと測定値

この変数による stderr/stdout の有効・無効ログはない。ファイルを開けない場合も Strata は警告しない。出力ファイルに書かれる request 見出しは `# request p0=%lld`、イベント行の書式は上記のとおり（CUDA/HIP: `engine/src/program/generate.cpp:21934-21939,22567-22572`、SYCL: `engine/sycl/src/program/generate.cpp:11907-11912,12533-12538`）。

## 根拠

- env helper と debug gate: `engine/src/program/generate.cpp:681-687`、`engine/sycl/src/program/generate.cpp:325-340`。
- pipeline decode の条件と trace path の cache: `engine/src/program/generate.cpp:13263-13267,21810-21822,21930-21939`、`engine/sycl/src/program/generate.cpp:7712-7717,11783-11796,11903-11912`。
- event の append 出力: `engine/src/program/generate.cpp:22556-22572`、`engine/sycl/src/program/generate.cpp:12520-12538`。

