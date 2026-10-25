# `--prompt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--prompt` |
| 別名 | なし |
| 値 | 必須の文字列。改訂で達成してほしい内容 |

## 役割

Time-skip run に依頼内容を渡します。run の記録と各改訂 attempt に保存され、`--revise-command` を指定した場合は改訂コマンドの環境変数 `STRATA_TIMESKIP_PROMPT` に渡されます。プロンプトそのものがファイルを変更するのではなく、改訂コマンドが候補ディレクトリで実行する処理を導きます。

## 使い方

```sh
strata timeskip run --workspace "$PWD" \
  --prompt "既存の決定的チェックを保ちながら、入力検証の不足を補う" \
  --revise-command 'your-revision-command'
```

`--workspace` は必須です。実際に改訂を行わせるには `--revise-command` も指定します。

## 値と既定値

値は `argparse` の通常の文字列引数で、必須です。空文字列かどうか、長さ、書式、文字種に対する CLI 側の検証・正規化はありません。シェルから複数語を一つの値として渡す場合は引用符で囲みます。既定値および短縮別名はありません。 (parser: `strata_cli/cli.py:352-369`)

## 実行時の動作

- `_timeskip` は受け取った値を `TimeSkipRun` にそのまま渡します。run の永続記録 `run.json` の `prompt` フィールドと、attempt ごとの `prompt` フィールドに保存されます。 (`strata_cli/cli.py:1570`; `strata_control/time_skip.py:321-329,349-367,442-450`)
- `--revise-command` があると、各 attempt で Strata はそのコマンドを `shell=True` で候補ディレクトリを作業ディレクトリとして起動し、環境変数 `STRATA_TIMESKIP_PROMPT` に prompt を設定します。同じ子プロセスには `STRATA_TIMESKIP_ATTEMPT` で attempt 番号も渡ります。コマンドの stdout/stderr は捕捉され、成功時の stdout の末尾（最大500文字）が attempt の記録理由として使われる場合があります。 (`strata_cli/cli.py:1572-1584`)
- `--revise-command` を省略すると改訂コマンドは起動されません。parser の説明は「改訂なし」としていますが、`--attempts` が正なら状態機械は各 attempt の候補作成・チェックに進み、callback は `None` を返します。`--attempts 0` なら改訂ループは実行されません。 (`strata_cli/cli.py:356-365,1572-1585`; `strata_control/time_skip.py:442-461`)
- `strata timeskip status` は prompt を表示し、`strata timeskip list` は各 run の prompt の先頭48文字を表示します。JSON 出力では run データに prompt が含まれます。内容はローカルの run 状態ファイルに平文で保存されるため、秘密情報を含めないでください。 (`strata_cli/cli.py:1487-1498,1500-1512,1585-1589`; `strata_control/time_skip.py:349-367`)

## 適用条件と副作用

オプションは `timeskip run` のみで有効です。各 attempt に渡される値は同じで、attempt ごとの変化は別環境変数の番号で示されます。prompt による改訂・候補内容の変更は `--revise-command` の実装次第です。Strata は子プロセスを候補ディレクトリで起動します。実行コマンドは shell を介して呼ばれ、Strata 側で prompt をコマンド文字列へ展開するのではなく環境変数として渡します。 (`strata_cli/cli.py:1572-1584`; `strata_control/time_skip.py:442-450`)

CLI 自体は空文字列を拒否しません。ただし、同梱 Harness 例 `integrations/harness/revise_once.py` は環境変数を strip した後に空ならエラー終了するため、この特定の改訂コマンドでは空 prompt は利用できません。 (`integrations/harness/revise_once.py:84-89`)

## 出力とエラー

`--prompt` 単独に固有の成功メッセージや検証エラーはありません。オプションの欠落や値の欠落は `argparse` が通常の引数エラーとして扱います。run の通常出力は結果の状態・attempt・decision と status/apply の案内で、JSON モードは run オブジェクトを出力します。改訂コマンドが非ゼロ終了すると run は失敗として記録され、CLI は終了コード6のエラーを返します。 (`strata_cli/cli.py:1577-1588,1590-1602`; `strata_control/time_skip.py:486-490`)

## 根拠

- parser と `--prompt` の必須指定: `strata_cli/cli.py:348-369`
- run 作成時の値の受け渡し、workspace 検査、checks 読込、改訂 command の起動: `strata_cli/cli.py:1557-1585`
- prompt の永続化と attempt への引き渡し: `strata_control/time_skip.py:321-367,422-450`
- Harness 改訂コマンドが空 prompt を拒否する例: `integrations/harness/revise_once.py:84-89`
- 索引上のコマンド階層と予定リンク: `docs/cli/README.md:680-690`

調査範囲は上記 checkout のソースです。CLI の help 実行や Release 配布物との照合は行っていません。子プロセスが prompt をどう解釈するかは指定された `--revise-command` に依存するため、特定の agent や外部 Harness の動作一般はここでは断定していません。
