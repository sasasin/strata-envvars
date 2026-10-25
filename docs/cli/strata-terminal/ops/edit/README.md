# `strata ops edit`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops edit` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |
| 引数 | `NAME`（編集する recipe ID） |
| 必須 option | `--profile PROFILE` |
| 出力形式 | `--output human|json`（既定値 `human`）、`--json` は JSON 出力の alias |

## 役割

保存済み serving profile に紐づく、型付きローカル operation recipe を外部エディターで編集します。recipe は任意の shell command を実行するためのファイルではなく、`runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれかの Strata 操作と、その型付きパラメーターを記録します。編集は recipe の保存までで、operation の実行は `strata ops run` が行います（`strata_cli/cli.py:255-267`、`strata_control/recipes.py:28-29,93-114`）。

## 使い方

profile と recipe を先に用意し、エディターで編集した後、必要なら plan を確認してから実行します。

```sh
strata ops init --profile four-gpu
strata ops edit restart --profile four-gpu
strata ops plan restart --profile four-gpu --output json
strata ops run restart --profile four-gpu
```

`ops init` は `restart`、`calibrate`、`check` の標準 recipe を初期化します。既存 recipe の一覧確認には `strata ops list`、直接パラメーターを変える場合には `strata ops set NAME --profile PROFILE KEY=VALUE` を使えます。編集コマンド自体は recipe `NAME` と必須 `--profile` を受け取り、`--output`、`--json`、`--quiet` は各 one-shot ops parser に共通で追加されます（`strata_cli/cli.py:258-277,508-515`、`docs/TERMINAL.md:99-108`）。

## 実行モード

| モード | コマンド例 | 動作 |
| --- | --- | --- |
| 初期化 | `strata ops init --profile PROFILE` | 標準 recipe を初期化します。 |
| 一覧・表示 | `strata ops list --profile PROFILE`、`strata ops show NAME --profile PROFILE` | recipe 一覧または個別内容を表示します。 |
| 編集 | `strata ops edit NAME --profile PROFILE` | 保存済み recipe の一時 JSON コピーをエディターで開き、正常終了と schema 検証後に保存します。 |
| 計画 | `strata ops plan NAME --profile PROFILE` | recipe 種別に応じた事前確認を行い、実行予定の効果を表示します。操作本体は実行しません。 |
| 実行 | `strata ops run NAME --profile PROFILE` | recipe に対応する Strata 操作を実行し、結果を operation journal に記録します。 |
| 履歴管理 | `strata ops history NAME --profile PROFILE`、`strata ops rollback NAME --profile PROFILE --to REVISION` | recipe の revision を表示し、指定した過去 revision を復元します。 |
| 実行記録 | `strata ops runs --profile PROFILE`、`strata ops result OPERATION_ID --profile PROFILE` | operation の一覧または個別結果を表示します。 |

recipe の種類によって実行時の影響が異なります。restart は稼働 instance の drain と新 instance の起動、calibration は engine を使った測定と新しい report の作成、components verify は component の検査を行います。calibration の実行には毎回 `--exclusive` が必要です。recipe 編集と operation 実行は別コマンドです（`strata_cli/cli.py:1391-1453`、`strata_control/recipes.py:329-398`、`docs/TERMINAL.md:104-116`）。

## 主な動作と副作用

- `--profile` は既存の保存済み profile を指定します。profile ID と recipe ID は小文字英字で始まり、小文字英数字、`_`、`-` を使う最大64文字です。recipe は profile directory 内の `.ops/PROFILE/NAME.json` に保存されます（`strata_control/recipes.py:32-64`、`strata_control/profiles.py:25,38-45`）。
- エディターは `VISUAL` を優先し、未設定なら `EDITOR` を使います。値は `shlex.split` で argv に分割され、shell を介さず一時ファイルのパスを末尾引数として起動します。どちらも未設定・空の場合は編集を開始せずエラーになります（`strata_control/recipes.py:299-312`）。
- 元 recipe を同じ `.ops/PROFILE/` 内の一時 JSON に書き、エディターが正常終了した場合だけ JSON を読み直して検証します。変更なしなら既存 revision のままで、変更があれば現 revision を `.ops/PROFILE/.history/NAME/` に保全し、新しい JSON に置換します。成功時は一時ファイルを削除します（`strata_control/recipes.py:214-237,307-326`）。
- Recipe JSON は最大64 KiBの通常ファイルで、POSIX では profile/recipe/history の owner-only 権限が検査されます。recipe schema は version 1 で、未知の field や種類ごとに許されない値を拒否します。restart の `startup_wait_s` は整数1..600、calibration の `report_dir` は空でない絶対パス、components verify は `live` boolean のみです（`strata_control/recipes.py:38-59,71-86,93-114,180-196`）。
- 保存は profile lock のもとで revision を再確認します。編集中に別プロセスが recipe を変更した場合は競合エラーとなり、その draft を保持します。エディターが非0終了した場合や JSON/schema が不正な場合も draft を保持して場所をエラーに示します（`strata_control/recipes.py:214-237,299-326`）。

## 注意点

- 編集には `VISUAL` または `EDITOR` が必要です。設定できない環境では、型付き変更を行う `strata ops set` が代替になります。
- `edit` は recipe を保存するコマンドであり、plan や operation の実行は行いません。保存内容を見直し、必要に応じて `strata ops plan` を実行してから `strata ops run` を使ってください。
- recipe file が未作成の場合は `strata ops init --profile PROFILE` を案内するエラーになります。編集による一時 draft は recipe directory 内に作られるため、編集失敗時には手動で確認・削除するまで残ることがあります（`strata_control/recipes.py:180-196,299-326`）。
- `--quiet` は human 出力を stdout から抑制し、JSON 出力には適用されません。失敗時に抑制対象の human 出力があれば stderr に出します。各 option の詳細は [CLI オプション索引](../../../README.md) を参照してください。索引では `strata ops edit` 配下の `--help`、`--json`、`--output`、`--profile`、`--quiet` を掲載しています（`strata_cli/cli.py:508-515,2232-2248`）。

## 関連文書

- [Terminal CLI の使い方（ops の例）](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/TERMINAL.md)
- [CLI オプション索引](../../../README.md)
- [`strata ops` 実装](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py)

## 根拠

- Strata `strata_cli/cli.py:255-277,508-515` — `ops` の階層、引数、共通 output/json/quiet option。
- Strata `strata_cli/cli.py:2232-2248` — one-shot `--json` の適用と `--quiet` による human 出力の扱い。
- Strata `strata_cli/cli.py:1391-1422,2160-2173` — `edit` から recipe 層への呼び出しとエラー出力経路。
- Strata `strata_control/recipes.py:28-29,32-64,71-114` — recipe 種別、保存場所、ID、schema と値の検証。
- Strata `strata_control/recipes.py:180-196,214-237,299-326` — 読み込み制約、revision 競合、履歴保存、一時 draft と editor の起動・失敗処理。
- Strata `strata_control/recipes.py:329-398` — plan と run が種別ごとに行う処理。
- Strata `strata_control/profiles.py:38-45,62-63,213-233` — profile directory と revision、atomic file replacement。
- Strata `docs/TERMINAL.md:99-116` — ops の利用例と推奨される init/edit/plan/run の流れ。

調査は上記 commit のソース checkout と同 checkout の `docs/TERMINAL.md` に限定しました。Release archive に含まれる CLI バイナリとの照合は行っていません。
