# `strata-split-N --serve`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N = 2 / 3 / 4） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--serve` は sFNX split engine を Terminal の server が使う常駐 engine として起動するための必須フラグです。parser はこのフラグがある場合だけ起動処理へ進み、モデル・draft layer（または DFlash2）と engine を初期化して、標準入力の要求を読み標準出力へ応答するプロトコルを開始します。ネットワーク待受けをこのフラグ自身が設定する処理はなく、Terminal 側の server が engine 子プロセスを起動して標準入出力を接続します（`engine/src/split/tools/sfnx.cpp:1-20, 73-117, 1137-1161`; `terminal/serve/server.py:827-829`）。

## 使い方

直接 engine プロセスを起動する構文例です。実際にはビルドされた `strata-split-N` と対応するモデル・draft ファイルを指定します。

```sh
strata-split-2 --serve --native MODEL.gguf --mtp RT_DIR --draft-vocab VOCAB.bin
```

Terminal server 経由では server が executable の引数先頭に `--serve` を付けて起動します。通常の split 設定から組み立てる引数にはこのフラグを含めず、親 server が付加します（`terminal/serve/server.py:823-829`; `terminal/strata_control/split_engine.py:267-284`）。

## 値と既定値

- 値・短縮別名はありません。parser は引数トークンが `--serve` と完全一致する場合にフラグを立てます（`engine/src/split/tools/sfnx.cpp:73-85`）。
- 指定しない場合の既定状態は無効です。引数走査後にフラグが立っていなければ `sfnx runs as --serve` を例外として出し、main は stderr に `sfnx: ...` を出力して終了コード `2` を返します（`engine/src/split/tools/sfnx.cpp:75-82, 105-115`）。
- 同じ `--serve` を複数回指定しても、同じ真偽値を再設定するだけです。明示的な重複エラー処理はありません（`engine/src/split/tools/sfnx.cpp:75-82`）。
- 値付きの `--serve=value` は完全一致しないため未知の引数として拒否されます（`engine/src/split/tools/sfnx.cpp:76-82, 105-115`）。

## 実行時の動作

このフラグ自体は値を他の設定へ転送せず、`parse_args` 内の必須起動条件としてのみ使われます。条件を満たすと、MTP 方式では `--native` と `--mtp` が必要です。DFlash2 方式では `--native`、`--draft-model` と `--draft-vocab`、または `--mtp` ディレクトリ内の `draft_vocab.bin` が必要です。これらの不足は `--serve` の有無とは別の parser 検証エラーです（`engine/src/split/tools/sfnx.cpp:108-117`）。

parser を通過すると main はモデルと drafter を読み、engine・server を構築します。初期化に成功すると標準出力に `INFO ...` と `READY <context> stop` を出して、入力 reader と server の処理を開始します。以後は engine 用の行プロトコルで要求を受け付けます（`engine/src/split/tools/sfnx.cpp:1107-1161`; プロトコルの説明は同ファイル `:1-20`）。

## 適用条件と副作用

- この文書の対象は `strata-split-N` の root parser です。CMake 上では sFNX 用 executable が card 数ごとに作られ、split build は opt-in（`STRATA_BUILD_SPLIT=ON`）です。したがって、このバイナリを含まない build には適用されません（`engine/src/split/CMakeLists.txt:1-5, 76-80, 116-122`）。
- `--serve` を付けると単発処理ではなく engine server が起動し、モデル読み込みと engine 初期化を行います。GPU・モデルなどのロードに失敗した場合、main は `ERR <理由>` を標準出力、`sfnx: failed: <理由>` を標準エラーへ出し、終了コード `1` で終了します（`engine/src/split/tools/sfnx.cpp:1094-1102, 1117-1135`）。
- 親 server 経由の場合、engine の stdin/stdout は pipe に接続され、stderr は server log に渡されます（`terminal/serve/server.py:827-829`）。

## 出力とエラー

- `--serve` 不足、未知引数など parser 段階のエラーは stderr の `sfnx: <理由>` と終了コード `2` です（`engine/src/split/tools/sfnx.cpp:105-115, 1113-1115`）。
- parser 通過後の初期化・実行時例外は `ERR <理由>` を標準出力、詳細を `sfnx: failed: ...` として標準エラーへ出し、終了コード `1` になります（`engine/src/split/tools/sfnx.cpp:1094-1102, 1134-1166`）。
- 起動成功時は `INFO engine=sfnx ...` と `READY <context> stop` を標準出力へ出します（`engine/src/split/tools/sfnx.cpp:1155-1158`）。

## 根拠

- `engine/src/split/tools/sfnx.cpp:73-117` — parser 登録、値を取らない処理、必須条件、関連引数の検証。
- `engine/src/split/tools/sfnx.cpp:1094-1102, 1107-1169` — parser・初期化エラーの終了経路、engine/server の起動と成功時出力。
- `engine/src/split/CMakeLists.txt:1-5, 76-80, 116-122` — split engine の build 条件と `strata-split-N` executable。
- `terminal/serve/server.py:823-829` — Terminal server による子プロセス起動時の `--serve` 付加と標準入出力接続。
- `terminal/strata_control/split_engine.py:267-284` — split engine 用引数の組み立て。`--serve` は含めず、親 server 側が付加する。
