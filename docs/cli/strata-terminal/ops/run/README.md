# `strata ops run`（保存済みオペレーションの実行）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |

## 役割

指定したプロファイルに保存された型付きレシピを読み込み、その種類に対応する Strata の処理を実行します。レシピに任意のシェルコマンドや実行可能な文字列を保存する仕組みではありません。現行ソースで受理される種類は次の3つです。

| レシピ種類 | 実行内容 | 主な影響 |
| --- | --- | --- |
| `runtime.restart` | 保存プロファイルの稼働インスタンスを再起動 | 現在のインスタンスを停止・排出し、新しいインスタンスを起動します。 |
| `engine.calibrate.measure` | エンジンの decode 校正測定 | エンジン測定を実行し、新しいレポートを書きます。run config は変更しません。結果の適用は別のレビュー手順です。 |
| `components.verify` | インストール済みコンポーネントを検査 | 読み取り専用です。レシピの `live=true` の場合はホスト GPU 情報も照会します。 |

コマンドはレシピ名と必須の `--profile` を受け取ります。レシピの作成・初期化には [`strata ops`](../README.md) の `init` / `create` を使い、実行前には `plan` で対象と事前確認の結果を確認してください。計画表示は実行を行いません。

## 基本的な使い方

```sh
# 指定プロファイルの既定レシピを初期化
strata ops init --profile workstation

# 登録されたレシピを確認
strata ops list --profile workstation

# restart レシピの事前確認（実行しない）
strata ops plan restart --profile workstation

# 計画を確認した後に実行
strata ops run restart --profile workstation

# 実行履歴を確認し、必要なら個別結果を読む
strata ops runs --profile workstation
strata ops result OPERATION_ID --profile workstation
```

`workstation` と `OPERATION_ID` は実際に作成したプロファイル名と、履歴に表示された operation ID に置き換えてください。初期化される既定レシピは `restart`（`runtime.restart`）、`calibrate`（`engine.calibrate.measure`）、`check`（`components.verify`）です。

## 実行モードと結果

- `strata ops plan NAME --profile PROFILE` は種類ごとの事前確認を行い、実行効果を表示します。restart では現在の runtime 状態、calibration ではコンポーネント事前確認、components 検証では検査レポートを確認します。計画の `would_execute` は false です。
- `strata ops run NAME --profile PROFILE` は選択レシピの実装を実行し、operation ID と結果を表示します。正常終了時の終了コードは 0、処理結果が失敗なら結果内の終了コード（未指定時は 5）を返します。
- `--output human` が既定です。run の人向け出力は operation の JSON 表示です。`--output json` または alias の `--json` は `schema_version`、`ok`、`operation` を含む一行 JSON を stdout に出します。これらは一回限りの出力です。
- `--quiet` は共通 one-shot parser で受理されます。人向け出力を抑制し、失敗時に捕捉した説明を出します。JSON 出力では JSON を維持します。

完了・失敗した operation はプロファイルごとのローカル journal に記録されます。`ops runs` で一覧を、`ops result OPERATION_ID` で個別記録を確認できます。中断などで journal に running 状態が残った場合、結果取得時には完了を確認できない状態として扱われます。記録だけでは処理が現在も動いているか、停止済みかは確定できません。

## 種類ごとの動作と注意点

### `runtime.restart`

`startup_wait_s` を使って保存プロファイルを再起動します。既定レシピの待機値は 300 秒です。plan が表示する現在の owner ID、instance ID、profile revision、候補 run config の SHA-256 は、確認内容を固定するための run 引数として渡せます。指定した revision や ID、digest が計画後に変わっていれば実行を拒否します。

```sh
strata ops plan restart --profile workstation
strata ops run restart --profile workstation \
  --if-revision RECIPE_REVISION \
  --if-profile-revision PROFILE_REVISION \
  --if-owner-id OWNER_ID \
  --if-instance-id INSTANCE_ID \
  --if-source-sha256 SOURCE_SHA256
```

ID と digest の各値は plan 出力から取得します。owner と instance の一方だけを渡すことはできません。source digest や owner/instance の前提条件は restart レシピ専用です。restart 自体は現在のインスタンスを drain して新しいインスタンスを起動する処理なので、状態を確認せずに実行しないでください。

### `engine.calibrate.measure`

このレシピは校正測定を実行し、設定された report directory に新しい `calibration-<UUID>.json` を作成します。測定レシピでは、計画後の実行ごとに `--exclusive` が必須です。これは利用者によるデバイス排他の確認であり、CLI が無関係な GPU プロセスすべてを排除する保証ではありません。校正結果の適用・rollback はこの run の範囲外です。

```sh
strata ops plan calibrate --profile workstation
strata ops run calibrate --profile workstation --exclusive
```

### `components.verify`

コンポーネントの検査結果を返し、ファイルを書きません。レシピの `live` 値が true のときに限り、ホスト GPU の照会も行います。検査結果の `ok` が false の場合、run は失敗扱いとなります。

## エラーと制約

- `--profile` は必須で、レシピ名も `run NAME` の位置引数として必須です。未知の引数や不足した引数は argparse が拒否します。
- レシピまたはプロファイルが plan 後に変わった場合、期待値との不一致として拒否します。calibration レシピで `--exclusive` がない場合、または別種類に `--exclusive` を指定した場合もエラーです。
- 人向けエラーは stderr に `strata: ...` と表示され、machine output では `ok: false` とエラー情報を含む JSON になります。通常の入力・事前条件エラーは主に終了コード 2 または 6、保存領域や操作失敗はコード 5 等を返します。中断や完了状態が確定できない失敗では 130 等になり得ます。
- plan と run はプロファイル設定やファイル状態に依存します。OS ごとの権限・ACL 動作、実機での GPU/engine の動作、Release 配布版の差はこのソース読解では検証していません。

個別オプションの説明は [索引](../../../README.md) の `strata ops run` 節にある各文書を参照してください。関連コマンドは [`strata ops plan`](../plan/README.md)、[`strata ops runs`](../runs/README.md)、[`strata ops result`](../result/README.md)、[`strata runtime restart`](../../runtime/restart/README.md)、[`strata engine calibrate`](../../engine/calibrate/README.md)、[`strata components verify`](../../components/verify/README.md) です。

## 根拠

- `strata_cli/cli.py:255-290` — `ops` 階層、`run` の位置引数、必須 `--profile`、出力と run 固有オプションの parser 定義。
- `strata_cli/cli.py:508-515` — `--json` と `--quiet` を one-shot parser 群（ops を含む）に追加。
- `strata_cli/cli.py:1391-1464` — plan/run の dispatch、種類別の引数転送、出力形式と終了コード。
- `strata_control/recipes.py:1-5,28-35` — 型付きレシピであり、任意コマンド文字列を保持しないこと、対応する種類と名前の規則。
- `strata_control/recipes.py:329-360` — 種類別の plan と「実行しない」計画結果。
- `strata_control/recipes.py:363-438` — revision 確認、exclusive 条件、journal 開始、restart・校正・検証の実行。
- `strata_control/journal.py:247-273,276-313` — run 結果と一覧の読み取り、実行記録の保持・上限処理。
- `strata_cli/cli.py:527-542` — human / machine の成功・エラー出力規則。
