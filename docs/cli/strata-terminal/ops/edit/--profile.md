# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops edit` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前。位置引数 `name` と組み合わせて編集対象の recipe を特定する |

## 役割

編集する operation recipe の所属 profile を指定します。この値は recipe の読み込み、保存先の選択、レシピの profile ID 検証に使われます。run config JSON のパスを受け取るオプションではありません。

## 使い方

```sh
strata ops edit --profile local restart
```

`local` profile の `restart` recipe をエディタで開きます。`--profile` と recipe 名はいずれも必須です（`strata_cli/cli.py:255-267`）。

## 値と既定値

- 値は必須の文字列で、既定値はありません。parser は選択肢や型変換を追加していません（`strata_cli/cli.py:264-267`）。
- profile 名は profile ID の規則に従い、小文字英字で始まり、小文字英字・数字・`_`・`-` を使います。recipe の profile 名と recipe 名にも同じ ID 検査が適用されます（`strata_control/profiles.py:48-55`、`strata_control/recipes.py:32-35`）。
- 指定 profile が読み込めない場合や recipe が存在しない場合は失敗します。recipe 読み込み時には JSON/schema、profile と ID の一致、recipe kind と params も検証されます（`strata_control/recipes.py:93-114`、`180-196`）。

## 実行時の動作

`strata ops edit` の処理は `recipes.edit(profile, name)` に委譲されます。まず現在の recipe と revision を読み、環境変数 `VISUAL`、次に `EDITOR` の順でエディタを選びます。どちらも設定されていない場合は編集せずエラーになります。エディタ指定は OS に応じた `shlex.split` で分割され、一時 JSON ファイルのパスを末尾引数として子プロセスを起動します（`strata_cli/cli.py:1419-1422`、`strata_control/recipes.py:299-312`）。

一時ファイルは recipe の内容で初期化され、エディタが正常終了すると JSON と recipe schema を検証して保存します。保存時に元の revision と現在の recipe を照合し、同時更新があれば競合として拒否します。変更がある場合は旧版を履歴へ退避し、新版を保存します（`strata_control/recipes.py:214-237`、`299-326`）。profile の recipe は profile 設定ディレクトリ内の `.ops/<profile>/<name>.json` に置かれます（`strata_control/recipes.py:38-64`）。

## 適用条件と副作用

- profile は先に保存済み profile として解決されます。recipe ディレクトリは profile ディレクトリ下の `.ops/<profile>` です。保存先の基底ディレクトリは `STRATA_PROFILE_DIR`、Windows の `APPDATA`、または Unix 系の `XDG_CONFIG_HOME`（未設定時はホームの `.config`）に依存します（`strata_control/recipes.py:38-59`、`strata_control/profiles.py:38-45`）。
- OS 環境変数の `VISUAL` / `EDITOR` がエディタ選択に影響し、エディタのプロセスが起動します（`strata_control/recipes.py:301-312`）。値は `--profile` の parser validation ではありません。
- 保存時は変更前 recipe の履歴ファイルを作成し、recipe 本体を更新します。recipe が変更されていなければ既存内容・revision を維持します（`strata_control/recipes.py:214-237`）。
- recipe ディレクトリ、recipe ファイル、履歴はシンボリックリンクや不正なファイル種別を拒否します。POSIX では owner-only 権限も要求されます（`strata_control/recipes.py:38-59`、`180-196`、`214-237`）。

## 出力とエラー

- 成功時は recipe、変更前 revision、変更後 revision を返し、human 出力では保存した recipe 名と revision の遷移を表示します。`--output json` を併用した場合は JSON 形式です（`strata_cli/cli.py:1419-1422`）。
- `VISUAL` / `EDITOR` が未設定または空、profile/recipe が不正、編集 JSON/schema が不正、エディタが非ゼロで終了、または編集中に recipe が変わった場合はエラーになります。非ゼロ終了や編集 JSON/schema 不正、revision 競合では draft の一時ファイルを残し、そのパスをエラー文に含めます。正常保存時は一時ファイルを削除します（`strata_control/recipes.py:299-326`）。
- CLI は `ValueError` を共通エラー経路で処理します。`ProfileError` の終了コードがあればそれを用い、なければ通常は 2 です（`strata_cli/cli.py:2166-2173`、`strata_control/profiles.py:30-35`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:255-267`
- `edit` の CLI 呼び出しと成功表示: `strata_cli/cli.py:1419-1422`
- recipe の profile/name 検証、保存場所: `strata_control/recipes.py:32-64`
- recipe の読み込み・検証: `strata_control/recipes.py:93-114`、`180-196`
- エディタ起動、一時ファイル、保存・履歴・revision 競合: `strata_control/recipes.py:214-237`、`299-326`
- profile ID と設定ディレクトリ: `strata_control/profiles.py:38-55`
- 索引上の階層と予定リンク: `docs/cli/README.md:517-525`
