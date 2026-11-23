# `STRATA_CRASH_BT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux 向けの Strata engine program で、fatal signal 時に native call stack を出力する調査用フック。`engine/src/program/generate.cpp` の translation unit 初期化時に環境を読み、設定に応じて `SIGFPE`、`SIGSEGV`、`SIGBUS`、`SIGABRT` の handler を登録する。モデル処理や生成設定を変えるものではなく、CLI 引数による上書き経路もこの実装にはない。Linux 以外ではこの実装全体がコンパイル対象外である（`engine/src/program/generate.cpp:362-388`）。

## 値と判定

`std::getenv` の結果を文字列全体として parse せず、未設定・空文字・先頭文字を直接判定する。設定値によっては値そのものを出力ファイル名として使う（`engine/src/program/generate.cpp:365,380-385`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux | 無効 | 空でない値で先頭文字が `0` 以外。`1` だけの値は stderr に出力し、それ以外は値を出力先パスとして扱う。例: `1`、`true`、`/tmp/strata-crash.txt` | 空文字、または先頭文字が `0`。例: `0`、`0anything` |
| Linux 以外 | このコードによる読み取りなし | 該当なし | このコードによる効果なし |

値全体の数値・真偽値検証、大文字小文字変換、空白除去はない。したがって `true` は真偽値としてではなくファイルパスとして扱われ、`false` も無効値ではなく同名のパスとして扱われる。` 1` は先頭が空白なのでパス、`1 ` や `10` も値全体が `1` ではないためパスとなる。一方 `01` は先頭が `0` のため無効。パスは `g_crash_path` の 512 byte 配列へ `snprintf` でコピーされ、長い値は配列に収まる範囲に切り詰められる（同 `:365,381-384`）。

## 有効になる条件

- Linux 上で `engine/src/program/generate.cpp` を含む Strata engine program を実行すること。非 Linux では signal handler の定義も読み取りも `__linux__` 条件内にない（`engine/src/program/generate.cpp:362-388`）。
- プロセス初期化時に値が空でなく、先頭文字が `0` でないこと。変数はグローバル初期化 lambda で一度読み取られ、その後の環境変更は反映されない（同 `:380-386`）。
- 対象の四 signal のいずれかが発生し、Strata の登録 handler が呼ばれること（同 `:366-384`）。CLI 引数、モデル状態、GPU backend による有効化条件はこの処理にない。
- `STRATA_CRASH_BT` が `1` 以外の有効文字列なら、その値を出力先パスとして開けること。開けなかった場合も handler は有効なままで、出力先を stderr に戻す（同 `:371-376`）。

## 実行時の詳細

グローバル初期化 lambda が起動時に一度 `STRATA_CRASH_BT` を読み取る。unset・空文字・先頭 `0` なら登録せず終了する。それ以外は、値が厳密に `1` でなければ値を `g_crash_path` に保存し、四つの signal に同じ handler を登録する（`engine/src/program/generate.cpp:365,380-386`）。

handler は最大 48 frame 分を `backtrace` で取得し、`strata: fatal signal, call stack:\n` と `backtrace_symbols_fd` による frame 表示を書き出す。厳密な値 `1` のとき、および指定パスを `open(O_WRONLY | O_CREAT | O_APPEND, 0644)` で開けないときは fd 2（stderr）を使う。パスを開けた場合は追記出力する。出力後は当該 signal の処理を `SIG_DFL` に戻し、同じ signal を `raise` して終了経路を元の signal に委ねる（同 `:366-378`）。

## ログと測定値

有効値で対象 signal が発生すると、選択された出力先に次のヘッダーと最大 48 frame の symbolized address 表示が書かれる。ファイル指定時に open が失敗した場合は stderr に出る。未設定・空文字・先頭 `0` の場合、この handler による出力はない（`engine/src/program/generate.cpp:366-376,380-385`）。

```text
strata: fatal signal, call stack:
```

出力後は同じ signal を再送するため、通常の復帰や継続処理には進まない（同 `:377-378`）。この変数に関する測定値は Strata の資料で確認できなかった。

## 根拠

- Linux 限定の実装、handler の出力・signal 再送、環境値の判定と handler 登録: `engine/src/program/generate.cpp:362-388`
- Linux 用の `execinfo`、`fcntl`、signal、`unistd` の include: `engine/src/program/generate.cpp:154-159`
