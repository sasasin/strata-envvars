# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False`、指定時は `True` |

## 役割

保存済み connection の `url`、`prefix`、`credential_env` のいずれか一項目を変更する候補を検証して表示し、ファイルには保存せず終了します。対象 connection の確認や、保存前に変更内容を確認する用途です。

## 使い方

```sh
strata connection set work prefix=/strata --plan
```

`work` は事前に `strata connection create` で作成した名前です。`KEY=VALUE` は `url`、`prefix`、`credential_env` のいずれか一つを指定します。`--plan` は `--if-revision`、`--output human|json`、または `--json` と併用できます。

## 値と既定値

`--plan` 自体は値を受け取りません。parser では `store_true` として定義され、未指定なら通常保存経路、指定すれば候補表示経路を選びます（`strata_cli/monitor_commands.py:86-94`）。重複指定を個別に拒否する処理はありません。

位置引数 `NAME` と `KEY=VALUE` は必須です。編集可能なキーは `url`、`prefix`、`credential_env` に限られます。`url` は HTTP(S) のサーバールートで、埋め込み認証情報・パス・query・fragment を含めず、localhost 等のローカル宛てでない HTTP は拒否されます。`prefix` は最大256文字の単純な `/path` セグメントで、`.` / `..` は不可です。`credential_env` は ASCII の環境変数名形式です（`strata_cli/connections.py:245-253`; `strata_cli/client.py:45-76`）。

## 実行時の動作

このオプションは `strata connection set` の parser にのみ定義されています。`strata_cli/cli.py` が connection parser 群を登録し（`strata_cli/cli.py:488-493`）、コマンド実行を `monitor_commands.run()` に委譲します（同 `2119-2165`）。

`--plan` の有無にかかわらず、まず `connections.propose()` が対象ファイルを読み込み、assignment のキーと値を検証して候補および読み込み時点の revision を返します。revision を `--if-revision` で指定した場合はこの後に比較され、不一致なら候補の出力や保存へ進みません（`strata_cli/monitor_commands.py:152-160`; `strata_cli/connections.py:245-253`）。

`--plan` を指定すると、候補、revision、`would_save`（現在値と候補が異なるか）を出力します。この分岐は `connections.save()` を呼ばないため connection ファイルを更新せず、保存ロックも取得しません（`strata_cli/monitor_commands.py:155-163`）。候補の検証と表示のため保存ファイルは読み取ります。値が現在値と同じなら `would_save` は `false` です。

出力は既定で human 形式、`--output json` または `--json` では JSON 形式です（`strata_cli/monitor_commands.py:91-94,162-163,167-175`）。`--quiet` は human 形式で stdout の情報出力を抑制します。JSON 出力時は quiet による抑制は行われません（同 `168-175`）。

## 適用条件と副作用

既存の connection が必要です。`propose()` は対象を読み込むだけなので、存在しない名前や不正な保存データは失敗します（`strata_cli/connections.py:128-146,245-253`）。

計画表示自体は設定ファイルを書き換えません。ただし読み込み後、`would_save` の計算で現在のファイルをもう一度読みます。並行更新がある場合、表示される候補・revision と `would_save` の比較対象が同一時点でない可能性があります。plan 実行後に通常実行する場合、通常実行側で改めて候補を読み込み直します。

## 出力とエラー

成功時は終了コード0です。human 出力では JSON と同じ payload から `schema_version` と `ok` を除いた候補 connection、revision、`would_save` が表示されます。machine 出力では `schema_version: 1`、`ok: true` を含む JSON が stdout に出ます（`strata_cli/monitor_commands.py:155-164`）。

無効なキー、形式不正の値、URL/prefix の検証失敗などは `ConnectionError` として伝播し、既定では終了コード2です。対象 connection が存在しない、保存ファイルが不正・非 private などの場合は終了コード5です。指定した `--if-revision` が読み込み時点の revision と一致しない場合は、メッセージ `connection changed since preview; inspect it again` と終了コード6で失敗します（`strata_cli/connections.py:47-56,128-146,245-253`; `strata_cli/monitor_commands.py:152-154,231-240`）。人向けエラーは `strata: ` を付けて stderr、JSON エラーは stdout に `ok: false` と error 情報を出します（`strata_cli/monitor_commands.py:124-129,231-236`）。

## 根拠

- option 定義、引数、共通出力 option: `strata_cli/monitor_commands.py:75-94`。
- parser 登録と CLI 実行委譲: `strata_cli/cli.py:488-493,2119-2165`。
- 候補の生成、revision 条件、plan/save 分岐と成功出力: `strata_cli/monitor_commands.py:140-164`。
- connection の読込、検証、編集可能キー、値検証: `strata_cli/connections.py:97-114,128-146,245-253`、`strata_cli/client.py:45-76`。
- エラー出力と終了コードの扱い: `strata_cli/monitor_commands.py:124-129,231-240`。
- 調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。確認したのはソース checkout と文書内の索引・調査規約です。別途ビルド済み CLI の help および Release 配布物との比較は行っていません。
