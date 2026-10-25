# `strata profile show --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile show` |
| オプション | `--json` |
| 別名 | なし（`--output json` が同じ出力形式を指定） |
| 値 | 値を取らないフラグ。既定値は無効。 |

## 役割

プロフィールを表示する one-shot コマンドの出力を、機械処理向け JSON にします。成功時のトップレベルには `schema_version: 1`、`ok: true`、保存プロフィール `profile` とその `revision` が含まれます。通常の `show` では保存内容を返し、`--effective` も指定すると実効設定 `plan` が加わります。

## 使い方

```sh
strata profile show default --json
strata profile show default --json --effective
```

`name` は必須の位置引数です。`--json` は `profile show` の parser に登録されます。`--output json` も使えます。両方を指定した場合も JSON 出力です。

## 値と既定値

- 値引数なしの `store_true` フラグで、未指定時は `false` です。重ねて指定しても有効状態のままです。
- `profile show` は `--output` に `human` または `json` を受理し、既定は `human` です。`--json` が真なら parser 後処理が `output` を `json` に設定するため、同時指定した `--output human` も JSON 指定に上書きされます。
- コマンド階層が異なる `--json` は別スコープです。ここで扱うのは `strata profile show` のものです。

## 実行時の動作

1. parser は `profile show` を登録し、`name`、`--effective`、`--output` を定義します。後段の one-shot parser 登録が同じ parser に `--json` と `--quiet` を追加します。
2. `main` は `--json` が指定されると `output=json` にします。`_profile_command` は `output == "json"` を machine 出力として扱います。
3. `show` はプロフィールをロードして `{"profile": ..., "revision": ...}` を組み立てます。`--effective` がある場合はさらに launch plan を計算し、`plan` を加えます。成功 JSON は一行で stdout に出力されます。JSON の文字列は Unicode のまま出し、`allow_nan=False` で非有限数を拒否します。

`--effective` の plan はプロフィールと参照先 run config を読み、設定値の出所、値の検証、実効 server/engine 引数を計算します。値の優先順位はコマンド指定、保存プロフィール、run config、`STRATA_BATCH_TELEMETRY` 環境変数（`batch_telemetry` のみ）、既定値です。例えば queue timeout に max queue がない場合や、run config 内の batch 指定とプロフィール override が競合する場合は失敗します。plan はサーバーを起動しません。

## 適用条件と副作用

- `--json` 自体は表示形式を切り替え、プロフィールを書き換えたりサーバーを起動したりしません。`--effective` を付けない経路はプロフィールをロードするだけで、参照先 run config は読みません。
- プロフィール名は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です。プロフィールは OS 別設定ディレクトリ（POSIX では既定で `$XDG_CONFIG_HOME/strata/profiles`、未設定時は `~/.config/strata/profiles`）にあり、`STRATA_PROFILE_DIR` で変更できます。
- profile load は対象が通常ファイルであること、1 MiB 以下であること、JSON/schema/ID/source path/override が有効であることを確認します。Windows などで権限エラーになった場合、ユーザー所有領域と判断できればアクセス権を一度修復して再読込することがあります。
- CLI 共通の起動処理は parser 実行前に `adopt_user_defaults()` を呼びます。ソース上、Windows で昇格実行時に以後作るファイルの owner/default ACL をユーザー向けに設定する処理です。プロフィール内容の保存ではありません。
- `--quiet` も one-shot parser で受理されますが、`--json` により `output=json` となるため quiet の人間向け出力捕捉経路には入りません。

## 出力とエラー

- 成功時: stdout に `{"schema_version":1,"ok":true,"profile":...,"revision":"..."}` を一行出します。`--effective` 時は `plan` が含まれます。
- 実行中の `ValueError`（プロフィール不正・未保存、effective plan 検証失敗など）と未処理の `OSError` は、通常の CLI 例外処理で JSON の `ok:false` と `error.code` / `error.message` に変換されます。`ProfileError` の終了コードはエラーごとに設定され、未保存プロフィール等はコード5、デフォルトの入力不正はコード2です。`profiles.load` と `read_run_config` は読込エラーを `ProfileError` に変換するため、プロフィール・run config の読込失敗は通常コード5です。その他の未処理 `OSError` はコード6です。
- parser が認識しない引数や値を伴う誤用は処理本体より前に `argparse` が usage/error を stderr に出し、通常は終了コード2となります。JSON エラー envelope にはなりません。

## 根拠

- 索引上のスコープと配置: `docs/cli/README.md` の `strata profile show` 項。
- parser の位置引数、`--effective`、`--output` と JSON alias の追加: `strata_cli/cli.py:77-80`, `strata_cli/cli.py:508-515`。
- alias の適用と共通出力 envelope: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2224-2236`。
- show のプロフィール読込、effective 条件と成功 payload: `strata_cli/cli.py:958-959`, `strata_cli/cli.py:968`, `strata_cli/cli.py:1015-1020`。
- プロフィール名・保存場所、schema/file validation と権限修復読込: `strata_control/profiles.py:38-55`, `strata_control/profiles.py:135-166`。
- effective plan の設定優先順位・相互検証・plan 組立: `strata_cli/cli.py:545-547`, `strata_cli/cli.py:745-779`, `strata_cli/cli.py:782-826`。
- 例外を JSON エラー・終了コードにする経路: `strata_cli/cli.py:2166-2193` の `_run` 例外処理、`strata_cli/cli.py:2226-2235` の parser 前処理。
- 共通起動時の Windows user defaults 処理: `strata_cli/cli.py:2217-2223`, `strata_control/private_files.py:349-380`。

調査範囲は指定 checkout の Python CLI と profile 実装です。Release 配布物や別 revision は照合していません。
