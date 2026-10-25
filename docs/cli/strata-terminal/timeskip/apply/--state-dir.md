# `strata timeskip apply --state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | 状態ディレクトリのパス（文字列）。型・存在確認の parser validation なし |

## 役割

読み込む Time-skip run の記録が置かれたディレクトリを指定します。`run_id` はこのディレクトリ直下の `<run_id>/run.json` から読み込まれます。実行時に使った状態ディレクトリと異なる場所を指定すると、その場所に対象 run がない限り読み込みに失敗します。

## 使い方

```sh
strata timeskip apply RUN_ID --state-dir /path/to/time-skip --dry-run
```

`--state-dir` は `strata timeskip apply` 固有の parser option です。同じ名前の option は `timeskip run`、`status`、`list` にもありますが、各サブコマンドで個別に定義されています。

## 値と既定値

- 値は `argparse` の既定の文字列として受け取り、`default=None` です。パス形式、存在、書き込み可能性を parser 段階では検証しません。
- 省略時は `STRATA_TIMESKIP_DIR` が設定されていればその値、そうでなければ `strata_control.paths.state_base() / "time-skip"` を使います。POSIX の `state_base()` は `$XDG_STATE_HOME/strata`（未設定時は `~/.local/state/strata`）、Windows は `%LOCALAPPDATA%\Strata`（未設定時はユーザーの `AppData\Local\Strata`）です。
- 明示値は `Path` に変換されます。相対パスはプロセスの作業ディレクトリを基準に解決されます。空文字列は state root 選択時の真偽値判定で未指定と同様に扱われます。

## 実行時の動作

CLI は `--state-dir` または既定 root から `TimeSkipStore` を作り、その root を使って `run_id` を検索します。store 初期化時に root がなければ親ディレクトリも含め作成します。そのため、apply の run 読み込み前に状態ディレクトリが作成される場合があります。

記録を読み込んだ後、run の保存済み情報から `TimeSkipRun` を再構築します。通常の適用では、保存済みの retained checkpoint（または `--attempt` で選んだ revision）を、保存済み workspace か `--workspace` の宛先へ適用します。`--dry-run` は変更予定を返すだけです。適用前には宛先の内容が baseline と一致するかを照合し、異なれば上書きを拒否します。適用のための rollback copy は run 状態ディレクトリ内の `rollback` に置かれます。`--restore` はこの通常適用とは別に baseline を宛先へ戻し、run 記録も更新します。

## 適用条件と副作用

- `--state-dir` 自体はファイルや workspace を変更せず、run の読み込み元・状態保存先を選びます。ただし指定先がなければ `TimeSkipStore` の初期化によりディレクトリを作成します。
- 適用先は既定で run に記録された workspace です。`--workspace` を併用すると宛先を変更しますが、`--state-dir` は依然として run 記録の検索元です。
- 通常適用は baseline と宛先が一致する場合だけ続行し、成功時にはファイルをコピー・削除して rollback copy を残します。dry-run は書き込みを行いません。
- `--restore` は baseline をコピーして run の選択 checkpoint・decision を更新し、run 状態を保存します。実装は restore 時に apply の dry-run 分岐を通しません。
- この調査では安全な既存の同一 revision CLI を特定できず、help は実行していません。値の境界や異常な権限・ファイルシステム条件は実測していません。

## 出力とエラー

- run が見つからない場合など `TimeSkipError` は stderr に `strata: ...` を出し、終了コード 2 になります。`--output json` では `ok: false` とエラー情報を JSON で出力します。
- 通常適用で宛先が baseline から変化している場合は競合として拒否され、終了コード 6 です。適用失敗後に rollback された場合も、未完了として終了コード 6 になります。
- 成功時の通常出力は `applied ...` と `rollback copy: ...`、dry-run は `would write: ...` および必要に応じ `would remove: ...` です。JSON 出力では結果を `apply` または `restore` キーに含めます。
- ルート作成や状態ファイルの読取で発生する全 OS 例外について、CLI がどの表示・終了コードへ変換するかはこの経路のコードだけでは一律に確認できません。

## 根拠

- `strata_cli/cli.py:380-393` — `timeskip apply` の引数定義。`--state-dir` は値を取る文字列で既定 `None`。
- `strata_cli/cli.py:1467-1485` — state root の優先順位と `TimeSkipStore` 初期化。
- `strata_control/paths.py:13-21` — OS ごとの既定 state base。
- `strata_control/time_skip.py:695-716` — store root 作成、run 一覧・run 読み込み。
- `strata_control/time_skip.py:375-379` — `<root>/<run_id>/run.json` の読み込みと run 不在エラー。
- `strata_cli/cli.py:1524-1555,1605-1618` — run 再構築、apply/restore 分岐、出力・終了コード。
- `strata_control/time_skip.py:597-664` — retained checkpoint / attempt の適用、宛先 digest 照合、dry-run、rollback copy、restore の副作用。
- `strata_cli/cli.py:527-541` — 人間向け・JSON エラー出力。
