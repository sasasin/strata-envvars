# `--check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `false`、指定時 `true` |

## 役割

署名付き update feed を読み、この PC の engine、Control、desktop app に何が適用されるかを表示します。通常の更新処理へ進まず、パッケージはダウンロードしません。ただし feed とその署名の読み込み、および確認結果のローカル状態保存は行います。

## 使い方

```sh
strata update --check
```

JSON 形式で結果を得る場合は、同じ parser 群に `strata_cli/cli.py` が追加する `--json` を併用できます。

```sh
strata update --check --json
```

## 値と既定値

- `argparse` の `store_true` フラグであり、値は指定しません。既定値は `false` です。`--check` を指定すると `a.check` が真になります（`strata_cli/update_cmd.py:42-47`）。
- `--check=true` のような値付き指定はこの parser の構文ではありません。重ねて指定しても真偽値を切り替える機能はなく、効果は変わりません。
- 同じ共有 parser 定義が `strata components update` にも `--check` を登録します。こちらのオプション文書は [`strata components update --check`](../components/update/--check.md) です（`strata_cli/update_cmd.py:50-53`）。

## 実行時の動作

1. `strata update` は `update_cmd.add_parsers()` から parser 登録され、実行時には `update_cmd.run()` に委譲されます（`strata_cli/cli.py:139-140,2135-2137`）。
2. CLI は hardware を検出し、`--backend` があれば選択値で上書きして確認用 context を作ります。確認はその platform/backend 条件に合う engine を選ぶため、`--backend` は表示される engine 判定に影響します（`strata_cli/update_cmd.py:174-184`、`strata_control/updater.py:522-524,566-590`）。
3. feed の参照先は `--feed`、環境変数 `STRATA_UPDATE_FEED`、components state に記録された前回の feed、既定の GitHub Release feed の順で決まります（`strata_cli/update_cmd.py:87-95`）。feed と署名を読み、署名・期限・sequence などを検証したうえで結果を組み立てます（`strata_control/updater.py:355-366`、`strata_control/feed.py:342-360`）。ネットワーク feed の場合は feed JSON と署名の読み込みを行います（`strata_control/feed.py:342-360`、`strata_control/transfer.py:159-187`）。
4. engine、Control、app の状態、稼働中 engine の情報、hardware を含む report を作成します。成功時の終了コードは `0` で、人間向け表示では engine の候補・状態や Control/app の状態を表示します（`strata_control/updater.py:624-632`、`strata_cli/update_cmd.py:132-160,203-209`）。

## 適用条件と副作用

- `--check` 分岐は通常更新処理より前に return するため、この経路では `run_update()` による engine/Control/app のインストール、engine の test start、`--wait` による待機は実行されません（`strata_cli/update_cmd.py:203-213`）。`--no-engine`、`--no-control`、`--app` が指定されても、check report 自体は engine・Control・app を対象に作られます。
- `--force` は context に渡され、失敗済みまたは rollback 済みの候補を `failed-before` / `skipped` として保留する判定に影響します（`strata_cli/update_cmd.py:182-184`、`strata_control/updater.py:603-614`）。
- 確認は読み取り専用ではありません。components directory 内の `.updates/update.lock` を取得し、feed 情報と確認結果を `.updates/state.json` に保存します。`last_check` には時刻、候補 engine/app、確認対象時点の Control/engine version が記録されます（`strata_control/updater.py:134-162,624-640`）。
- 通常の既定 feed は `https://github.com/Niko1221/Strata/releases/latest/download/strata-feed.json` です。ローカル feed の場合、ソースは feed と署名ファイルの読み込みを行います。個別 feed の URL 制約・署名鍵の設定はこのオプションだけでは変更しません（`strata_cli/update_cmd.py:23-28,87-95`、`strata_control/feed.py:342-360`）。

## 出力とエラー

- 既定の human 出力は feed sequence/channel/署名鍵、engine の更新候補と選択 package、Control/app の状態、および稼働中 engine の有無を表示します（`strata_cli/update_cmd.py:132-160`）。`--json` は `--output json` の alias として parser に追加され、成功時は report を含む JSON を stdout に出します（`strata_cli/cli.py:508-515`、`strata_cli/update_cmd.py:203-209`）。
- feed を読めない場合は feed error（通常は終了コード `6`）、署名検証エラーまたは取得禁止の場合は終了コード `5` などで失敗します。human mode は `strata: ...` を stderr に出し、machine mode はエラー情報を JSON で出力します（`strata_control/feed.py:342-360`、`strata_cli/update_cmd.py:167-172,225-232`）。
- 同じ components directory で別の update が lock を保持している場合は終了コード `7` で拒否されます（`strata_control/updater.py:134-152`）。

## 根拠

- `strata_cli/update_cmd.py:42-47` — `strata update` の parser と `--check` 宣言。
- `strata_cli/update_cmd.py:87-95,163-209,225-234` — feed の優先順位、check 分岐、成功出力・失敗処理。
- `strata_cli/cli.py:139-140,508-515,2135-2137` — parser 登録、共有 `--json` / `--quiet`、実行委譲。
- `strata_control/updater.py:134-162,355-366,522-524,566-614,624-640` — lock/state、feed 更新、engine 判定、check report と保存。
- `strata_control/feed.py:342-360`、`strata_control/transfer.py:159-187` — feed・署名の読み込み経路。
