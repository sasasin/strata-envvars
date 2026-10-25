# `strata timeskip run`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip run` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/time_skip.py` |

## 役割

作業ディレクトリの現状を baseline として保存し、宣言済みチェックで評価したうえで、任意の revision command を隔離候補ごとに最大回数まで実行します。候補はチェック結果と保持済み状態に照らして判断されます。run は結果を記録しますが、候補を workspace に反映しません。反映・復元は別コマンド `strata timeskip apply` で、内容を確認してから行います。サブコマンドの説明も「checkpoint、revision、check、decision」の順を示しています（`strata_cli/cli.py:348-352`）。

## 使い方

```sh
# workspace に .strata/checks.json を用意して実行
strata timeskip run --workspace "$PWD" --prompt "make the failing test pass" \
  --attempts 2 --revise-command "<revision command>"

# baseline のチェックと checkpoint だけを行う
strata timeskip run --workspace "$PWD" --prompt "改善目標" --attempts 0
```

`--revise-command` を省略すると revision は行われず、結果は改善を示せないため inconclusive になります。run の後は表示された run ID を使って `strata timeskip status <run-id>` で記録を確認し、`strata timeskip apply <run-id> --dry-run` で適用差分を確認できます。実際の適用は明示的な apply が必要です（`strata_cli/cli.py:359-365,1570-1585,1590-1605`）。

オプションの個別仕様は [`docs/cli/README.md`](../../../README.md) の `strata timeskip run` 節にある [`--attempts`](--attempts.md)、[`--prompt`](--prompt.md)、[`--revise-command`](--revise-command.md)、[`--state-dir`](--state-dir.md)、[`--workspace`](--workspace.md)、[`--output`](--output.md) を参照してください。

## 実行モードと主な動作

1. CLI は `--workspace` と `--prompt` を必須として受け取り、`--attempts` は整数（既定値 2）、`--revise-command` は任意、`--output` は `human` または `json`（既定値 `human`）です（`strata_cli/cli.py:352-369`）。
2. workspace がディレクトリであることを確認し、任意の `.strata/checks.json` を読み込みます。ファイルがなければチェックなしとして続行し、stderr に inconclusive になる旨を警告します。不正な形式などの読み込み失敗はエラーです（`strata_cli/cli.py:1557-1568`、`strata_control/time_skip.py:718-731`）。
3. run ごとに記録領域を作り、workspace の baseline を checkpoint として複製します。チェックは baseline と各候補で実行され、revision ごとに選択中の checkpoint から候補ディレクトリを作ります。候補が保持されても workspace には書き戻しません（`strata_control/time_skip.py:321-335,422-460`）。
4. 最大 `--attempts` 回の試行を行います。チェック結果が不足・不明確な場合は自動的な改善と断定せず、確認を求める結果になり得ます。revision command がない場合も改善を捏造しません（`strata_cli/cli.py:359-365`、`strata_control/time_skip.py:442-475`）。
5. run の記録には状態、チェック、attempt、判断が保存されます。既定の保存先は `--state-dir`、`STRATA_TIMESKIP_DIR`、またはユーザー状態ディレクトリ配下の `strata/time-skip`（Windows は `%LOCALAPPDATA%\Strata\time-skip`）の順です（`strata_cli/cli.py:1476-1485`、`strata_control/paths.py:13-21`）。

## 主な副作用と注意点

- baseline、candidate、run の JSON 記録などを state directory に作成します。workspace は run による候補適用先ではありませんが、チェック command は workspace のコピー上で実行され、revision command は candidate directory を cwd として実行されます（`strata_control/time_skip.py:422-460`、`strata_control/time_skip.py:718-731`）。
- revision command は `subprocess.run(..., shell=True)` で起動され、親プロセスの環境に `STRATA_TIMESKIP_PROMPT` と `STRATA_TIMESKIP_ATTEMPT` を加えて渡します。任意のシェルコマンドを実行するため、そのコマンド自身の外部副作用は CLI が制限しません。「workspace に触れない」は parser help と実装上の契約であり、OS レベルの隔離を意味しません（`strata_cli/cli.py:359-365,1572-1583`）。
- `.strata/checks.json` の各 check は `command` または `file` が必要です。`kind` は `deterministic` または `advice`、既定は deterministic です。command の既定 timeout は 300 秒で、未実行・timeout のチェックは `unknown` として保持されます（`strata_control/time_skip.py:67-102,718-731`）。
- workspace が存在しない、checks の読込に失敗する場合は終了コード 2 のエラー経路です。実行中の例外で run が `failed` / `interrupted` になると終了コード 6 で報告します。人間向け出力は run ID、state、attempt の判断、decision、確認用の status/apply preview を表示し、JSON 出力は機械可読な結果を返します（`strata_cli/cli.py:1557-1568,1585-1605`）。
- このコマンドの説明・利用例は調査対象リポジトリの `docs/work/QUALIFICATION-KIT.md:223-243` にもあります。CLI の関連コマンド階層は [索引](../../../README.md) を参照してください。

## 根拠

- `strata_cli/cli.py:348-369` — timeskip/run の登録と引数。
- `strata_cli/cli.py:1467-1485,1557-1605` — state 保存先、入力検証、revision command 起動、結果出力。
- `strata_control/time_skip.py:67-102,313-335,422-490,718-731` — check 定義、run の状態遷移・checkpoint と candidate、checks の読込。
- `strata_control/paths.py:13-21` — POSIX / Windows の状態ディレクトリ基点。
- `docs/work/QUALIFICATION-KIT.md:223-243` — 利用例と `.strata/checks.json` の例。

調査は上記 commit のソースとリポジトリ内文書に基づきます。CLI `--help` は実行せず、実行時の Release 配布物や各 OS での実動作はこの調査では確認していません。
