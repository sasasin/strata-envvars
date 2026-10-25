# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops edit` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ出力形式を選ぶ別オプション） |
| 値 | `human` または `json` |

## 役割

編集する operator recipe の保存処理は変えず、成功・失敗の結果を人向け表示か JSON で出力します。省略時は `human` です。parser は `ops` の各サブコマンドに `--output` を登録しており、この文書では `edit` スコープの意味を説明します（`strata_cli/cli.py:255-267`）。

## 使い方

`local` profile にある `restart` recipe を `$VISUAL`（未設定なら `$EDITOR`）で開き、成功結果を JSON で受け取る例です。

```sh
strata ops edit restart --profile local --output json
```

recipe がまだなければ、先に `strata ops init --profile local` などで作成します。`name` と必須の `--profile` は位置引数・オプションで指定します（`strata_cli/cli.py:262-267`）。

## 値と既定値

- 受理する値は `human` と `json` のみです。既定値は `human` で、ほかの値は `argparse` が引数エラーとして拒否します（終了コード 2。`strata_cli/cli.py:266-267,2223-2231`）。
- `--json` は全 `ops` one-shot parser に追加される alias で、実行前に `--output json` と同じ値へ設定します。`--output` 自体に短縮別名はありません（`strata_cli/cli.py:508-515,2232-2235`）。
- 値は一つの parser 引数です。複数回指定した場合は通常の `argparse` の扱いとなり、最後に解析された値が使われます。

## 実行時の動作

`human` では、保存成功後に `Saved recipe <name>: <旧 revision> -> <新 revision>` を stdout に出します。`json` では、成功時に1行の JSON を stdout に出し、`schema_version: 1`、`ok: true`、`recipe`、`previous_revision`、`revision` を含めます（`strata_cli/cli.py:1391-1394,1419-1422,535-541`）。recipe 内容が変わらなかった場合、保存関数は現 revision を返して履歴・recipe ファイルを書き換えませんが、CLI は同じ成功形式を返します（`strata_control/recipes.py:214-225`）。

`--output json` は編集を dry run にしません。recipe を実際に編集するには `$VISUAL` または `$EDITOR` が選ばれて起動し、その終了後に JSON draft が検証・保存されます。環境変数値は `shlex.split` で argv に分割され、末尾に一時 JSON ファイルのパスを付けて実行します。シェル経由ではありません（`strata_control/recipes.py:299-318`）。

## 適用条件と副作用

- `--output` の選択は `edit` 成功後の結果形式に適用されます。対象 recipe は指定 profile の `.ops/<profile>/<name>.json` から読み込まれます。profile と recipe 名は小文字英字で始まり、小文字英字・数字・`_`・`-` を使う最大64文字の識別子です（`strata_control/recipes.py:32-64`; profile の格納場所は `strata_control/profiles.py:38-55`）。
- 編集用一時ファイルを recipe directory に作り、現在の recipe を JSON として書き込みます。検証を通って内容が変わった場合は、ロックと revision 照合の後、従来版を履歴に保存し、新しい recipe を atomic に置き換えます（`strata_control/recipes.py:299-326,214-237`）。
- 保存可能な recipe は `runtime.restart`、`engine.calibrate.measure`、`components.verify` の型付き schema に限られ、recipe ID・profile・schema version・params の型や必須キーも検証されます（`strata_control/recipes.py:28-29,93-114`）。
- POSIX では profile directory、recipe directory、recipe file の owner-only 権限も検査されます。recipe file は通常ファイルで64 KiB以下である必要があります（`strata_control/recipes.py:38-59,180-196`）。
- `--quiet` を併用すると human 成功出力は抑制されます。JSON は機械出力として抑制されません（`strata_cli/cli.py:513-515,2236-2247`）。

## 出力とエラー

- `json` の失敗は stdout に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式で出ます。`human` の失敗は `strata: ...` を stderr に出します（`strata_cli/cli.py:527-532,2168-2188`）。
- `$VISUAL` / `$EDITOR` が未設定、空白だけ、recipe の読込・validation 失敗などは `ProfileError` となり、通常は終了コード 2（または例外に設定されたコード）です。editor が非0で終了した場合はコード 6 で一時 draft を残します（`strata_control/recipes.py:299-315`; `strata_control/profiles.py:30-35`; `strata_cli/cli.py:2168-2173`）。
- editor 起動後の JSON parse または recipe validation に失敗すると、draft を残して `invalid recipe edit (...)` と報告します。recipe が編集中に変更され revision が一致しない場合も保存を拒否し、コード6で draft を残します（`strata_control/recipes.py:214-225,316-326`）。一方、正常に完了した場合は一時ファイルを削除します（同 `:323-326`）。
- `--output json` でも editor 自身の stdout/stderr は CLI の編集処理ではリダイレクトされません。editor 起動後に CLI が出す結果 JSON と混ざらないよう、呼び出し側で editor の出力先に注意してください（`strata_control/recipes.py:307-318`）。

## 根拠

- `strata_cli/cli.py:255-267,508-515` — `ops edit` の parser、`--output` と `--json` / `--quiet` の登録。
- `strata_cli/cli.py:1391-1422,527-541,2168-2188,2232-2247` — `edit` の呼び出し、成功・失敗の出力、終了コードと quiet の処理。
- `strata_control/recipes.py:28-29,32-64,93-114,180-196,214-237,299-326` — recipe の識別・検証、読み書き、revision 照合、editor と一時 draft の処理。
- `strata_control/profiles.py:30-45` — `ProfileError` の終了コードと profile 保存先の決定。

調査制約: 同 revision の CLI `--help`、Release artifact、Windows 実行時の editor 挙動は確認していません。この文書は指定 revision の parser と実装に基づきます。
