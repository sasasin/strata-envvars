# `strata components rollback --feed`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | URL またはフォルダーを表す文字列。parser は型・形式を検証しない |

## 役割

このコマンドは、コンポーネント状態に記録された前回のエンジンへ切り替える。`--feed` は共通引数として受理されるが、rollback の実行経路では値を参照せず、フィードの取得にも使用しない。したがって、feed の指定は rollback の対象や動作を変えない。

## 使い方

```sh
strata components rollback --feed https://updates.example.invalid/
```

この例の `--feed` 値は parser に受理されるだけで、rollback 処理には使われない。rollback はローカルのコンポーネント状態を使う。

## 値と既定値

`--feed` は文字列値を一つ受け取る。共通 parser の定義には `choices`、型変換、必須指定がなく、既定値は `None`。空文字列も parser では拒否されない。複数回指定した場合の argparse の標準的な最終値への集約はライブラリ側の挙動であり、この調査では実行確認していない。

rollback 分岐は `ctx.source` を空文字列で初期化し、`_feed_source()` を呼ばない。そのため値が指定されていても、フィード URL/フォルダーとして検証・利用されず、ネットワークアクセスの契機にもならない。

## 実行時の動作

`strata_cli/update_cmd.py` の `_common()` が rollback parser にも `--feed` を登録する。一方 `run()` は rollback を識別すると、待機処理の後に `updater.rollback_engine(ctx)` を呼び、その結果を出力して終了する。この分岐は通常の update 経路にある `_feed_source(a, root)` より前にあるため、明示した `--feed`、`STRATA_UPDATE_FEED`、保存済み feed source のいずれも rollback では使われない。

rollback は状態ファイルから `engine.previous` を読み、対応するローカルエンジンの manifest と全ファイルを検証し、必要なら serving 中エンジンの終了待ちを行って切り替える。したがって `--feed` の指定で別の feed からエンジンを取得したり、切替先を選んだりすることはない。

## 適用条件と副作用

`--feed` 自体による通信・ファイル操作はない。rollback の本体は前回エンジンが記録されていることを要求し、ローカルのパッケージ検証を行う。切替時は state の pin、previous/active/skipped 情報や履歴を更新し、エンジン変更に応じて保存 tuning preset に再確認マークを付ける場合がある。ダウンロードや旧エンジンの削除は rollback 処理の説明・実装にはない。

## 出力とエラー

成功時の human 出力は切替方向・バージョン、tuning preset の扱い、次の操作案内を表示する。`--output json` または `jsonl` では共通出力設定に従い JSON 結果を表示する。`--feed` の値による出力差はない。

前回エンジンがない、すでに前回エンジンが有効、または既存エンジンが現在の PC で使えない場合は `UpdateError` となる。前二者は終了コード 2、検証・適合エラーはコード 5 として stderr（machine output 時は JSON error）へ出力される。待機中の失敗など、ここに列挙していない個別経路の詳細は本オプション文書の調査範囲外。

## 根拠

- `strata_cli/update_cmd.py:47-56` — `_common()` による `--feed` の登録、既定値と型指定なし。
- `strata_cli/update_cmd.py:80-82` — `rollback` parser に共通引数を登録。
- `strata_cli/update_cmd.py:138-147` — feed の優先順位（明示値、環境変数、記録値、既定値）。
- `strata_cli/update_cmd.py:310-321` — rollback 用 context の初期化と rollback 分岐。`_feed_source()` より前に rollback を処理する。
- `strata_cli/update_cmd.py:345-348` — feed source を解決するのは rollback 分岐を抜けた通常 update 経路。
- `strata_cli/update_cmd.py:322-331,368-380` — 成功出力、失敗の出力形式・終了コードの伝播。
- `strata_control/updater.py:1450-1472` — rollback のローカル state 参照、検証、切替と失敗条件。
- `strata_control/updater.py:1398-1447` — 切替時の state 更新、preset マーク、履歴記録。
