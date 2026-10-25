# `strata code sessions`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code sessions` |
| 実装 | `strata_cli/cli.py` |
| 位置引数 | `action`。現在は `list` のみ |

## 役割

共有 Desktop harness の coding session を扱う CLI のサブコマンドです。parser は `sessions` の下に `list` action を定義しています。ただし、この revision では共有 Desktop harness component が未実装で、`strata code` 系の処理はいずれも session 操作を実行せず、利用不可のエラーを返します（`strata_cli/cli.py:494-507,2162-2164`）。

## 使い方

```sh
# session 一覧を人向け形式で要求する（既定）
strata code sessions list

# JSON 形式を要求する
strata code sessions list --output json
strata code sessions list --json
```

いずれも現状は一覧を取得せず、共有 harness がないことを示して終了コード 5 を返します。`--workspace` や `--resume` は親の `code` parser で定義されていますが、現行の `code` dispatch はこれらを利用しません（`strata_cli/cli.py:494-497,2162-2164`）。

## 実行時の動作と出力

`action` は必須の位置引数で、選択肢は `list` のみです。`sessions` parser は `--output human|json` を受け付け、既定値は `human` です。`--json` は `--output json` の alias、`--quiet` は人向けの情報出力を抑える one-shot 共通オプションとして登録されています（`strata_cli/cli.py:505-515`）。

parser を通過しても、dispatch は `a.command == "code"` の場合に component 不在のエラーを返します。出力が `human` の場合は `strata: the shared Desktop harness component is not installed; coding sessions are unavailable` を stderr に出し、JSON 出力の場合は stdout に `schema_version: 1`、`ok: false`、エラーコード `5` とメッセージを含む JSON を出します。失敗コードは `_error` の戻り値から伝播します（`strata_cli/cli.py:527-532,2162-2164`）。したがって、現時点で session の読取、作成、ファイル変更などの session 副作用は確認できません。

CLI 全体では未知の引数は argparse の usage error となります。`--quiet` による捕捉は stdout を対象とし、component 不在時の human エラーは stderr に出力されます（`strata_cli/cli.py:2223-2237,2241-2248,527-532`）。

## 実行モードと注意点

`list` はソース上の parser が受け付ける唯一の action ですが、その一覧処理はこの revision では提供されません。利用者向け Terminal 文書も `strata code` は利用不可で終了コード 5 を返すと説明しています。Strata server に接続する coding app の利用方法としては `strata connect` を案内しています（`docs/TERMINAL.md:275-277`）。

調査対象 revision の CLI help は実行していません。parser 定義と dispatch を直接照合しています。テストには `strata code run` の不在 component による終了コード 5 を確認するケースがありますが、`sessions` 固有の成功経路を示す実装・テストは見つかりません（`tests/terminal/test_terminal.py:608-615`）。

## 関連文書

- [`strata code` の概要](../README.md)
- [`strata code run` の概要](../run/README.md)
- [`--help`（alias: `-h`）](--help.md)
- [`--json`](--json.md)
- [`--output`](--output.md)
- [`--quiet`](--quiet.md)
- [CLI 文書索引](../../../README.md)

## 根拠

- `strata_cli/cli.py:494-507` — `code` / `sessions` parser、`list` action、`--output` とその既定値。
- `strata_cli/cli.py:508-515` — `--json` alias と `--quiet` の登録。
- `strata_cli/cli.py:527-542,2162-2164` — human/JSON エラー出力と code command の不在 component 経路。
- `strata_cli/cli.py:2217-2248` — 引数解析、JSON alias 適用、quiet 出力処理。
- `tests/terminal/test_terminal.py:608-615` — `code run` の終了コード 5 を確認するテスト。
- `docs/TERMINAL.md:275-277` — 利用者向けの現状説明と `strata connect` の案内。
