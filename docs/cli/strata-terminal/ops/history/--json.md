# `strata ops history --json`

`strata ops history` の結果を機械可読な JSON で標準出力へ出すフラグです。recipe の履歴を表示するだけで、履歴や recipe は変更しません。

## 使い方

```sh
strata ops history recipe-name --profile profile-name --json
```

`recipe-name` は履歴を表示する recipe 名、`profile-name` はその recipe が属する保存済み profile です。両方ともこのコマンドで必要です。

## 値・既定値・検証

- 値は取りません。`store_true` の真偽フラグです。指定しない場合は `False` で、通常の人向け表示になります。
- `--json` は `strata ops` の one-shot parser 群へ共通で追加されます。`history` を含む全 ops action が対象です。JSON 表示の正規指定は `--output json` です。
- `--output` の選択肢は `human` と `json`、既定値は `human` です。`--json` を付けると、parser 後の処理で `--output` が `json` に設定されます。そのため `--output human` も併記した場合は `--json` が優先します。
- recipe 名と profile 名は `--json` 自体の検証対象ではありません。必須の `--profile` や位置引数 `name` の不足、不正な引数は argparse が拒否します。

## 実行時の動作

履歴取得ではまず現在の recipe を読み込んでその revision を求め、続けて `.history/<recipe名>/` にある履歴ファイルを走査します。出力の `history` 配列は現在の revision を先頭に置き、その後に過去 revision をファイル更新時刻の新しい順に並べます。現在の要素には `current: true` が付き、過去の要素には revision と `saved_at`（ファイル更新時刻）が含まれます。

成功時の出力は1行の JSON で、`schema_version: 1`、`ok: true`、`profile`、`recipe`、`history` を含みます。`--quiet` と併用しても JSON 出力は抑止されません。`--json` は `--quiet` も受理する one-shot action に追加されており、JSON モードでは quiet 用の人向け標準出力捕捉処理を通らないためです。

履歴の読み込みは参照のみです。recipe が存在しない、データが不正、履歴ディレクトリが symlink である、または権限・ファイル状態が不正などの場合は処理が失敗し得ます。JSON モードでは失敗を `schema_version: 1`、`ok: false`、`error`（終了コードとメッセージ）の JSON として標準出力へ出します。たとえば recipe がない場合、案内付きのエラーになり終了コードは `5` です。

## 根拠

調査対象は Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、調査日は `2026-10-25` です。調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

- 索引のコマンド階層と option scope: `docs/cli/README.md`（`strata ops history` 節）。
- parser 定義、必須の `name` / `--profile`、`--output` の選択肢と既定値: `strata_cli/cli.py:255-268`。
- one-shot ops parser 群への `--json` と `--quiet` 追加: `strata_cli/cli.py:508-515`。
- `--json` が `--output json` に変換される処理: `strata_cli/cli.py:2232-2237`。JSON 応答と `--quiet` の失敗時捕捉: `strata_cli/cli.py:2236-2248`。
- `history` action の呼び出しと成功表示: `strata_cli/cli.py:1391-1394,1431-1435`。
- 成功 JSON の形式、人向け表示との分岐: `strata_cli/cli.py:535-542`。
- 履歴収集順、revision と `saved_at` の構成: `strata_control/recipes.py:240-250`。
- recipe の読み込み、ファイル種別・サイズ・POSIX 所有者権限の確認、および未作成時の終了コード: `strata_control/recipes.py:180-196`。
- 履歴ディレクトリの symlink と所有者権限確認: `strata_control/recipes.py:71-86`。
- 例外を JSON エラーへ変換する共通経路: `strata_cli/cli.py:2119-2173`。
