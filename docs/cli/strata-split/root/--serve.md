# `strata-split-N --serve`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N はビルド対象のカード数） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`sFNX` の分割推論エンジンを、標準入力・標準出力の行プロトコルを処理する常駐エンジンとして起動するための必須フラグです。`--serve` が無ければ処理を開始せずエラーになります。HTTP listener を開く処理ではありません。エンジン側は token ID の行プロトコルを扱い、通常は Strata の `serve/server.py` が子プロセスとして起動し、pipe で接続します（`src/split/tools/sfnx.cpp:1-20,100-101`、`serve/server.py:1055-1061,1152-1154`）。

## 使い方

```sh
strata-split-2 --serve --native /models/model.gguf --mtp /models/mtp --draft-vocab ./data/draft_vocab_en.bin
```

これは引数の形を示す例です。ファイルの存在やモデルとビルドの適合性は別途必要です。`N` は実際に利用するビルド済み executable 名に置き換えます。Strata のサーバー経由では、起動側が executable の引数の先頭に `--serve` を付加します（`serve/server.py:1152-1154`）。

## 値と既定値

値は不要です。parser は引数を左から走査し、文字列が `--serve` と一致すれば真偽値を true にします。既定は false で、複数回指定しても true のままです（`src/split/tools/sfnx.cpp:72-82`）。`--serve` に値を渡す構文はなく、たとえば `--serve=true` は未知の引数として拒否されます（同 `:75-80,97-98`）。短縮 alias や help option はこの parser に定義されていません（同 `:75-98`）。

## 実行時の動作

parser は `--serve` を受理条件として記録します。フラグがない場合は `sfnx runs as --serve` で停止し、ある場合は続けて `--native` と `--mtp` が指定されていること、`--batch` が `1..MAX_SLOTS` に入ること、rope scale が有効であることを検査します（`src/split/tools/sfnx.cpp:74-104`）。`--serve` 自体は値の変換やモデル設定を行いません。

起動後、モデルと MTP を読み込み、エンジンを構築して `INFO engine=sfnx ...` と `READY <context> stop` を標準出力へ出し、標準入力を読む thread と行プロトコル処理を開始します（`src/split/tools/sfnx.cpp:1040-1087`）。プロトコルの例は `GEN` / `T` / `DONE` と `STOP` で、複数 slot 用には `BGEN` 系の行もあります（同 `:7-20`）。HTTP 接続や port の指定はこのフラグからは行われません。

## 適用条件と副作用

`--serve` を指定しても単体でエンジンが起動できるわけではなく、必須の `--native`・`--mtp`、モデル等のロード条件が満たされる必要があります（`src/split/tools/sfnx.cpp:100-104,1051-1061`）。製品側のサーバーは `[exe, "--serve", *args]` を子プロセスとして起動し、stdin/stdout を pipe に接続します（`serve/server.py:1152-1154`）。分割 engine のビルドは Linux の CUDA または HIP 条件などに限定され、CMake option `STRATA_BUILD_SPLIT` は既定 OFF です（`src/split/CMakeLists.txt:1-5,20-30,92-97`）。

## 出力とエラー

`--serve` が無い場合、または parser が不正・未知の引数を受け取った場合は、`sfnx: <理由>` を標準エラーに出し、終了コード 2 で戻ります（`src/split/tools/sfnx.cpp:97-104,1040-1049`）。引数検査を通過してモデル読み込み後に初期化・実行エラーが起きると、`ERR <理由>` を標準出力、`sfnx: failed: <理由>` を標準エラーに出して終了コード 1 になります（同 `:1027-1036,1051-1061,1084-1092`）。正常な初期化時は `INFO` と `READY` を標準出力へ出します（同 `:1081-1084`）。

## 根拠

- parser、既定値、値なしの処理、未知引数、必須条件: `src/split/tools/sfnx.cpp:65-104`
- 行プロトコルの説明: `src/split/tools/sfnx.cpp:1-20`
- モデル初期化、`INFO` / `READY` 出力、プロトコル処理、終了処理: `src/split/tools/sfnx.cpp:1027-1095`
- サーバーが `--serve` を付け、stdio pipe で子プロセスを起動する箇所: `serve/server.py:1055-1061,1152-1154`
- split engine の build 条件と executable target: `src/split/CMakeLists.txt:1-5,20-30,92-97`
