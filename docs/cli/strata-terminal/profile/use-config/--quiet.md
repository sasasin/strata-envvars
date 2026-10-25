# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile use-config` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽スイッチ |

## 役割

成功時の human 向け案内を抑制します。`use-config` の設定変更や `--plan` の計画表示自体には影響しません。

## 使い方

```sh
strata profile use-config office --from-config /path/to/run.json --plan --quiet
```

この例は変更予定の human 表示を抑えて計画を確認します。実際に保存するときは `--plan` を外します。

## 値と既定値

値は不要です。指定すると `quiet=True` 相当になり、省略時は quiet が無効です。parser は `action="store_true"` で登録し、既定値に `argparse.SUPPRESS` を使うため、省略時は Namespace に属性自体を追加しません。CLI の共通処理は属性がない場合を `False` として扱います。追加の値検証はありません。【`strata_cli/cli.py:508-515,2236-2243`】

このオプションは `profile_source` を含む one-shot コマンド群へ共通登録されています。`use-config` ではサブコマンド名の後に指定します。別名はありません。【`strata_cli/cli.py:89-95,508-515`】

## 実行時の動作

`strata profile use-config` は `--from-config` で指定された run config を検証し、`--plan` がなければ保存済み profile の参照先を更新します。`--quiet` はこの処理の前後で標準出力を捕捉し、成功時に出力を表示しません。設定ファイルの選択、revision 確認、plan と保存の分岐は quiet の有無で変わりません。【`strata_cli/cli.py:958-985,2236-2243`; `strata_control/profiles.py:252-263,266-295`】

`--output json` またはその alias の `--json` を指定すると quiet でも JSON レコードを抑制しません。`main()` は JSON 出力を quiet 捕捉より優先し、`_success()` は machine モードで JSON を標準出力へ書きます。【`strata_cli/cli.py:513-515,535-542,2232-2243`】

## 適用条件と副作用

`--quiet` 自体は出力制御だけで、profile や run config の内容を変更しません。ただし通常の `use-config` は `--quiet` を指定しても profile を保存します。変更を行わない確認には `--plan` を併用します。plan と保存の動作は `--plan` によって切り替わります。【`strata_cli/cli.py:92,969-985`】

## 出力とエラー

quiet は human 出力を成功時に抑えますが、エラーは標準エラーに残ります。`use-config` 内で発生した `ValueError`（`ProfileError` を含む）は共通処理でエラー文として出力され、例外の終了コードがあればそれを返します。quiet 中に失敗し、すでに標準出力へ出ていた human 文がある場合は、その捕捉分を標準エラーへ書き戻します。捕捉できる量は末尾 64 KiB で、それを超えて切り詰めた場合は省略通知も標準エラーに出します。【`strata_cli/cli.py:527-532,2166-2173,2196-2214,2241-2248`】

profile がない、指定 run config を読めない、保存中に profile の revision が変わった、といった失敗経路は quiet によって無効化されません。run config は存在する通常ファイルであり、有効な `args` 配列などを持つ必要があります。【`strata_cli/cli.py:969-974`; `strata_control/profiles.py:150-166,252-263,266-295`】

## 根拠

- `strata_cli/cli.py:89-95` — `use-config` parser と `--from-config`、`--plan`、`--if-revision`、`--output` の宣言。
- `strata_cli/cli.py:508-515` — one-shot profile parser 群に `--quiet` と `--json` を追加する共通登録。
- `strata_cli/cli.py:958-985` — `use-config` の plan 表示と保存処理。
- `strata_cli/cli.py:535-542,2166-2173,2196-2248` — human/JSON 成功出力、例外出力、quiet 捕捉と失敗時の扱い。
- `strata_control/profiles.py:252-295` — run config の確認、revision 検証、profile 保存。
- `docs/TERMINAL.md:224-226` — one-shot の JSON と quiet に関する利用者向け説明。
