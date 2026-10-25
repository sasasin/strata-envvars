# `strata tune apply --state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリのパス（文字列、必須） |

## 役割

チューニング job を読む state directory を指定します。apply が成功すると、このディレクトリの下に作成される `applications/` に適用記録、変更前の設定のコピー、候補設定を保存します。`strata tune rollback` も同じ state directory を参照するため、適用後の rollback にも同じ値を指定してください。

## 使い方

```sh
strata tune apply <job-id> --config ./strata-model.json --model-path ./model.gguf --state-dir ./tune-state
```

この例では `./tune-state/<job-id>/job.json` から job を読み、成功時には適用記録を `./tune-state/applications/<application-id>/` に保存します。相対パスはプロセスの作業ディレクトリを基準に解決されます。

## 値と既定値

- parser は値を文字列として受け取り、既定値は `None` です。パスの存在、ディレクトリであること、絶対パスであることなどを parser では検証しません（`strata_cli/cli.py:461-470`）。
- 省略時は環境変数 `STRATA_TUNE_DIR` が設定されていればその値を使い、未設定または空なら `state_base() / "tuning"` を使います（`strata_cli/cli.py:1643-1650`）。
- `state_base()` は POSIX では `$XDG_STATE_HOME/strata`（`XDG_STATE_HOME` 未設定時は `~/.local/state/strata`）、Windows では `%LOCALAPPDATA%\Strata`（未設定時は `%USERPROFILE%\AppData\Local\Strata` 相当）です。したがって既定の tuning directory はそれぞれ `.../strata/tuning`、`...\Strata\tuning` です（`strata_control/paths.py:13-21`）。
- 明示値が空文字列の場合は truthy 判定を通らず、環境変数または既定値にフォールバックします。繰り返し指定時の独自処理はなく、通常の `argparse` による解析です（`strata_cli/cli.py:464-470,1643-1650`）。

## 実行時の動作

1. `strata tune apply` は `state_root()` を使い、`--state-dir`、`STRATA_TUNE_DIR`、OS 別既定値の順に保存先を選びます（`strata_cli/cli.py:1643-1650,1710-1712`）。
2. `<job-id>` は16進数8〜64文字でなければ job として読み込まれません。選択したディレクトリの `<job-id>/job.json` を読みます（`strata_cli/cli.py:1941-1950`）。
3. apply の前段では report の状態・推奨の有無・測定中の drift・report hash・現在の artifact identity などを確認します。条件を満たさない場合は拒否され、設定ファイルには書き込みません（`strata_control/tune_apply.py:227-289,317-321`）。
4. 適用が通ると `--state-dir/applications/<application-id>/` を作り、`before.json`、`candidate.json`、`application.json` を保存します。別途、`--config` で指定した run config を atomic write で置き換えます。したがって `--state-dir` は run config の保存場所を変更しません（`strata_control/tune_apply.py:62-74,300-370`）。
5. `strata tune rollback <application-id>` はその state directory の適用記録を使います。既定以外のディレクトリへ apply した場合、rollback にも同じ `--state-dir` を指定します（`strata_cli/cli.py:472-475,1953-1963`; `strata_control/tune_apply.py:373-401`）。

`--state-dir` を変えると job の探索先も変わるため、job が別の保存先にある場合はその job を見つけられません。apply parser の `--context` は整数値を受け取りますが、現行の `_tune_apply` はその CLI 値ではなく job の plan に保存された context を identity の再計算に使います（`strata_cli/cli.py:468-470,1868-1879`）。

## 適用条件と副作用

- apply は明示的な実行で、job に有効な推奨があり、report と現在の engine/model/backend/workload/context/machine identity が整合するなどの条件が必要です（`strata_control/tune_apply.py:227-289`）。CLI は model digest が記録されていない job、model file が見つからない場合、identity を再構成できない場合も拒否します（`strata_cli/cli.py:1883-1898`）。
- 現行 CLI は `apply_recommendation(..., verify=None)` を呼びます。そのため candidate を実モデルで起動して token 生成を確認する callback は渡されません。人間向け成功出力にも実行検証をしていない旨を表示します（`strata_cli/cli.py:1900-1920`）。
- 成功時は `--state-dir` 以下にバックアップ等のファイルを新規作成し、指定または自動選択された run config を変更します。rollback は apply 後にその設定が編集されていた場合、後の編集を失わないよう復元を拒否します（`strata_control/tune_apply.py:339-370,373-400`）。
- パスの形式に関する OS・backend 別の追加制約や、`~` 展開は CLI に実装されていません。`Path` に渡されるパス文字列が使われます（`strata_cli/cli.py:1643-1650`）。

## 出力とエラー

job が見つからない場合、人間向けでは stderr に `strata: ...` を出して終了コード `2` を返します。JSON 出力では同じ失敗を `{schema_version, ok: false, error: {code, message}}` 形式で stdout に出します（`strata_cli/cli.py:1859-1861,527-532`）。`ApplyError` による適用拒否も同じ出力経路を使い、例外に設定された code を返します（`strata_cli/cli.py:1900-1905,527-532`）。

成功時は human 出力で変更対象、追加・削除された flag、前後の SHA256 の一部、rollback 用 application ID を表示します。`--output json` では成功結果を JSON で出力します（`strata_cli/cli.py:1907-1920,535-542`）。

## 根拠

- parser と `--state-dir` の値定義: `strata_cli/cli.py:461-470`
- state directory の優先順位と apply への受け渡し: `strata_cli/cli.py:1643-1650,1710-1712`
- job 読み込みと失敗時の出力: `strata_cli/cli.py:1859-1866,1941-1950,527-532`
- identity 条件、apply 関数の呼び出し、成功表示: `strata_cli/cli.py:1868-1920`
- OS 別 state base: `strata_control/paths.py:13-21`
- apply の検査、バックアップと設定書き込み、rollback: `strata_control/tune_apply.py:227-289,300-401`

調査範囲は上記 checkout の Python CLI と関連する tuning 実装です。同一 revision の CLI `--help` および Release 配布物との照合は行っていません。文書はソースコードの parser と使用経路に基づいています。
