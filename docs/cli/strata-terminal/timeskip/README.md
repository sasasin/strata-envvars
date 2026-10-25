# `strata timeskip`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip` とそのサブコマンド |
| 主な実装 | `strata_cli/cli.py`、`strata_control/time_skip.py` |

## 役割

作業ディレクトリの現状をチェックポイントとして保存し、隔離した候補コピー上で上限付きの改訂を試し、宣言済みチェックの結果を記録するコマンド群です。チェックの証拠から候補を保持するか判断します。候補を実際の作業ディレクトリへ書き戻す操作は、`apply` を明示的に実行するまで行いません（`strata_control/time_skip.py:408-419,422-474,597-607`）。

このコマンドは `run`、`status`、`list`、`apply` のサブコマンドを持ちます。`strata timeskip` だけではサブコマンドが必要です（`strata_cli/cli.py:348-393`）。各サブコマンドのオプションは [CLI 索引の `strata timeskip` 節](../../README.md) を参照してください。

## 基本的な使い方

```sh
# 作業ディレクトリを基準に改訂を試す。REVISION_COMMAND は利用者が用意した
# 1回分の改訂コマンドを指す（下記の「run の実行条件」参照）。
strata timeskip run --workspace "$PWD" --prompt "指定した改善内容" \
  --revise-command "$REVISION_COMMAND"

# run の ID を指定して記録と検査結果を確認
strata timeskip status RUN_ID

# 保存済み run を一覧表示
strata timeskip list

# 書き戻し前に差分をプレビューし、確認後に適用
strata timeskip apply RUN_ID --dry-run
strata timeskip apply RUN_ID
```

`run` の完了出力には run ID、状態、各試行の判定が表示され、詳細確認用の `status` とプレビュー用 `apply --dry-run` の呼び出しも案内されます（`strata_cli/cli.py:1585-1602`）。人向け出力が既定で、`--output json` を選べるサブコマンドもあります（`strata_cli/cli.py:369,373-378,393`）。

## 実行モード

| サブコマンド | 動作 |
| --- | --- |
| `run` | ベースラインを保存してチェックし、指定された改訂コマンドを隔離候補上で最大回数実行し、各候補を同じチェックで評価します。 |
| `status RUN_ID` | run の永続記録、チェックポイント、試行、判定を表示します。 |
| `list` | 保存済み run の ID、状態、判定、prompt の一部を一覧表示します。 |
| `apply RUN_ID --dry-run` | 適用予定の書き込み・削除を表示します。作業先には書き込みません。 |
| `apply RUN_ID` | 選択されたチェックポイント、または `--attempt` で指定した試行を作業先へ適用します。 |
| `apply RUN_ID --restore` | 保存済みベースラインを作業先へ戻します。 |

`apply` は既定で run が保持したチェックポイントを適用し、`--attempt N` を指定すると確認後に選んだ試行を適用します。`--restore` は候補の適用ではなく、run 開始時のベースラインを戻すモードです（`strata_cli/cli.py:380-393,1524-1555`）。

## `run` の実行条件と判定

- `--workspace` と `--prompt` は必須です。workspace がディレクトリでなければ run を開始せず、エラー（終了コード 2）になります（`strata_cli/cli.py:352-355,1557-1564`）。
- 検査定義は workspace の `.strata/checks.json` から読みます。ファイルがない場合はチェックなしとして進みますが、改善を裏付けられず判定は inconclusive になります。不正な形式や定義は読み込みエラーになります（`strata_control/time_skip.py:718-731`、`strata_cli/cli.py:1561-1568`）。
- `--attempts` は整数で既定値 2、0 はベースラインの保存・検査のみです。負数は実装で 0 に丸められます（`strata_cli/cli.py:356-358`、`strata_control/time_skip.py:321-330,442-459`）。
- 実際に改訂するには `--revise-command` が必要です。省略時も試行枠は処理されますが、改訂コマンドは呼ばれず候補は変わらないため、チェックで新しい改善が示されず判定は inconclusive になります。指定したコマンドは shell 経由で候補ディレクトリを作業ディレクトリとして実行され、prompt と試行番号は `STRATA_TIMESKIP_PROMPT`、`STRATA_TIMESKIP_ATTEMPT` 環境変数で渡されます。非ゼロ終了は失敗 run として記録されます（`strata_cli/cli.py:359-365,1572-1602`、`strata_control/time_skip.py:442-474,551-556`）。信頼できるコマンドだけを指定してください。
- 各試行は選択中のチェックポイントから別々の候補ディレクトリに作られます。決定的チェックが失敗した候補は拒否され、チェックが実行不能・不明、または改善の証拠がない場合は自動採用されません。助言用チェックは記録されますが、採否を決めるゲートにはなりません（`strata_control/time_skip.py:442-474,519-556`）。

