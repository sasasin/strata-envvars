# `--workspace`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| オプション | `--workspace` |
| 別名 | なし |
| 値 | 作業ディレクトリのパス（必須） |

## 役割

Time-skip run が基準版を読み取ってチェックし、候補作成の入力元とするディレクトリを指定する。`--workspace` は `run` 専用 parser の必須引数であり、`strata timeskip apply` の同名オプションとは別スコープである。後者は適用先を上書き指定する（`strata_cli/cli.py:352-354,380-384`）。

## 使い方

```sh
strata timeskip run --workspace ./my-project --prompt "設定画面の入力検証を改善する"
```

## 値と既定値

- 値は `argparse` が受け取る文字列で、既定値はなく省略できない。存在確認、絶対パス化、正規化などの追加 parser validation はない（`strata_cli/cli.py:352-355`）。
- 実行時に `Path(value).is_dir()` を確認する。相対パスはプロセスの作業ディレクトリ基準で解決される。ディレクトリでない場合（存在しないパスや通常ファイルなど）は `workspace is not a directory: <path>` を出して終了コード 2 となる（`strata_cli/cli.py:1557-1560`）。
- 空文字列を明示した場合、Python の `Path("")` は現在ディレクトリを指し、それがディレクトリなら受理される。文字列の空チェックは実装されていない（`strata_cli/cli.py:1558-1560`）。

## 実行時の動作

1. 指定ディレクトリの `.strata/checks.json` を読み、チェック定義を得る。ファイルがなければチェックなしとして続行し、stderr に警告を出す。JSON 読み込み、形式検証などで `TimeSkipError`、`ValueError`、`OSError` が起きると、エラーを表示して終了コード 2（JSON 出力時は JSON 形式）となる（`strata_cli/cli.py:1561-1568`、`strata_control/time_skip.py:718-731`）。
2. workspace 全体を run の `baseline` にコピーし、さらに checkpoint として保存する。チェックはこの基準版に対して実行され、各候補は選択中 checkpoint から分離コピーされる。通常の run 処理は指定 workspace を直接編集せず、候補と記録を状態ディレクトリ側に作る（`strata_control/time_skip.py:422-448`）。
3. チェックポイントのコピーと inventory では `.git`、`__pycache__`、`.strata` ディレクトリを除外し、シンボリックリンクのファイルもコピー・inventory 対象から除く。このため `.strata/checks.json` はチェック定義として読み込まれる一方、workspace snapshot には含まれない（`strata_control/time_skip.py:241-260,271-284`）。
4. run の記録には `str(workspace)` が保存されるが、`Path.resolve()` は呼ばれない。相対パスを使った記録を後日別の作業ディレクトリから適用すると、保存された相対パスがその時点の cwd 基準として解釈され得る。後続の `apply` では `--workspace` を指定して適用先を明示できる（`strata_control/time_skip.py:321-327,349-367`、`strata_cli/cli.py:1524-1538`）。

## 適用条件と副作用

- workspace は既存ディレクトリである必要がある。`.strata/checks.json` は任意だが、チェックがない run は基準版を保存した後に「判定不能」となる旨を警告し、改善を主張しない（`strata_cli/cli.py:1558-1568`）。
- workspace は run 中に読み取られ、その内容のコピーが状態ディレクトリへ保存されるため、サイズに応じた読み取り・ディスク使用が発生する。シンボリックリンクおよび上記の除外ディレクトリはコピー対象外（`strata_control/time_skip.py:271-284,429-438`）。
- `--revise-command` が指定されると、そのコマンドは候補ディレクトリを cwd として実行され、prompt と試行番号が環境変数 `STRATA_TIMESKIP_PROMPT`、`STRATA_TIMESKIP_ATTEMPT` で渡る。実装上、コマンドは workspace を変更しない前提だが、CLI の subprocess 実行は shell command であり workspace 外へのアクセスを隔離する処理は確認できない（`strata_cli/cli.py:359-365,1572-1583`、`strata_control/time_skip.py:422-448`）。
- 選んだ結果を workspace に反映するのは別コマンド `strata timeskip apply`。適用時は基準版との差分で現在の宛先を照合し、変更があれば上書きを拒否する。適用失敗時は rollback copy から復元を試みる（`strata_control/time_skip.py:597-652`）。

## 出力とエラー

- workspace 不正、checks 読み込み失敗は終了コード 2。
- run 自体が `failed` または `interrupted` になった場合、human 出力では run ID と状態などを表示した後、エラーを stderr に出して終了コード 6。JSON 出力ではエラー JSON で終了コード 6。それ以外の終了状態は通常終了コード 0（`strata_cli/cli.py:1585-1604`）。
- 正常な human 出力には run ID と状態、各 attempt の判定、decision があればその結果、status 確認コマンドと `apply --dry-run` のプレビュー例が含まれる（`strata_cli/cli.py:1590-1604`）。

## 根拠

- parser と必須値: `strata_cli/cli.py:352-355`
- workspace 検査、checks 読み込み、警告、run の初期化: `strata_cli/cli.py:1557-1570`
- 基準版・候補のコピーと分離実行: `strata_control/time_skip.py:271-284,408-448`
- inventory とコピーの除外対象: `strata_control/time_skip.py:241-260,271-284`
- run 記録への workspace 保存: `strata_control/time_skip.py:321-327,349-367`
- apply の宛先競合検査と rollback: `strata_control/time_skip.py:597-652`
- 出力と run 失敗時の終了コード: `strata_cli/cli.py:1585-1604`
