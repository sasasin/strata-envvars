# `strata ops run --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み profile の ID（英小文字で始まり、英小文字・数字・`_`・`-`、最大64文字） |

## 役割

実行する operator recipe と、その recipe が対象にする保存済み serving profile を指定する。`strata ops run` は recipe 名を位置引数 `NAME` で受け取り、`--profile` はその recipe の名前空間と対象 profile の両方を決める。

## 使い方

```sh
strata ops run restart --profile local
```

`local` profile に保存された `restart` recipe を実行する例。実行前の preview と同じ recipe/profile revision を要求する場合は、`--if-revision` と `--if-profile-revision` も指定できる。

## 値と既定値

- 値を1つ取る。parser では全 `ops` サブコマンドに `required=True` で定義されているため、省略すると引数解析に失敗する。既定値はない。
- `--profile` の parser 自体には型変換・choices・専用 validator はない。recipe のロード時に ID が検証され、1〜64文字、先頭は英小文字、残りは英小文字・数字・`_`・`-` に限られる。大文字、空文字、パス形式は有効な ID にならない。
- 指定 ID の profile ファイルが存在しない、通常ファイルでない、読めない、または内容が schema/ID/保存済み設定の検証に通らない場合は実行できない。

## 実行時の動作

1. parser は `--profile` を `a.profile` に格納する。`run` は `NAME` とともに `recipes.load(a.profile, a.name)` を呼び、profile 配下の recipe を読み込む。
2. profile ID は `strata_control.profiles.profile_dir()` 配下の `<ID>.json` を選ぶ。`STRATA_PROFILE_DIR` が設定されていればそのパスを使い、未設定時は Windows では `%APPDATA%/Strata/profiles`（`APPDATA` がなければユーザーディレクトリ以下）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定なら `~/.config/strata/profiles`）を使う。
3. recipe は同じ profile directory の `.ops/<ID>/<NAME>.json` から読み込まれる。保存済み profile の run config と override は、選択した recipe kind の処理に渡される。
4. recipe の種類は `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれか。成功・失敗を含む run 記録は同じ profile の `.ops/<ID>/.runs/` に作られる。したがって profile の選択は、recipe・対象設定・operation journal の分離境界にもなる。

## 適用条件と副作用

- `--profile` だけでは実行内容は決まらず、`NAME` が指す recipe の kind と params で決まる。`runtime.restart` は管理下の実行環境を再起動し、`engine.calibrate.measure` は engine を使った測定を行い report を新規作成する（この kind では毎回 `--exclusive` が必要）。`components.verify` は profile の run config を使って component を検査する。
- 実行前に recipe revision、profile revision、および指定された restart の owner/instance/source 条件を検査する。確認条件と現在値が合わない場合、recipe は実行されず失敗する。
- 実行開始時に profile revision と recipe intent を含む journal record を書き、実行後に terminal state と compact result を更新する。recipe 実行中に例外が起きた場合も journal を `failed` または `completion_unknown` に更新する。これは単なる読み取り指定ではない。
- profile、recipe、journal のファイルやディレクトリが不正、権限条件を満たさない、容量上限に達している場合は処理が失敗することがある。profile/recipe 保存先の作成・修復等の細部は各 helper の実装に依存する。

## 出力とエラー

- 人間向け出力は実行 operation の JSON。`--output json` の場合は `schema_version`、`ok`、`operation` を含む JSON を stdout に出す。
- 成功時の終了コードは `0`。recipe の実行結果が失敗なら result の `exit_code`、未設定なら `5` を返す。
- 捕捉された値エラーは `strata: <message>` を stderr に出し、例外の `exit_code`（未設定なら `2`）を返す。profile/recipe 不在や破損などの helper error は `ProfileError` としてこの経路に入る。
- `--exclusive` を calibration 以外の recipe に使うと `2` で失敗する。calibration recipe で `--exclusive` を付けない場合も失敗する。その他の種類固有の失敗条件は該当処理から返される。

## 根拠

- parser・必須指定・run 固有の関連条件: `terminal/strata_cli/cli.py:283-318`
- run dispatch、profile/name による recipe load、exclusive 条件、revision 条件、出力・終了コード: `terminal/strata_cli/cli.py:1461-1464`, `terminal/strata_cli/cli.py:1518-1534`
- profile directory、ID の形式、profile read/validation: `terminal/strata_control/profiles.py:25`, `terminal/strata_control/profiles.py:38-55`, `terminal/strata_control/profiles.py:120-132`, `terminal/strata_control/profiles.py:153-173`
- recipe kind、profile ごとの recipe path と値検証: `terminal/strata_control/recipes.py:28`, `terminal/strata_control/recipes.py:32-64`, `terminal/strata_control/recipes.py:93-114`
- preview/run の実処理と副作用: `terminal/strata_control/recipes.py:329-360`, `terminal/strata_control/recipes.py:363-439`
- operation journal の profile ごとの保存先、record 作成と終了状態: `terminal/strata_control/journal.py:47-63`, `terminal/strata_control/journal.py:321-361`, `terminal/strata_control/journal.py:364-378`
- CLI 共通エラー表示と終了コード: `terminal/strata_cli/cli.py:558-563`, `terminal/strata_cli/cli.py:2248-2265`

調査範囲は parser、CLI dispatch、profile/recipe/journal の実装です。同一 revision の CLI `--help` は実行していません。重複指定時の扱いなど Python `argparse` 自体の詳細は本書では仕様として断定していません。
