# `--engine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--engine` |
| 別名 | なし |
| 値 | `strata` または `mock` |

## 役割

serve が使う推論エンジンの種類を選ぶ。`strata` は run config に記録された実エンジンを使う通常の選択で、既定値でもある。`mock` は scripted な応答を返す MockEngine を選び、CLI の help ではクライアントテスト用、GPU とモデルを使わない選択肢として説明されている（`strata_cli/cli.py:46-50`）。

このオプションの値は実行ファイル名・パスではない。実エンジンの場所は必須の `--profile`（別名 `--config`）で指定する run config から得られる（`strata_cli/cli.py:47-50`、`strata_cli/cli.py:782-825`）。

## 使い方

```sh
strata serve --profile ./run.json --engine mock
```

`--profile` は必須。省略すると `strata serve` 自体の parser が引数エラーにする（`strata_cli/cli.py:46-50`）。mock のサーバーも通常どおり foreground で起動するため、この例は HTTP サーバーを実際に起動する。起動せずに plan を確認する場合は `--plan` を加える。

## 値と既定値

- `strata`: 既定値。run config の `exe` と `args` を使って StrataEngine を起動する。
- `mock`: MockEngine を起動し、Terminal CLI からは script を指定しないため、既定の短い挨拶を返す。
- 大文字小文字を含め、受理値は parser の choices にある `strata` と `mock` のみ。別の値や空文字は argparse の引数エラーとなる。短縮 alias はない（`strata_cli/cli.py:48-50`）。同じ `--engine` を複数指定した場合は argparse が後に解析した値を採用する。

## 実行時の動作

Terminal CLI は `_launch_plan` で `--engine <選択値>` を server の引数列に加えてから foreground server を呼ぶ（`strata_cli/cli.py:782-826`、`strata_cli/cli.py:915-955`）。server 側も `--engine` の値を `mock` / `strata` に限定している（`serve/server.py:8139-8142`）。

- `strata` の場合、設定の component engine 参照を実行ファイルへ解決し、設定から組み立てた引数・環境で `StrataEngine` を起動する。複数 GPU の replica 設定があれば replica engine の起動経路を使う（`serve/server.py:8343-8357`、`serve/server.py:8394-8424`）。
- `mock` の場合、`MockEngine` を作り、Terminal CLI から script 引数を渡さないため組み込み応答を使う。実エンジン起動処理（`StrataEngine` / replica 起動）は通らない（`strata_cli/cli.py:794-825`、`serve/server.py:8425-8430`）。server module 自体には `--script` parser 引数があるが、`strata serve` の parser にはなく、この CLI からは指定できない（`strata_cli/cli.py:46-67`、`serve/server.py:8146-8155`）。
- `strata serve` の `--profile` は両選択肢で必須で、Terminal CLI は config を読み、launch plan と engine 引数も組み立てる。したがって `mock` でも profile/run config の参照は必要であり、設定ファイルを一切読まない単独モック起動を意味しない（`strata_cli/cli.py:47-50`、`strata_cli/cli.py:545-547`、`strata_cli/cli.py:782-826`）。server は設定に tokenizer があればそのパスを使い、MCP や API などの共通設定も処理する（`serve/server.py:8241-8245`、`serve/server.py:8309-8329`、`serve/server.py:8447-8450`、`serve/server.py:8608-8615`）。

## 適用条件と副作用

`strata` は設定済み engine、モデル、tokenizer および環境に依存し、設定された GPU/CPU 実行経路を起動する。`mock` は設定された inference engine/model を起動せず MockEngine を使うが、HTTP server は bind して稼働する。mock 選択でも共通の config / launch plan 処理は行われる。どちらも `strata serve` の foreground 実行であり、通常は停止するまでプロセスが継続する（`strata_cli/cli.py:782-826`、`strata_cli/cli.py:900-955`、`serve/server.py:8425-8430`、`serve/server.py:8615-8623`）。

## 出力とエラー

- 未対応値は `argparse` が usage とエラーを stderr に出し、終了コード `2` で拒否する。Terminal CLI 側の parser 宣言は `strata_cli/cli.py:48-50`。
- `strata` 選択時に tokenizer が見つからない場合、server parser の `error` で起動が拒否される（`serve/server.py:8313-8315`）。実エンジンの設定や起動失敗も startup failure 経路となる。
- `--output jsonl` を指定した場合、Terminal CLI は foreground 起動中の失敗を `failed` JSONL event と終了コードで出力する。`--output json` は `--plan` と併用する必要があり、foreground 起動には使えない（`strata_cli/cli.py:829-835`、`strata_cli/cli.py:915-955`）。

## 根拠

- `strata_cli/cli.py:46-50` — `serve` parser、必須 profile、engine の選択肢と既定値。
- `strata_cli/cli.py:782-826` — 設定読み込み、server 引数の生成、engine 引数を含む plan。
- `strata_cli/cli.py:915-955` — serve の検証、plan/foreground 分岐と server 呼び出し。
- `serve/server.py:8139-8142` — 内部 server parser の engine choices。
- `serve/server.py:8241-8245`, `serve/server.py:8309-8329` — config と tokenizer の読込。
- `serve/server.py:8343-8357`, `serve/server.py:8394-8430` — strata 実 engine 起動と mock engine 選択。
- `serve/server.py:8608-8623` — 共通 MCP 起動と HTTP server の bind / ready 出力。

確認範囲は上記 commit の Terminal CLI と `serve/server.py` の実装。GPU/backend ごとの実エンジン動作や Release 配布物は実行・照合していない。
