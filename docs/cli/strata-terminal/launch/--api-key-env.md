# `--api-key-env`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--api-key-env` |
| 別名 | なし |
| 値 | 環境変数名 `NAME`。環境変数の内容を API key として使う |

## 役割

API key をコマンドライン引数に直接書かず、指定した環境変数から読み込んで launch の設定に渡します。parser は `NAME` を必須の値として受け取ります（`strata_cli/launch/cmd.py:119-126`）。

## 使い方

```sh
STRATA_LAUNCH_KEY='your-key' strata launch --model <model-name> --access lan --api-key-env STRATA_LAUNCH_KEY
```

`--model` と `--access` は例示用です。利用可能な model 名や access 種別は環境に合わせて指定してください。

## 値と既定値

- 値は環境変数名です。parser に既定値や専用の型変換・形式検証はなく、値を受け取らない場合は通常の `argparse` エラーになります（`strata_cli/launch/cmd.py:119-126`）。
- 指定名で `os.environ.get(NAME)` を行います。未設定または空文字なら `ValueError` となり、エラー文は「環境変数が空または未設定」と指定した名前を示します（`strata_cli/launch/cmd.py:258-262`）。
- 環境変数の値自体を trim したり、形式・長さを検証する処理はこの読込箇所にはありません。空文字以外の値が `api_key` に設定されます（同 `cmd.py:258-262`）。
- `NAME` に空文字を渡した場合は `if a.api_key_env` が偽となり読み込み処理を通りません。空の名前について、別の明示的な拒否処理は確認できません（同 `cmd.py:258-262`）。

## 実行時の動作

設定済み preset があればその値を基に CLI flags を重ね、`--api-key` の値を適用した後に `--api-key-env` の値を適用します。そのため両方を指定し、環境変数が有効なら環境変数側が優先します（`strata_cli/launch/cmd.py:197-203, 256-262`）。

読み込んだ値は `LaunchSettings.api_key` に入り、`--no-api-key` も同時に指定したときは警告を追加したうえで key を保持します。`--no-api-key` だけなら preset に保存されていた key も消します（`strata_cli/launch/cmd.py:258-269`）。`--access` が非 local で key がなく、明示的に key 無効化もしていなければ、後続の defaults 処理で既存 key の再利用または新規 key 生成が行われます（`strata_cli/launch/cmd.py:341-350`）。

実際に起動する場合、key は launch 用設定へ渡されます（`strata_cli/launch/runner.py:371-382`）。`--save-preset NAME` を使うと `LaunchSettings` 全体が preset JSON に保存され、そこには `api_key` も含まれます。したがって環境変数から読んだ key も保存対象です（`strata_cli/launch/cmd.py:788-790`、`strata_cli/launch/store.py:75-85`、`strata_cli/launch/settings.py:99,114-118`）。

## 適用条件と副作用

この値は launch の API key 設定に使われます。共有先の設定（`--access`）により key が不要な local 起動でも、指定値は settings に格納されます（`strata_cli/launch/cmd.py:252-269`）。実行が `--plan` なら plan 表示後に終了し、起動処理へ進みません。plan は key の実値ではなく `API key on` の状態のみを表示します（`strata_cli/launch/cmd.py:733-760`）。

通常の human 出力では起動後の key はマスク表示され、JSON 出力でも `api_key` は実値でなく `set` として出力されます（`strata_cli/launch/cmd.py:801-817`）。ただし `--save-preset` による preset 保存では実値が保存されるため、環境変数経由であっても保存先の扱いに注意してください（`strata_cli/launch/store.py:75-85`）。

## 出力とエラー

- 指定した環境変数が未設定または空なら `ValueError` を捕捉し、既定 human 出力では stderr に `strata: ...` を出して終了コード `2`、`--output json` では `ok: false` の JSON を stdout に出して同じコードを返します（`strata_cli/launch/cmd.py:636-641, 832-835`）。エラー文に環境変数の値は含まれず、名前が含まれます（同 `cmd.py:258-262`）。
- `--no-api-key` と key の併用時は「key を保持する」警告が通常出力に加わります（`strata_cli/launch/cmd.py:263-269, 761-764`）。

## 根拠

- parser と option scope: `strata_cli/launch/cmd.py:119-126`
- preset を基にした設定、key の適用・競合処理: `strata_cli/launch/cmd.py:197-203, 252-269`
- 非 local 共有時の key 補完: `strata_cli/launch/cmd.py:341-350`
- plan と起動時の出力・エラー処理: `strata_cli/launch/cmd.py:636-641, 733-760, 788-817, 832-835`
- 起動設定への key の反映: `strata_cli/launch/runner.py:371-382`
- preset の key 保存と表示用マスキング: `strata_cli/launch/store.py:75-85`, `strata_cli/launch/settings.py:99,114-118`
