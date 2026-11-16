# `strata components remove --family`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--family` |
| 別名 | なし |
| 値 | `NAME`。エンジン family 名。省略可能 |

## 役割

削除対象を family で絞り込みます。同じバージョンのエンジンが複数 family にある場合に、対象を一意に指定できます。指定を省略すると全 family から検索し、複数候補が一致すれば曖昧として失敗します（`strata_cli/update_cmd.py:84-91`, `strata_control/engine_library.py:184-197`）。

## 使い方

```sh
# Qwen 系の 0.1.54 を削除する
strata components remove 0.1.54 --family qwen

# インストール済みの shape engine を指定して削除する
strata components remove 0.1.54 --family shape:q4_lite
```

削除対象は位置引数 `engine` にバージョンまたはフォルダー名で指定します。 family を指定しただけでは削除対象は決まりません（`strata_cli/update_cmd.py:88-91`, `strata_control/engine_library.py:184-197`）。

## 値と既定値

- 値は文字列 `NAME` で、既定値は `None`（未指定）です。短縮別名はありません（`strata_cli/update_cmd.py:88-91`）。
- `qwen` が通常の family です。`shape:<shape>` は shape engine の識別子で、`<shape>` は `shape_engine.valid()` の名前規則を満たす必要があります。名前は小文字英字で始まり、英小文字・数字・アンダースコアを含む所定の長さで、連続アンダースコアや予約済み component ID は不可です（`strata_cli/update_cmd.py:98-110`, `strata_control/engine_library.py:28-38`, `strata_control/shape_engine.py:29-33,80-87`）。family として構文上有効でも、その shape のエンジンがインストールされていなければ候補は見つかりません。
- parser の choices は `qwen` に加えて有効な shape 名と `retired.is_name()` が認識する旧 DeepSeek 名を受理します。ただし旧 DeepSeek 名は削除対象として提供されず、削除処理で拒否されます（`strata_cli/update_cmd.py:98-110`, `strata_control/retired.py:18-24,60-65`, `strata_control/engine_library.py:317-324`）。
- parser に `type` 変換や既定 family の補完はありません（`strata_cli/update_cmd.py:88-91`）。

## 実行時の動作

`strata components remove` は `update_cmd.run()` に渡され、エンジン一覧を読みます。`--family` はその一覧から対象 family のエントリーだけを選ぶフィルターです。続く `engine` はフォルダー名との完全一致を先に探し、一致しなければバージョンで検索します。family を省略した状態で複数エントリーに一致した場合は、候補フォルダー名を示して失敗します（`strata_cli/cli.py:2145-2147`, `strata_cli/update_cmd.py:333-334,419-440`, `strata_control/engine_library.py:184-197`）。

選ばれたエンジンが現在使用中、または実行中プログラムに使用されている場合は削除を拒否します。削除前にコンポーネントの更新ロックを取り、一覧を再取得して状態を確認します。削除時は対象フォルダーを `.deleting-<識別子>` にリネームしてから中身を消し、関連する更新状態と履歴を保存します。モデルファイルと設定、別 family のエンジンは削除対象外です（`strata_control/engine_library.py:139-149,317-366`）。

`--backend` は共通オプションとして併用できます。指定した backend は一覧作成時のハードウェア情報に使われますが、削除候補を family で絞るのは `--family` です（`strata_cli/update_cmd.py:47-56,310-317,419-440`, `strata_control/engine_library.py:98-122`）。

## 適用条件と副作用

- `--family` 自体はローカルのエンジン一覧の検索条件です。ダウンロードやモデル・設定の変更は行いません。エンジン本体の削除と、Qwen family の更新状態・履歴、または shape engine 側の pin・履歴の更新が起こります（`strata_control/engine_library.py:317-366`）。
- 現在使用中のエンジン、または稼働中プロセスが使用するエンジンは削除できません。ファイルが使用中などでリネームに失敗した場合は削除を中止し、何も変更していない旨を含むエラーになります（`strata_control/engine_library.py:139-148,334-342`）。
- 削除後の再帰削除は `ignore_errors=True` で行われます。削除できずに残ったファイルは `.deleting-*` に残り、次回の掃除対象になります（`strata_control/engine_library.py:337-344,373-375`）。

## 出力とエラー

- 成功時の人向け出力は削除したバージョンと解放サイズを表示します。JSON / JSONL 系の `--output` では構造化結果を出力します（`strata_cli/update_cmd.py:113-121,465-470`）。
- 対象がない、複数候補に一致する、現行エンジンまたは稼働中エンジンで削除不可、旧 DeepSeek 名などの拒否は `UpdateError` になります。通常出力では `strata: ...` を標準エラーへ、machine 出力では error object を標準出力へ出し、各エラーの code を終了コードにします。未導入・曖昧・削除拒否は code 2、リネーム時の OS エラーは code 6 です（`strata_control/engine_library.py:184-196,317-342`, `strata_cli/update_cmd.py:303-308,368-372`）。

## 根拠

- `strata_cli/update_cmd.py:84-110` — `use` / `remove` parser、`--family` の既定値・choices と動的 family 検証。
- `strata_cli/update_cmd.py:299-317,333-340,419-470` — CLI 実行分岐、family と engine の検索・削除処理、出力。
- `strata_control/engine_library.py:28-38,98-149,152-197,317-366` — family 識別、エンジン一覧・削除可否、検索、削除と状態更新。
- `strata_control/shape_engine.py:29-33,80-87` — shape 名の形式と予約名検証。
- `strata_control/retired.py:18-24,60-65` — 旧 DeepSeek 名の判定。
- `strata_cli/cli.py:2145-2147` — `components remove` を `update_cmd.run()` に委譲する分岐。
