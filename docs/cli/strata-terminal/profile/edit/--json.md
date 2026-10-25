# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile edit` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `false`、指定時 `true` |

## 役割

成功・失敗の結果を機械処理向け JSON で出力します。`profile edit` が行う編集内容や保存方法は変更しません。

## 使い方

```sh
strata profile edit demo --json
```

`VISUAL` または `EDITOR` に編集プログラムを設定しておく必要があります。`demo` は既存の保存済みプロファイル名です。

## 値と既定値

値は不要です。`profile edit` 専用 parser に `--json` を直接書くのではなく、`profile_edit` を含む one-shot parser 群に `action="store_true"` として追加します。既定は argparse の `false` です。`main()` はこのフラグが立っている場合に `output` を `json` に設定します。既存の `--output json` でも同じ成功出力モードを選べます（`strata_cli/cli.py:96-98,508-515,2232-2236`）。

## 実行時の動作

フラグ指定時、成功結果は stdout に1行の JSON として出力されます。外側のオブジェクトに `schema_version: 1` と `ok: true` が入り、`profile`、`previous_revision`、`revision`、各変更の `changes` が含まれます。JSON は Unicode をそのまま出し、NaN/Infinity を許容しません。編集対象の値が変わらない場合でも成功レスポンスが返り、revision は変わらないことがあります（`strata_cli/cli.py:535-542,998-1005`; `strata_control/profiles.py:284-295`）。

`--json` は `--output` による形式指定と同じ one-shot 出力設定です。`--quiet` と併用しても JSON 出力は quiet 用の stdout 抑制処理に入らず、そのまま出力されます（`strata_cli/cli.py:2232-2244`）。

編集自体は保存済みプロフィールを一時 JSON に複製してエディタで編集し、終了後に JSON と profile schema を検証して保存します。`--json` によって一時ファイル、エディタ起動、永続化の有無は変わりません（`strata_control/profiles.py:349-379`）。

## 適用条件と副作用

`--json` 自体は出力形式だけを選びますが、対象コマンドは保存済みプロファイルを更新し得ます。編集成功時、内容に変更があれば旧版を履歴ディレクトリへ保存し、profile JSON を原子的に置き換えます。実行中の server を再構成する処理は `edit` の経路にはありません（`strata_cli/cli.py:998-1005`; `strata_control/profiles.py:266-295,349-379`）。

エディタは `VISUAL` を優先し、空または未設定なら `EDITOR` を使います。どちらも指定されていない場合、コマンドは失敗します。編集途中の JSON 不正、エディタの非ゼロ終了、保存前の revision 競合では一時 draft を残し、それ以外の終了経路では削除します（`strata_control/profiles.py:349-379`）。保存先は `STRATA_PROFILE_DIR` があればそのディレクトリ、なければ OS ごとの標準設定ディレクトリです（`strata_control/profiles.py:38-45`）。

## 出力とエラー

成功時は前述の JSON オブジェクトを stdout に出し、終了コード `0` を返します（`strata_cli/cli.py:535-542,998-1005`）。例外による失敗では、JSON モードなら stdout に `schema_version: 1`、`ok: false`、`error.code`、`error.message` を持つ JSON を出します。既定の profile エラーはコード `2`、profile 未保存・破損など一部は `5`、エディタ異常終了や revision 競合は `6` です。ファイル操作の `OSError` はコード `6` として扱われます（`strata_cli/cli.py:524-532,2166-2188`; `strata_control/profiles.py:30-35,150-166,363-375`）。

JSON フラグ自体を誤ったサブコマンド位置で使うなど parser が引数を拒否する場合は、`main()` の通常の例外 JSON 化より前に argparse が usage/error を出して終了します（`strata_cli/cli.py:2223-2236`）。

## 根拠

- parser と flag のスコープ: `strata_cli/cli.py:96-98,508-515`
- `--json` から `output=json` への正規化、quiet の分岐: `strata_cli/cli.py:2232-2244`
- profile edit の成功結果と `_success` の JSON 形式: `strata_cli/cli.py:535-542,998-1005`
- エラー JSON と終了コード処理: `strata_cli/cli.py:524-532,2166-2188`
- 編集用一時ファイル、エディタ選択、draft 保持、保存: `strata_control/profiles.py:349-379`
- profile の配置、load 検証、revision 保護と履歴保存: `strata_control/profiles.py:38-55,150-166,266-295`
