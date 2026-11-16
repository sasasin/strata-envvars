# `--preset`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--preset` |
| 別名 | なし |
| 値 | 保存済み launch preset の名前（`NAME`） |

## 役割

保存済みの launch 設定を読み込み、モデル、context、接続方式などを使って起動する。ほかの `strata launch` 設定オプションを同時に指定すると、指定した項目は今回の起動用に preset の値を上書きする。`--save-preset` も指定した場合は、起動設定をその名前で保存する。

## 使い方

```sh
# 既存の preset を読み込み、変更内容を確認する（起動・設定変更はしない）
strata launch --preset "Office" --plan

# 既存の preset で起動し、画面を使わず接続先を表示して戻る
strata launch --preset "Office" --no-tui

# 今回だけ context を上書きして起動する。元の preset は保存し直さない
strata launch --preset "Office" --context 128k --no-tui

# 上書きを含む今回の設定を別名で保存してから起動する
strata launch --preset "Office" --context 128k --save-preset "Office 128K" --no-tui
```

例の `Office` は既存の preset 名に置き換える。

## 値と既定値

- `--preset` は `NAME` を1つ取る。parser に型変換や列挙値の制約はない。オプションを重複して指定した場合の個別検証はなく、`argparse` の同名引数の通常の結果として最後の値が namespace に入る（parser 登録: `strata_cli/launch/cmd.py:82`）。
- 未指定時は空の `LaunchSettings` から設定を組み立てる。`--preset` 自体に既定名はない（`strata_cli/launch/cmd.py:206-212`）。
- 名前は小文字化し、ファイル名に使えない文字列を `-` に置き換え、連続する `-` をまとめ、先頭・末尾の `-` と `_` を除いてから、先頭が英字でなければ `l` を付け、48文字で切り詰める。この slug に `.json` を付けたファイルが読み込み先になる。表示上の名前と slug が異なっても、この規則で同じ保存先を参照し得る（`strata_cli/launch/settings.py:327-332`、`strata_cli/launch/store.py:35-36`）。
- 保存先は `STRATA_LAUNCH_PRESET_DIR` が設定されていればそのディレクトリ、そうでなければ profiles ディレクトリの隣の `launch-presets/`（`strata_cli/launch/store.py:27-32`）。

## 実行時の動作

1. `settings_from_args` が指定名の JSON を読み、`LaunchSettings` に復元する。保存設定があればその値が起点となり、同時指定した `--model`、`--context`、`--access` などの値で対応する項目を上書きする。preset 未指定なら初期設定から始める（`strata_cli/launch/cmd.py:206-212, 223-296`）。
2. `--preset` は選択済み設定があることを示すため、通常は最初の選択画面を開くのではなく、その設定で起動経路へ進む。対話端末では設定を起動前に表示する TUI monitor が開き、`--no-tui` では画面を使わず実行して接続先を表示する。`--plan` を付けると計画だけを出して終了する（`strata_cli/launch/cmd.py:803-825, 851-877, 897-903`）。
3. 実起動では選択に応じた launch profile（`launch-<slug>`）の設定を書き、engine とモデルの準備、tuning、server 起動へ進む。既に同じ選択で serving 中なら再利用し、異なる設定で同じ launch または port が使用中の場合は、`--restart` なしの非対話実行では拒否する（`strata_cli/launch/runner.py:638-639, 2030-2058, 2543-2582`）。
4. `--save-preset` がなければ preset の選択値自体は保存し直さないが、起動が正常終了した場合は `last_used` を更新して preset ファイルを書き戻す。`--save-preset` を指定すると、指定した保存名で preset を作成または置換し、`last_used` も更新する（`strata_cli/launch/cmd.py:914-918`、`strata_cli/launch/store.py:75-85, 139-144`）。

`--no-api-key` は保存 preset にあった API key も今回の設定から取り除く。反対に `--api-key` または `--api-key-env` と `--no-api-key` を併記した場合は、key を保持して警告する（`strata_cli/launch/cmd.py:271-284`）。

## 適用条件と副作用

- 指定名に対応する保存ファイルが必要。preset は端末の setup screens と共有され、保存項目に API key を含み得る。通常の書き込みは一時ファイル経由で置換され、POSIX では mode `0600` を試み、Windows では現在ユーザーだけに制限する処理を試みる（`strata_cli/launch/store.py:1-7, 39-60`）。
- 実起動時には選択に応じて server 用 profile と設定ファイルが更新され、engine 起動・モデル準備・tuning・port 使用が起き得る。`--plan` は `runner.plan()` の後に「変更なし」として終了し、実行処理には進まない（`strata_cli/launch/cmd.py:851-877`、`strata_cli/launch/runner.py:2543-2582`）。
- 他の launch flags は今回の設定に反映されるが、`--save-preset` を付けない限り、それらを preset の設定として保存しない。ただし前述の `last_used` は実起動の正常終了時に更新される（`strata_cli/launch/cmd.py:285-296, 914-918`）。
- `--preset` は `strata connect` にも同じ表記の別オプションがある。そちらは接続先情報の参照用で、この文書の対象ではない（`strata_cli/launch/cmd.py:157-168`）。索引でもコマンド階層ごとに別リンクである（`docs/cli/README.md` の `strata launch` 節および `strata connect` 節）。

## 出力とエラー

- 保存 preset が見つからない場合は `There is no saved preset called ...` と候補一覧または類似名を添えて失敗する。JSON が読めない場合、または最上位が object でない場合も `PresetError` として失敗する（`strata_cli/launch/store.py:88-103, 106-112`）。
- `run_launch` は `PresetError` と設定値の `ValueError` を失敗として扱う。human 出力では `strata: ...` を stderr に出し、終了コード 2。`--output json` の場合は `ok: false` とエラー内容を含む JSON を stdout に出す（`strata_cli/launch/cmd.py:710-721, 961-964`）。
- engine/server の起動失敗は `LaunchError` として文面・終了コード付きで返る。事前に launch 設定ファイルが書かれていて `--save-preset` を指定した場合、失敗時にもその preset を保存しようとする（`strata_cli/launch/cmd.py:901-913`）。

## 根拠

- `strata_cli/launch/cmd.py:73-83` — `strata launch` parser と `--preset NAME` の宣言。
- `strata_cli/launch/cmd.py:157-174` — `strata connect --preset` が別 parser scope であること。
- `strata_cli/launch/cmd.py:206-296` — preset 読込、他の引数との合成、API key / 保存名処理。
- `strata_cli/launch/cmd.py:803-825, 851-877, 897-918, 961-966` — 実行モード、計画終了、保存、失敗処理。
- `strata_cli/launch/store.py:27-36, 39-60, 75-103, 132-144` — 保存場所、private write、置換、読込、削除、最終使用時刻の更新。
- `strata_cli/launch/settings.py:327-332` — preset 名からファイル・profile に使う slug への変換。
- `strata_cli/launch/runner.py:638-639, 2030-2058, 2543-2582` — `launch-<slug>` profile、稼働中 server の扱い、実起動処理。
- 索引照合: `docs/cli/README.md` の `strata launch` 節にこの文書へのリンクがあり、`strata connect` 節には別の `--preset` 文書へのリンクがある。
