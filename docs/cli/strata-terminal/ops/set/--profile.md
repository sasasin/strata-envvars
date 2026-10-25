# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み profile の名前。省略不可。 |

## 役割

値を設定する recipe が属する serving profile を選びます。profile は既存の保存済み profile でなければなりません。recipe を選ぶ位置引数 `NAME` と組み合わせ、`--profile` は profile ごとの recipe 保存領域を決めます。`strata ops set` は recipe の値を提案・保存するだけで、その recipe の operation は実行しません。

## 使い方

```sh
strata ops set restart --profile my-profile startup_wait_s=240
```

`NAME` は recipe ID、最後の位置引数は `KEY=VALUE` 形式です。保存前に確認する場合は `--plan` を付けます。

```sh
strata ops set restart --profile my-profile startup_wait_s=240 --plan
```

## 値と既定値

- `--profile` は値を1つ取ります。parser では `required=True` であり、既定値はありません。
- profile 名は小文字英字で始まり、小文字英字・数字・`_`・`-` を使う最大64文字の形式です。profile ファイルが存在し、内容も有効である必要があります。
- profile ディレクトリは `STRATA_PROFILE_DIR` が設定されていればそのパス、Windows では `%APPDATA%/Strata/profiles`（`APPDATA` 未設定時はホーム配下）、Unix 系では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` です。
- recipe 名も小文字英字・数字・`_`・`-` のみで、profile と同じ識別子規則を使います。

## 実行時の動作

`--profile` は `ops` の全 action parser に追加されます。`set` の処理はこの値と recipe 名で recipe を読み込み、`assignment` を recipe 種別に対応する型へ変換・検証します。対応する割当ては次のとおりです。

| recipe 種別 | `KEY=VALUE` | 値の規則 |
| --- | --- | --- |
| `runtime.restart` | `startup_wait_s=N` | 整数。1〜600。 |
| `engine.calibrate.measure` | `report_dir=PATH` | 空でない絶対パス。NUL 文字不可。 |
| `components.verify` | `live=true` または `live=false` | 小文字の `true` / `false` のみ。ブール値へ変換。 |

通常実行では recipe ファイルを更新し、変更前の revision を履歴へ保存します。値が現在値と同じ場合は保存内容・revision を変えません。`--plan` を指定した場合は提案内容と `would_save` を出力し、recipe は保存しません。

recipe の保存先は profile ディレクトリ内の `.ops/<profile>/<recipe>.json` です。保存時は profile 単位の lock を使い、現在の recipe revision が読み込み時から変わっていないことを確認してから履歴の作成と atomic replacement を行います。

## 適用条件と副作用

- `--profile` で選んだ profile が未保存、壊れている、または profile 名の規則に合わない場合は失敗します。recipe もその profile の保存領域に存在し、対応する recipe 種別・パラメーター構造を持つ必要があります。
- `KEY=VALUE` の値の解釈は recipe 種別に依存します。不明なキー、種別と合わないキー、`=` がない割当て、空値は拒否されます。`components.verify` の `live` は `true` / `false` 以外を拒否します。
- `--plan` は `set` のみのオプションです。これは実行計画を実行する機能ではなく、変更候補を表示する dry run です。
- 通常実行の副作用は recipe JSON の更新と変更前 revision の履歴保存です。profile 本体・run config・稼働中 server はこのコマンドでは更新されず、operation も起動されません。
- POSIX では recipe ディレクトリ・ファイル・履歴に owner-only の権限要件があり、recipe ファイルは通常ファイルかつ64 KiB以下である必要があります。

## 出力とエラー

- 通常保存の成功時は既定の human 出力で recipe 名と旧・新 revision を表示します。`--output json` では JSON を出力します。`--plan` の結果は `--output` の値にかかわらず JSON で、提案 recipe、現在 revision、`would_save` を含みます。`--output json` の場合は共通の `schema_version` と `ok: true` も付きます。
- `--output` は `human`（既定）または `json` です。値は parser の `choices` で制限されます。
- 無効な割当てや recipe 検証エラーは human 出力では `strata: <message>` を stderr に出し、通常は終了コード2です。recipe/profile が欠落・不正なファイル、権限・安全性チェックの失敗はコード5、同時編集による revision 不一致はコード6となります。
- JSON 出力時のエラーは `schema_version`、`ok: false`、`error.code`、`error.message` を含む JSON です。

## 根拠

- parser と必須値・適用 scope: `strata_cli/cli.py:255-275`。
- profile 名の形式・保存ディレクトリの決定: `strata_control/profiles.py:25,38-45,48-55`。
- profile の読み込み・検証: `strata_control/profiles.py:120-132,150-166`。
- profile ごとの recipe ディレクトリ、識別子、ファイル安全性検査: `strata_control/recipes.py:32-64,180-196`。
- `set` の呼出し、`--plan` 分岐、通常保存: `strata_cli/cli.py:1391-1394,1423-1430`。
- `KEY=VALUE` の型変換と recipe 種別ごとの検証: `strata_control/recipes.py:93-114,278-296`。
- revision 競合検査、履歴保存、atomic replacement: `strata_control/recipes.py:214-237`; atomic replacement の実装: `strata_control/profiles.py:213-234`。
- 成功・失敗出力形式と CLI の例外処理: `strata_cli/cli.py:527-542,2166-2188`。

調査は指定 revision の checkout 内ソースに限定しました。安全に実行できる既存 CLI help や Release 配布物との照合は行っていません。
