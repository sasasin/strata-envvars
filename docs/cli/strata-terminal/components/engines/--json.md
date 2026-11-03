# `strata components engines --json`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（`2026-11-03` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると JSON 出力を要求する。 |

## 役割

導入済み engine の一覧を、人間向けの表ではなく JSON オブジェクトとして標準出力に出します。このコマンドは一覧を読み取るだけで、engine の導入・切替・削除は行いません。 (`strata_cli/update_cmd.py:82-83,358-376`; `strata_control/engine_library.py:180-195`)

## 使い方

```sh
strata components engines --json
```

## 値と既定値

`argparse` の `store_true` として、値なしで宣言されています。省略時は `False`、指定時は `True` です。短縮 alias はありません。コマンド parser には `--output` もあり、既定値は `human`、選択肢は `human` / `json` / `jsonl` です。 (`strata_cli/cli.py:508-515`; `strata_cli/update_cmd.py:82-83,47-56`)

## 実行時の動作

CLI 組み立て時に `--json` は `update_cmd.add_parsers()` が返す parser 群にも後付けされるため、`engines` parser で受理されます。解析後、`--json` が真なら `output` を `json` に設定します（`output=jsonl` と同時指定した場合は後述のエラーになります）。 (`strata_cli/cli.py:508-515,2239-2252`)

`strata components engines` は `update_cmd.run()` に渡され、`output` が `json` または `jsonl` なら machine 出力になります。共通 option `--backend` を指定すると、検出した backend をその値に置き換えてから一覧を作るため、engine 行の適合可否に影響します。`--components-dir` は走査する component folder を指定します。 (`strata_cli/update_cmd.py:47-56,244-251`) `_engines_command()` は `engine_library.list_engines()` の結果を `{"schema_version": 1, "ok": true, ...}` の JSON 1件として標準出力へ出し、終了コード `0` を返します。データには導入先 `components_dir`、engine family ごとの一覧 `families`、総容量 `total_bytes`、実行中モデルの有無 `serving` が含まれます。各 engine 行には版・backend・適合可否・使用中かどうか等が含まれます。 (`strata_cli/update_cmd.py:233-235,272-273,358-367`; `strata_control/engine_library.py:109-122,180-195`)

### `--output` との関係

`--output json` も同じ machine JSON 分岐を選びます。`--output jsonl` だけを指定した場合も `machine` 扱いですが、`engines` 分岐はイベント列ではなく単一の JSON オブジェクトを出力します。`--json --output jsonl` は `--json` が one-shot 専用である共通チェックにより終了コード `2` となり、JSON Lines 形式の失敗イベントを出します。 (`strata_cli/update_cmd.py:56,235,363-367`; `strata_cli/cli.py:2249-2252,830-835`)

## 適用条件と副作用

この option は `strata components engines` 用です。`--json` は `update_cmd.add_parsers()` が返す複数の one-shot parser に共通で追加されますが、索引ではコマンドごとの scope に分けています。 (`strata_cli/cli.py:508-515`; `docs/cli/README.md` の `components/engines` 節)

一覧生成は導入済み package の情報を走査し、各 engine の適合性・使用中状態などを計算します。`list_engines()` は「ファイルを読むだけで、変更・ダウンロードしない」と定義されています。 (`strata_control/engine_library.py:91-123,167-195`)

## 出力とエラー

成功時は標準出力に JSON オブジェクト1件を出し、終了コード `0` です。`list_engines()` が読み取った一覧を返せないなど、実行中の `ValueError` / `OSError` は CLI 共通処理で JSON の `{"schema_version": 1, "ok": false, "error": {"code": ..., "message": ...}}` として出力され、対応する終了コードが返されます。 (`strata_cli/update_cmd.py:363-367`; `strata_cli/cli.py:2167-2184,527-532`)

未知の引数など parser 段階のエラーは `parse_known_args()` 後に `ap.error()` で処理されるため、`--json` による実行時 JSON エラー形式への切替前に終了します。無効な引数での出力形式・終了コードは argparse の共通処理に従います。 (`strata_cli/cli.py:2239-2252`)

## 根拠

- parser と `--json` 後付け登録: `strata_cli/update_cmd.py:82-83,47-56`; `strata_cli/cli.py:508-515`
- フラグの適用、`--output jsonl` との競合、parser エラーの順序: `strata_cli/cli.py:2239-2252`
- コマンド dispatch、JSON 成功出力: `strata_cli/cli.py:2136-2138`; `strata_cli/update_cmd.py:233-235,272-273,358-367`
- engine 一覧の読取範囲・返却データ: `strata_control/engine_library.py:91-123,167-195`
- 実行時エラー形式: `strata_cli/cli.py:2167-2184,527-532`
