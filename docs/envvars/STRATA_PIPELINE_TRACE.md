# `STRATA_PIPELINE_TRACE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` の pipelined decode ループで発生するイベントを、経過時間付きでファイルに追記する診断用フックです。生成やスケジューリングを制御する値ではなく、CUDA 実装と SYCL 実装にあります。通常利用者向けの設定として説明されている資料は見つからず、`STRATA_PIPELINE_DEBUG` で明示的に有効化する開発・診断用の出力です。

## 値と判定

この変数自体は文字列を parse しません。`pipe_dbg_env("STRATA_PIPELINE_TRACE")` が返すポインターが null かどうかだけを見ます。

| `STRATA_PIPELINE_DEBUG` | `STRATA_PIPELINE_TRACE` | 結果 |
|---|---|---|
| 無効 | 任意 | helper が null を返すため trace は無効 |
| 有効 | 未設定 | null のため trace は無効 |
| 有効 | 空文字を含む設定値 | 非 null なので trace バッファを作る。書き出し時に空のパスを `fopen` に渡し、開けない場合はエラー表示なしで出力されない |
| 有効 | その他の設定値 | 文字列全体をファイルパスとして使う。`1` など特定値は要求されない |

helper は `STRATA_PIPELINE_DEBUG` の先頭文字だけを確認し、未設定・空文字・先頭文字が `0` の値を無効、それ以外を有効とします。したがって `false` も有効です。この判定は helper 内の `static const bool` に保存されます。trace パスもパイプラインループ内の `static const char*` に保存されるため、各リクエストで環境を再読込する設定ではありません。

根拠: `src/program/generate.cpp:340-345,14170-14179`、`sycl/src/program/generate.cpp:296-300,10882-10891`。

## 有効になる条件

`STRATA_PIPELINE_DEBUG` とパスが有効でも、trace を記録するのは pipelined decode ループが実際に動く場合だけです。コード上の条件は `pipe && pl_pw >= 2 && pl_snap_ok` を満たし、直列実行へ切り替える理由がなく、キャンセルされておらず、生成上限にも達していないことです。この経路は `--serve` の layer-split pipeline の decode です。条件を満たさないリクエストでは trace ファイルに記録しません。

根拠: `src/program/generate.cpp:14067-14090`。SYCL にも同じ条件の分岐があります: `sycl/src/program/generate.cpp:10754-10888`。

## 実行時の詳細

ループ内の `tre()` 呼び出しごとに、ループ開始からの経過ミリ秒（小数点以下3桁）、イベント名、`seq`、`x0`、`x1` を1行のテキストにバッファします。コード上のイベント名には `F0`、`F1`、`U`、`CD`、`CE`、`L0`、`L1`、`V`、`CL` があります。`x0` と `x1` の意味はイベント呼び出し箇所ごとに異なります。

リクエストの pipeline drain 後、パスを `fopen(path, "a")` で開き、`# request p0=<値>` のヘッダーとイベントバッファを追記して閉じます。既存ファイルは上書きされません。ファイルを開けない場合は何も書かず、警告やエラーを出しません。`fwrite` の戻り値も検査されません。環境変数の値はあくまで出力先で、子プロセスへの転送処理はこの実装にはありません。

根拠: CUDA のイベント記録 `src/program/generate.cpp:14170-14179,14194,14336,14388,14412,14441,14490,14508,14544,14556,14598,14629` と追記処理 `14672-14689`。SYCL の対応箇所は `sycl/src/program/generate.cpp:10882-10891,10905,11085,11129,11157,11186,11235,11249,11283,11295,11334,11359,11394-11409`。

## 根拠と資料の照合

`docs/DETAILS.md` と `docs/MULTI_GPU.md` に `STRATA_PIPELINE_TRACE` の説明はありません。`docs/MULTI_GPU.md` は `--pipeline-windows` の機能自体を扱いますが、trace 環境変数の有効化条件・出力形式・失敗時の挙動はソースで確認した範囲のみ記載しました。測定値はありません。
