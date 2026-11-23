# `strata launch --show-key`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--show-key` |
| 別名 | なし |
| 値 | 取らないフラグ（`store_true`、既定値 `false`） |

## 役割

実行中の `strata launch`、指定した保存済み preset、または setup.py が用意したモデル設定から API key を探し、見つかった鍵をそのまま表示します。鍵の確認だけを行い、launch の開始・停止や設定ファイルの書き換えはこの分岐では行いません。`strata connect` にも同名フラグがありますが、そちらはアプリ向け設定表示で鍵をマスクするかどうかを制御する別スコープです（索引の `connect` 節、および `terminal/strata_cli/launch/cmd.py:181`）。

## 使い方

```sh
# 実行中の launch の鍵、または該当する setup.py 設定の鍵を表示
strata launch --show-key

# 名前を指定した実行中 launch または保存済み preset の鍵を表示
strata launch --show-key --preset office

# setup.py が設定したモデルの鍵を選ぶ（複数候補がある場合）
strata launch --show-key --model iq3_xxs
```

鍵そのものが stdout に出るため、端末履歴・ログ・パイプの保存先に残さないよう出力先を選んでください。

## 値と既定値

`--show-key` は `action="store_true"` で、値も別名もありません。省略時は `false` となり、通常の launch 処理へ進みます。複数回指定しても真偽値のままです。`--preset NAME` と `--model NAME` は値を取る別オプションで、前者は parser 上で保存済み preset の起動指定、後者はモデル指定として定義されています（`terminal/strata_cli/launch/cmd.py:82-83,160-161`）。

## 実行時の動作

`run_launch` は通常の launch 設定処理に進む前に `a.show_key` を確認します（`terminal/strata_cli/launch/cmd.py:798-816`）。まず `launch_info(a.preset)` を呼び、`--preset` があればその名前に一致する実行中 launch を探し、なければ同名の保存 preset を読みます。preset を指定しない場合は検出された実行中 launch の先頭を選びます。選んだ launch の設定ファイルに有効な `api_key` がある場合はそれを使い、なければ preset に保存された鍵を使います（`terminal/strata_cli/launch/cmd.py:663-689,703-725`）。

その経路で鍵が得られない場合に限り、`--preset` が指定されていなければ setup.py が用意したモデル設定を検索します。`--model NAME` があればモデル ID の大文字小文字を区別しない完全一致または末尾一致で絞ります。候補の設定 JSON から `api_key` を読み、空文字と大文字小文字を区別しない `none` は鍵として扱いません（`terminal/strata_cli/launch/cmd.py:728-750,803-815`）。

`--output` の形式は成功時の鍵表示には適用されず、成功鍵は `_say` によって stdout に一行で出ます。setup.py 設定から鍵を得た場合、人間向け出力ではモデル名と設定ファイルの出所が stderr に追加されます。`--output json` でも成功時の鍵は平文のまま stdout に出ます（`terminal/strata_cli/launch/cmd.py:495-498,798-810`）。

## 適用条件と副作用

- `--preset NAME` を付けると、その preset 名に対応する実行中 launch または保存 preset を対象とします。指定した preset から鍵が取れない場合、setup.py 設定へのフォールバックは行いません。
- `--preset` なしで実行中 launch に鍵がない場合は、setup.py 設定の鍵を検索します。`--model` はこの検索の絞り込みに使われます。
- setup.py 設定に鍵があるモデルが複数見つかった場合、`--model NAME` で一つを指定する必要があります。候補の列挙に失敗した場合や設定ファイルが読めない場合、その候補は検索結果に含まれません（`terminal/strata_cli/launch/cmd.py:728-750,811-815`）。
- このオプション自体はファイルに書き込みませんが、鍵を stdout に平文で露出します。実行中 launch の状態・設定や preset、setup.py のモデル設定は読み取り対象です。

## 出力とエラー

- 鍵があれば鍵を stdout に一行出して終了コード `0` を返します。setup.py 設定由来の場合、人間向け出力では出所の説明を stderr に出します。
- 鍵がない場合は終了コード `5` です。preset 指定時は `There is no API key for that launch.`、preset なしでモデル指定があるときは該当モデルと鍵がない旨（実装の文面は `and no launch is running` を含みます）、複数候補時は候補名と `--model NAME` を使うよう案内するメッセージになります。
- `--output json` の失敗は `ok: false` とエラーコード・メッセージを含む JSON を stdout に出します。成功時は前述のとおり平文の鍵を出します（`terminal/strata_cli/launch/cmd.py:757-764,798-815`）。
- preset が破損して読み込めない場合は `PresetError` を通じて終了コード `2` のエラーになります（`terminal/strata_cli/launch/store.py:89-104`; `terminal/strata_cli/launch/cmd.py:1009-1010`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:80-83,155-161` — `launch` の `--preset` / `--model` と `--show-key` の parser 定義。`--show-key` は管理オプション群にあり、値を取らない。
- `terminal/strata_cli/launch/cmd.py:663-689,703-725` — 起動中 launch の状態確認と preset を含む鍵・設定情報の選択。
- `terminal/strata_cli/launch/cmd.py:728-750,798-816` — setup.py 設定へのフォールバック、モデル絞り込み、成功表示および鍵不在時の分岐。
- `terminal/strata_cli/launch/cmd.py:495-498,757-764,1009-1010` — stdout / stderr と JSON エラー出力、終了コード。
- `terminal/strata_cli/launch/store.py:89-104` — preset の読込、未存在・破損時の扱い。

調査時点の Strata checkout は `git status --short --branch` で `## main...origin/main` と表示され、作業ツリーに未コミット変更はありませんでした。CLI の `--help` は実行していません。
