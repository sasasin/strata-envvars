# `strata components engines --output`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--output` |
| 別名 | `--json`（共通 one-shot option。`--output json` の alias） |
| 値 | `human`、`json`、`jsonl` |

## 役割

導入済み engine の一覧を、人向け表示または機械処理向け JSON で出力します。このコマンドでは `jsonl` も一つの JSON object を出力します。逐次イベントを出す処理ではありません。

## 使い方

```sh
strata components engines --output json
strata components engines --output human
strata components engines --json
```

## 値と既定値

- `--output` は値を必須とし、parser が `human`、`json`、`jsonl` のみを受け付けます。未指定時は `human` です。選択肢外の値や値の省略は parser の引数エラーになります。
- `--json` は `--output json` の alias として登録され、指定時は出力形式が `json` になります。
- `--output` は明示的な反復禁止を設定していません。複数回指定した場合は argparse の標準 `store` 動作で最後の値が使われます。

## 実行時の動作

`strata_cli/update_cmd.py` の `_common()` が `--output` を三つの choices と既定値 `human` で定義し、`engines` parser に共通 option 群を追加します（`strata_cli/update_cmd.py:47-56,82-83`）。`strata_cli/cli.py` は `--json` を `--output json` の alias として登録し、解析後に `a.output` を `json` にします（`strata_cli/cli.py:508-515,2240-2253`）。`strata components engines` は `update_cmd.run()` に委譲されます（`strata_cli/cli.py:2136-2138`）。

実行時に `human` 以外なら machine output として扱います。`json` と `jsonl` はどちらも `schema_version: 1`、`ok: true` と engine 一覧データを含む一つの JSON object を stdout に出します（`strata_cli/update_cmd.py:233-239,358-367`）。`human` は合計容量、family ごとの一覧、各 engine の version・容量・backend と使用中／最新／非対応の印を表示します（`strata_cli/update_cmd.py:368-376`）。

## 適用条件と副作用

出力形式は一覧データ自体を変えません。engine の検索はローカルの component directory を読み取り、サイズ・対応可否・使用中状態などを列挙します。`list_engines()` はファイルを読むだけで、変更やダウンロードをしないと明記されています（`strata_control/engine_library.py:180-195`）。

この `engines` parser は `_common()` の他の option も受け付けます。`--components-dir` は一覧対象の root を選び、`--backend` は検出 hardware の backend を指定値に置き換えて対応可否の判定に影響します（`strata_cli/update_cmd.py:49-50,244-255`）。`--feed`、`--wait`、`--force`、`--model-config` は共通 parser で受理されますが、`engines` の分岐では feed や待機・更新処理へ進まず一覧を作るため、この一覧出力には使われません（`strata_cli/update_cmd.py:48-55,254-256,272-273,358-367`）。

`--quiet` は同じ one-shot parser に追加されます。人向け出力と併用した場合、成功時の stdout は捕捉されて表示されません。`json` / `jsonl` は machine output 経路を通るため、`--quiet` でも JSON が出ます（`strata_cli/cli.py:512-515,2253-2264`）。

## 出力とエラー

- `--output jsonl` でも一覧全体を一つの JSON object として出力します。イベント単位の JSON Lines にはなりません（`strata_cli/update_cmd.py:358-367`）。
- 選択肢外の値、または値なしは argparse の parse 段階で拒否されます。余分な引数も parse 段階でエラーになります（`strata_cli/cli.py:2240-2248`）。
- `update_cmd.run()` が処理する実行時エラーは、machine output なら `schema_version`、`ok: false`、`error.code`、`error.message` を持つ JSON を stdout に出し、human output なら `strata: ...` を stderr に出します（`strata_cli/update_cmd.py:237-242,307-319`）。一覧中の `OSError` などは CLI 共通処理に渡り、`OSError` は終了コード 6 として扱われます（`strata_cli/cli.py:2167-2189`）。

## 根拠

- parser と既定値・choices: `strata_cli/update_cmd.py:47-56,82-83`
- `--json` alias と option scope: `strata_cli/cli.py:508-515,2240-2253`
- command dispatch、machine output 判定、一覧の分岐と表示: `strata_cli/cli.py:2136-2138`; `strata_cli/update_cmd.py:233-256,358-376`
- 一覧の読み取り専用動作と返却データ: `strata_control/engine_library.py:180-195`
- `--quiet` と共通エラー処理: `strata_cli/cli.py:2167-2189,2253-2264`; `strata_cli/update_cmd.py:237-242,307-319`