## 主な副作用と注意点

- run ごとの状態、チェックポイント、候補、適用時の rollback コピーが状態ディレクトリに保存されます。各サブコマンドで store を開く際に状態ディレクトリも作成されます。`--state-dir` がなければ `STRATA_TIMESKIP_DIR`、それもなければ POSIX では `$XDG_STATE_HOME/strata/time-skip`（未設定時は `~/.local/state/strata/time-skip`）、Windows では `%LOCALAPPDATA%\Strata\time-skip` が使われます（`strata_cli/cli.py:366-368,1476-1485`、`strata_control/paths.py:13-21`、`strata_control/time_skip.py:695-700`）。
- `run` は workspace を読み取り、状態領域へコピーを作ります。通常の改訂試行は候補ディレクトリ内で行われ、作業ディレクトリへの変更はありません（`strata_control/time_skip.py:408-419,422-459`）。ただし `--revise-command` と `.strata/checks.json` の command は shell で実行されます。コードは改訂コマンドが workspace を変更しない契約を記していますが、任意のコマンド自身の副作用を CLI が封じ込めるものではありません（`strata_cli/cli.py:359-365,1572-1583`、`strata_control/time_skip.py:176-205`）。
- 実適用の前に、作業先の内容が開始時のベースラインと一致するか照合します。変化があれば競合として拒否し、終了コード 6 を返します。適用時は rollback コピーを作り、書き込み失敗時は戻します（`strata_control/time_skip.py:597-652`、`strata_cli/cli.py:1541-1555`）。`--dry-run` で先に予定を確認してください。
- `--restore` は通常の apply のような作業先との一致確認を行わず、ベースラインのファイルを作業先へコピーします。既存の同名ファイルは上書きされ得ますが、コピー処理は作業先の余分なファイルを削除しません。対象 workspace を確認してから使ってください（`strata_control/time_skip.py:271-284,654-664`）。
- `status` の未知 ID や `apply` の run エラーは CLI エラーとして返されます。run の改訂失敗・中断状態は終了コード 6 です（`strata_cli/cli.py:1500-1505,1524-1545,1585-1602`）。

## 関連文書

- [`strata timeskip run`](run/README.md)
- [`strata timeskip status`](status/README.md)
- [`strata timeskip list`](list/README.md)
- [`strata timeskip apply`](apply/README.md)
- [CLI 文書索引](../../README.md)

## 根拠

- Strata `strata_cli/cli.py:348-393` — 親コマンド、サブコマンド、引数の parser 定義。
- Strata `strata_cli/cli.py:1467-1602,2147-2150` — 状態領域の選択、各モードの出力・失敗経路、コマンド dispatch。
- Strata `strata_control/time_skip.py:313-341,408-493` — run 状態、ベースライン保存、候補生成、完了・失敗記録。
- Strata `strata_control/time_skip.py:516-593` — チェック実行と判定規則。
- Strata `strata_control/time_skip.py:597-664,695-731` — apply / restore、run 一覧とチェック定義の読み込み。
- Strata `strata_control/paths.py:13-21` — ユーザー状態ディレクトリの既定パス。

調査は上記 commit の checkout 内ソースに基づきます。この作業では CLI `--help` と GitHub Release の実体は確認していません。配布済み CLI の版や platform ごとの差はここでは検証対象外です。
