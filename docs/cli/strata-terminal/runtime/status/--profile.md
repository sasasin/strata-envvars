# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime status` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済みプロファイル名。必須。 |

## 役割

照会する管理対象ランタイムをプロファイル名で指定します。指定名はランタイム状態ファイルの識別に使われます。profile の設定値や参照先 run config を読み込んで状態を判定するオプションではありません（`strata_control/management.py:231-234`、`strata_control/runtime.py:444-455`）。

## 使い方

```sh
strata runtime status --profile local
```

JSON で結果を得る場合:

```sh
strata runtime status --profile local --output json
```

## 値と既定値

- 値は省略できません。parser は `required=True` で受理し、値の型変換や選択肢指定はありません（`strata_cli/cli.py:213-215`）。
- 値は `strata runtime` の各操作で使う保存名です。先頭は小文字英字、続きは小文字英字・数字・`_`・`-`、長さは最大64文字です。パス形式や `.json` の参照は受け付けません（`strata_control/runtime.py:95-98`、`strata_control/profiles.py:25`）。
- 既定値はありません。profile 名が形式に合わない場合は `ProfileError` になります。形式に合う名前でも対応する profile 定義が存在しない場合、status は profile 定義を検査せず、ランタイム状態が見つからなければ `stopped` を返します（`strata_control/management.py:199,231-234`、`strata_control/runtime.py:444-447`）。

## 実行時の動作

`--profile` の値は runtime 操作へそのまま渡され、状態ファイルの名前と照合に使われます。状態がなくてもエラーにはせず、`ok: true` / `state: "stopped"` を返します。状態ファイルがあれば owner の lease を調べ、owner が稼働中なら秘密 token を使ってローカル制御チャネルへ `status` 要求を送ります（`strata_cli/cli.py:1345-1356`、`strata_control/management.py:231-234`、`strata_control/runtime.py:444-455,402-441`）。

owner が応答した状態には、host/child PID、owner ID、profile revision、shutdown timeout などが含まれ、子プロセスの停止・ready 検査に応じて `stopped`、`starting`、`ready`、`failed` などが返ります（`strata_control/runtime.py:933-969`）。status 要求を処理する際、owner が ready file の instance をまだ検証していなければ、非同期で readiness 検証を始めます。検証はローカル API の telemetry を確認し、モデルがロード済みなら `/v1/chat/completions` へ1 token の生成要求も送ります。モデルが未ロードならこの経路ではロードせず、`unloaded` 状態を返します（`strata_control/runtime.py:948-969,904-917`、`strata_control/readiness.py:84-86,101-120,121-143`）。status は start/verify コマンドそのものを開始せず、確認用の一時的な lease lock と制御要求を行います。ただし状態パスの解決時にランタイムディレクトリを作成し、Windows ではアクセス制御を確認・修復する経路があります（`strata_control/runtime.py:101-129,205-216,285-294`）。

`--output` の既定値は `human` で、プロファイル名と状態、存在する場合は instance ID・API URL・検証情報・エラーを表示します。`--output json` または同一 parser に追加される `--json` を指定すると、`schema_version: 1` を含む JSON オブジェクトを出力します（`strata_cli/cli.py:508-515,1331-1373`）。`--quiet` は human 出力を成功時に抑え、失敗時は捕捉した出力を stderr に出します。JSON 出力時には quiet の捕捉経路に入りません（`strata_cli/cli.py:508-515,2232-2248`）。

## 適用条件と副作用

- 管理ランタイムのローカル制御 transport が利用可能な Windows、または AF_UNIX 対応 POSIX が前提です。それ以外ではランタイムディレクトリ準備時に拒否されます（`strata_control/runtime.py:88-92,101-112`）。
- 保存済み profile の設定は照会対象選択に使われず、profile の存在・source config の有効性も確認しません。ランタイム状態ファイルと owner の lease/制御チャネルが照会基準です（`strata_control/management.py:231-234`、`strata_control/runtime.py:444-455`）。
- status 自体はサーバーを起動・停止せず、未ロードのモデルもロードしません。一方、owner が ready file を未検証なら、ローカル API の telemetry 確認と、モデルがロード済みの場合の1 token 生成が非同期に走り得ます。またローカル状態ディレクトリの作成・Windows ACL 修復、状態ファイルの読み取り、owner lease の確認、owner への status 要求も発生し得ます（`strata_control/runtime.py:101-129,215-235,285-294,402-455,948-969`、`strata_control/readiness.py:101-143`）。

## 出力とエラー

- 対応する状態記録がない場合や owner lease のファイルがなくなった場合は `stopped`、owner host の lease が失われた場合は `ok: false` / `state: "stale"` / `error: "owner_host_lost"` / 終了コード 6 を返します（`strata_control/runtime.py:444-455`）。
- 制御チャネルが利用できない場合は終了コード 3、応答 timeout は 8、不正・過大な応答は 6 の `ProfileError` になります。CLI は human 時に `strata: ...` を stderr へ、JSON 指定時にエラー JSON を stdout へ出します（`strata_control/runtime.py:402-440`、`strata_cli/cli.py:2166-2183`）。
- 状態ファイルの権限・形式が不正、または読み取り不能な場合は終了コード 5 のエラーになります。無効なプロファイル名は既定の終了コード 2 です（`strata_control/runtime.py:215-235,95-98`、`strata_control/profiles.py:30-35`）。
- `failed` や `stale` のように結果オブジェクト自体が `ok: false` の場合も、CLI はそのオブジェクトを表示して `exit_code` を返します。汎用例外としてのエラー表示とは出力経路が異なります（`strata_cli/cli.py:1359-1373`）。

## 根拠

- parser 定義と `--output`: `strata_cli/cli.py:213-215`
- `--json` / `--quiet` の追加と適用: `strata_cli/cli.py:508-515,2232-2248`
- runtime コマンドへの振り分け・引数転送・表示: `strata_cli/cli.py:2158-2159,1331-1373`
- profile 名の形式と runtime status 分岐: `strata_control/runtime.py:95-98,444-455`、`strata_control/profiles.py:25`
- 状態ディレクトリ・state file・lease・RPC: `strata_control/runtime.py:101-129,205-235,285-294,402-440`
- owner が返す状態情報: `strata_control/runtime.py:933-969`
- status を呼び出す管理層: `strata_control/management.py:188-201,231-234`
