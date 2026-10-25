# `--revise-command`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--revise-command` |
| 別名 | なし |
| 値 | 1回の改訂を実行するコマンド文字列 |

## 役割

Time-skip の候補ディレクトリに対して、指定した外部コマンドで改訂処理を1回実行します。Time-skip は改訂後に checks を実行し、根拠に基づいて候補を保持するか判定します。オプションを省略すると改訂処理は呼び出されず、候補のチェック結果は改善を示さないため、最終判定は「改訂なし」の `inconclusive` になります（`strata_cli/cli.py:1572-1585`、`strata_control/time_skip.py:442-459,568-582`）。

## 使い方

```sh
strata timeskip run --workspace ./project --prompt "既存のチェックを通るように改善する" \
  --revise-command 'python revise.py'
```

コマンドは候補ディレクトリを作業ディレクトリとして起動されます。改訂指示と試行番号はそれぞれ `STRATA_TIMESKIP_PROMPT`、`STRATA_TIMESKIP_ATTEMPT` 環境変数で渡されます（`strata_cli/cli.py:359-365,1572-1578`）。

## 値と既定値

- 値は必須のコマンド文字列です。parser は `default=None` で受け付け、文字列自体の形式検証や実行ファイルの事前確認はしません（`strata_cli/cli.py:359-365`）。
- 省略時は `None` となり、改訂 callback は直ちに `None` を返します。`--attempts` の回数分候補のチェック処理自体は行われ得ますが、コマンドによる変更はありません（`strata_cli/cli.py:1572-1574`、`strata_control/time_skip.py:442-459`）。
- 空文字列を明示した場合も偽値として扱われ、コマンドは実行されません。空白だけの文字列は真値なので shell に渡され、実行失敗となる可能性があります（`strata_cli/cli.py:1572-1578`）。
- 値を複数回指定した場合の独自処理はありません。`argparse` の通常の単一値引数として扱われます。

## 実行時の動作

1. `timeskip run` は workspace がディレクトリであることを確認し、`.strata/checks.json` を読み込みます。読み込み不能時はエラーになります。checks がない場合は stderr に警告を出し、改善を自動判定できない実行になります（`strata_cli/cli.py:1557-1568`）。
2. 実行は workspace の内容を baseline として保存し、baseline をチェックしてから開始します。各試行は現在選択中の checkpoint のコピーから候補を作るため、前の試行で不採用となった候補を次の試行の土台にはしません（`strata_control/time_skip.py:408-420,428-448`）。
3. callback はコマンド文字列を `subprocess.run(..., shell=True)` に渡し、`cwd` を候補ディレクトリに設定します。現在の環境変数を引き継いだ上で、prompt と 1 始まりの attempt 番号を上記の環境変数として設定します。標準出力と標準エラーは捕捉され、成功時は標準出力末尾（最大500文字）が試行のメモになります。標準出力はそのまま端末へ表示されません（`strata_cli/cli.py:1572-1585`）。
4. 指定コマンドは「1回の改訂」を行い、workspace を変更しない契約です。ただし CLI が実際に制限するのは作業ディレクトリの設定までで、コマンドが workspace の絶対パス等へアクセスすることは防止しません。shell 経由で実行されるため、信頼できるコマンド文字列だけを指定してください（`strata_cli/cli.py:359-365,1577`）。
5. `--attempts` は別オプションで既定値2です。試行回数を0にすると callback は呼ばれません。改訂コマンドの指定だけでは候補を workspace に適用せず、保持結果を workspace に反映する操作は `strata timeskip apply` です（`strata_cli/cli.py:356-365,1570-1585`、`strata_control/time_skip.py:442-475`）。

## 適用条件と副作用

- コマンド実行による変更先は通常候補ディレクトリですが、外部コマンドが行うファイル操作・ネットワーク通信・子プロセス起動などは CLI が制限しません。指定コマンド自身が行う副作用はその実装に依存します。
- Time-skip は実行状態を state directory に記録し、baseline・候補・checkpoint を保存します。state directory は `--state-dir`、`STRATA_TIMESKIP_DIR`、またはプラットフォーム別既定値で決まります（`strata_cli/cli.py:366-369,1476-1485`、`strata_control/time_skip.py:321-347,408-420`）。
- コマンド実行に timeout は設定されていません。長時間停止するコマンドは run を完了させない可能性があります（`strata_cli/cli.py:1577-1578`）。
- 候補の自動保持は checks の判定に依存します。改訂コマンドが成功しても、チェックが不合格・未評価、または既存の deterministic check に新たな改善がなければ候補の保持を保証しません（`strata_control/time_skip.py:458-472,535-556`）。

## 出力とエラー

- 指定コマンドが終了コード0以外で終了すると `TimeSkipError` になり、run は `failed` として保存されます。エラー本文には終了コードと、標準エラーがあればその末尾300文字、なければ標準出力の末尾300文字が含まれます（`strata_cli/cli.py:1577-1583`、`strata_control/time_skip.py:486-490`）。
- run が `failed` または `interrupted` の場合、JSON 出力では `_error` 経由で終了コード6相当のエラー応答、human 出力でもエラーを返します。それ以外の run は `--output`（既定 `human`、選択肢 `human`/`json`）に応じて結果を出します（`strata_cli/cli.py:369,1585-1602`）。
- 無効な `--attempts` の整数値は argparse が拒否します。負の整数は parser では拒否されず、`TimeSkipRun` が0以上に丸めます（`strata_cli/cli.py:356-358`、`strata_control/time_skip.py:321-330`）。workspace 不正や checks 読み込み失敗は終了コード2相当で、改訂コマンドの起動前にエラーになります（`strata_cli/cli.py:1557-1564`）。

## 根拠

- parser 定義と値の説明: `strata_cli/cli.py:352-369`
- workspace/checks の準備、callback、プロセス実行、出力: `strata_cli/cli.py:1557-1602`
- baseline・候補の作成、試行回数、判定と失敗状態の保存: `strata_control/time_skip.py:321-347,408-490,535-592`
- コマンド階層と索引上の option scope: `docs/cli/README.md`（作成元リポジトリの該当箇所 `strata timeskip run` は `timeskip/run` 配下、`--revise-command` は同コマンドのオプション）

調査は上記 commit のソースに基づきました。CLI help の実行、ビルド、テスト、GPU 実行、性能測定、Release 配布物の照合は行っていません。外部改訂コマンド固有の挙動と副作用は、そのコマンドの実装・実行環境を調査していないため対象外です。
