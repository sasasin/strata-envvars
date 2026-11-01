# `STRATA_CRASH_BT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Linux 版 `strata` 実行ファイルで、指定された致命的シグナルを受けたときに backtrace を出力する診断用設定です。値が有効だと `SIGFPE`、`SIGSEGV`、`SIGBUS`、`SIGABRT` のハンドラを登録します。通常実行時のログや計算処理は変えません。`strata` の実行ファイルは `src/program/generate.cpp` から作られます（`CMakeLists.txt:868-871`）。

## 値と判定

`src/program/generate.cpp:268-274` の初期化処理は環境変数を文字列として読みます。整数変換や CLI 引数との優先順位はありません。

| 環境値 | 判定と出力先 |
|---|---|
| 未設定 | 無効。ハンドラを登録しない |
| 空文字 | 無効。ハンドラを登録しない |
| 先頭文字が `0` | 無効。`0`, `0anything` など |
| 値が厳密に `1` | 有効。致命的シグナル時の出力先は標準エラー（fd 2） |
| 先頭文字が `1` で、値が厳密な `1` ではない | 有効。値全体を出力ファイルのパスとして保存する。例: `1/tmp/crash.log` は `/tmp/crash.log` ではなく `1/tmp/crash.log` というパス |
| 上記以外 | 無効。例: `true`, `2`, ` 1` |

出力先パスは 512 バイトのバッファに `snprintf` で格納されるため、終端 NUL を含めて最大 511 バイトが残ります。空白除去、大文字小文字変換、数値 parse はありません（`src/program/generate.cpp:253,268-272`）。

## 有効になる条件

- `#if defined(__linux__)` のコードに限られ、Linux 以外のビルドではこの環境変数を読む処理もハンドラ登録もありません（`src/program/generate.cpp:250-276`）。
- GPU backend、CLI オプション、モデル状態、他の環境変数による追加条件は、この実装にはありません。
- 値は `generate.cpp` の名前空間スコープ初期化で一度読みます。初期化後にプロセス環境を書き換えても再評価されません（`src/program/generate.cpp:268-274`）。

## 実行時の詳細

有効時に登録されるハンドラは、最大 48 フレームを `backtrace` で取得し、`strata: fatal signal, call stack:\n` とシンボル情報を出力します。値が厳密な `1` なら標準エラーへ直接出します。それ以外の有効値では、その値をパスとして `O_WRONLY | O_CREAT | O_APPEND` で開きます。ファイルを開けた場合はそのファイルへ追記し、開けなかった場合は標準エラーへ出力します（`src/program/generate.cpp:254-264`）。

出力処理後は該当シグナルのハンドラを既定値に戻し、同じシグナルを再送出します。そのため、バックトレース出力の後に元の致命的シグナルによるプロセス終了が続きます。対象は上記 4 シグナルであり、その他の終了原因を処理するものではありません（`src/program/generate.cpp:265-266,272`）。通常時にこの設定を知らせるログはありません。

候補名の全参照を確認すると、値を実際に読む箇所は `src/program/generate.cpp:269` のみです。`tools/par/variants/*.txt` と `tools/par/co_bt.sh`、`tools/par/host_seq.sh` には実験実行用の代入がありますが、これらは値の利用方法を定義する実装ではありません。

## 根拠

- Linux 専用のハンドラ、読み取り、値判定、シグナル登録: `src/program/generate.cpp:250-276`
- `strata` 実行ファイルへの組み込み: `CMakeLists.txt:868-871`
- 候補名の実際の読み取り箇所は 1 箇所のみ。他の一致は `tools/par/variants/` の実験設定および `tools/par/*.sh` の環境値設定。
