# `--no-engine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--no-engine` |
| 別名 | なし |
| 値 | 値なしのフラグ。既定値は `false` |

## 役割

通常の `strata update` 実行で engine の更新工程を省略します。Control の更新は別の `--no-control`、デスクトップアプリ installer のダウンロードは `--app` で独立して指定します（`strata_cli/update_cmd.py:42-49,213`）。

## 使い方

```sh
strata update --no-engine
```

Control とアプリ installer だけを対象にする場合は、たとえば次のように指定します。

```sh
strata update --no-engine --app
```

## 値と既定値

- parser は `action="store_true"` で定義され、引数値を取りません。省略時は `false`、指定時は `true` です（`strata_cli/update_cmd.py:42-49`）。
- 値の範囲や値の validation はありません。値を続けて渡す構文ではなく、同じフラグを複数回指定しても真偽値を立てる動作です（`strata_cli/update_cmd.py:48`）。

## 実行時の動作

- `strata update` はトップレベル `update` parser を登録し、CLI dispatcher から `update_cmd.run(a)` を呼びます（`strata_cli/update_cmd.py:42-49`; `strata_cli/cli.py:139-140,2135-2137`）。
- 通常実行では `run()` が `updater.run_update()` に `engine=not a.no_engine` を渡します。`--no-engine` 指定時、更新処理は feed の読込・状態保存を行ったうえで engine step を作らず、Control は `--no-control` がなければ、app は `--app` があれば処理します（`strata_cli/update_cmd.py:210-224`; `strata_control/updater.py:1274-1285`）。
- engine step を省略するため、この経路では engine package の選択・ダウンロード・検証・test-start・切替を行う `update_engine()` に進みません（`strata_control/updater.py:926-960,1279-1285`）。
- `--check` を指定した場合は、`--no-engine` の値を `run_update()` に渡す行より前に `updater.check()` を呼びます。そのため `--no-engine` は check レポートの engine 項目を除外せず、check は engine・Control・app の状態を判定します。また check は feed 以外をダウンロードしませんが、`last_check` を state に保存します（`strata_cli/update_cmd.py:203-209,213`; `strata_control/updater.py:624-640`）。
- `--no-engine` は feed 読込、署名鍵の読込、取得禁止 (`STRATA_NO_ACQUIRE`) の確認を省きません。通常実行時にも `run_update()` は取得禁止を確認し、更新 lock 内で feed を開いて state を保存します（`strata_cli/update_cmd.py:197-200`; `strata_control/updater.py:1274-1282`）。

## 適用条件と副作用

- この文書は `strata update` のスコープです。同じ `--no-engine` は `strata components update` にも別 parser で定義されていますが、そちらは索引上の別文書です（`strata_cli/update_cmd.py:50-56`; [`components update の文書`](../components/update/--no-engine.md)）。
- 通常実行では `_maybe_wait()` が `run_update()` より先に呼ばれ、engine が稼働中で `--wait` が未指定の場合、対話端末で待機確認を表示することがあります。これは `--no-engine` でも発生し得ます。ただし engine step を省略した後は、engine 更新処理内の serving 待機には進みません（`strata_cli/update_cmd.py:210,237-252`; `strata_control/updater.py:945-946,1279-1285`）。
- `--no-control` も付けて `--app` を省略した場合、実行対象 step は空になりますが、共通の取得確認・lock・feed 読込・state 保存は `run_update()` 内で行われます（`strata_cli/update_cmd.py:197,213`; `strata_control/updater.py:1274-1285`）。

## 出力とエラー

- 通常の human 出力では feed の署名情報と実行された各 component の結果を表示します。engine step を省略した場合、結果一覧に engine の行はありません。JSON/JSONL 出力でも `run_update()` の結果が使われ、engine step は含まれません（`strata_cli/update_cmd.py:211-224`; `strata_control/updater.py:1283-1297`）。
- feed、署名、取得許可などの共通処理が失敗すれば、このフラグを指定していてもエラーになります。`UpdateError` / `FeedError` は human 出力で stderr、JSON/JSONL ではエラー JSON として報告され、各例外の終了コードを返します。署名エラーと取得拒否はコード `5`、中断はコード `130` です（`strata_cli/update_cmd.py:167-172,225-234`）。
- 省略しなかった Control または app の処理が失敗しても、残りの step を試行し、全体は最初の `UpdateError` の終了コードを返します（`strata_control/updater.py:1286-1297`）。

## 根拠

- `strata_cli/update_cmd.py:42-49` — `strata update` parser と `--no-engine` の宣言。
- `strata_cli/cli.py:139-140,2135-2137` — parser 登録と `update_cmd.run()` への dispatch。
- `strata_cli/update_cmd.py:163-234` — 共通準備、取得可否、`--check` 分岐、通常実行への引き渡し、出力と失敗処理。
- `strata_cli/update_cmd.py:237-252` — 通常更新前の稼働確認・対話待機。
- `strata_control/updater.py:624-640` — check が各 component を判定し `last_check` を保存する処理。
- `strata_control/updater.py:926-960` — engine 更新工程。
- `strata_control/updater.py:1274-1297` — engine / Control / app step の選択、失敗集約と終了コード。

## 調査範囲

この記述は指定 checkout の Python CLI と updater 実装を対象にしています。別の checkout、Release binary の実行結果、各 OS での対話表示差は実行して確認していません。
