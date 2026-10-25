# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

再チェック結果の表示形式を選びます。`--output json` は機械処理向けの JSON を標準出力へ出し、進捗メッセージを抑制します。ファイル出力先を指定するオプションではありません。

## 使い方

```sh
strata presets recheck <preset-id> <profile-name> --output json
```

`<profile-name>` には preset が属する profile 名、または run configuration（JSON）のパスを指定します。preset と target はどちらも必須です。

## 値と既定値

- 省略時は `human`。
- 指定できる値は `human` と `json` のみ。別の値は `argparse` の `choices` 検証で拒否されます。
- 短縮別名や `--json` alias は定義されていません。
- `--output` は `presets` の各サブコマンドに共通で追加されますが、この文書の対象は `recheck` です。

## 実行時の動作

`human` では再チェック中の状況を標準エラーへ逐次表示し、終了時に判定に応じた短い結果を標準出力へ出します。判定は `keep`、`retune`、`inconclusive` です。`json` では進捗メッセージを抑え、終了時に `schema_version: 1`、`ok: true`、判定・理由・測定結果・更新後の preset 情報を含む JSON を標準出力へ出します。

このオプションは表示と進捗ログの選択だけに作用します。どちらの形式でも preset を検索し、target の設定と現在の PC/engine identity を読み、保存済み設定で engine を起動して測定します。通常は preset 設定で一度起動し、条件によって遅い prompt の再測定を行います。engine の tuning epoch が変わっていれば標準設定との比較起動も追加されます。測定後は判定を preset に記録します。したがって `json` を選んでも測定・保存の副作用はなくなりません。

## 適用条件と副作用

- 現在の PC と preset の差が hard stale と判定された場合、再チェックを始めず失敗します。JSON モードではエラー JSON、human モードでは標準エラーへエラーを出し、終了コード `5` です。
- `--status-file` が併用されると、進捗と完了状態を JSON ファイルへ書き込みます。書き込みは一時ファイル `<path>.tmp` から置換する方式です。書き込み時の `OSError` は無視されます。`--output` の形式はこの status file の書式を変えません。
- `--work-dir` 省略時は `strata-recheck-` prefix の一時ディレクトリを作成します。`--serve-dir` と `--boot-timeout` は worker の実行先・起動 timeout、`--gpu-lock` は指定時の engine 実行ロックに使われます。これらは `--output` と独立した同一サブコマンド内のオプションです。
- `keep` の場合、再チェック結果を保存し、成功時刻と現在の identity を更新します。測定値が以前より 3% 超速い場合は保存値も更新します。`retune` と `inconclusive` でも最終結果を preset に記録しますが、再調整を自動実行するものではありません。

## 出力とエラー

- 成功時の終了コードは `0`。human の最終表示は判定ごとに「Still as fast...」「Not as fast...」「Could not tell...」のいずれかです。
- human の進捗は標準エラー、最終結果は標準出力です。JSON モードでは進捗を抑止し、成功結果を標準出力へ一行の JSON として出します。
- recheck 内で preset が見つからない、target 解決に失敗するなど、捕捉対象の `PresetError` は終了コード `5`、`OSError` / `ValueError` は例外の `exit_code`（なければ `2`）です。`json` では `ok: false` と `error.code` / `error.message` を標準出力へ出し、human では `strata: <message>` を標準エラーへ出します。
- `--output` の値が未対応なら parser が拒否し、通常の argparse usage/error 経路（終了コード `2`）になります。

## 根拠

- `strata_cli/tune_commands.py:49-55`, `strata_cli/tune_commands.py:82-90` — `presets` の共通 `--output` 定義と recheck 専用引数。
- `strata_cli/cli.py:487`, `strata_cli/cli.py:2151-2152` — parser 登録と `presets_command` への dispatch。
- `strata_cli/tune_commands.py:95-108`, `strata_cli/tune_commands.py:289-293` — human/JSON 成功・失敗出力と `--output` の選択。
- `strata_cli/tune_commands.py:411-447` — recheck の実行、hard-stale 判定、進捗ログの抑制、status file、preset 記録、最終 payload。
- `strata_cli/tune_commands.py:126-137`, `strata_cli/tune_commands.py:149-157` — serve dir、GPU lock、status file の処理。
- `strata_control/autotune.py:885-955` — 測定回数・条件、engine tuning epoch による比較、判定の生成。
- `strata_control/presets.py:412-429` — 再チェック結果の保存と `keep` 時の identity/測定値更新。

調査範囲は上記 checkout の Terminal CLI と関連する preset/tuning 実装です。`strata --help` の実行、Release artifact、別 OS/backend での実動作確認は行っていません。
