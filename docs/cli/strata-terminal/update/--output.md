# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

更新確認・更新処理の出力形式を選びます。`--output` は `strata update` と `strata components update` / `strata components rollback` に共通の parser helper で登録されますが、この文書の対象は索引上の別スコープである `strata update` です。

## 使い方

```sh
strata update --check --output json
```

署名付き更新 feed を読み取り、変更候補を JSON で出力します。更新のダウンロードは行いません（`strata_cli/update_cmd.py:203-209`）。

## 値と既定値

- 省略時は `human` です。
- `human` は通常の人向け表示、`json` は一回の結果を JSON で出力、`jsonl` は処理中イベントを JSON Lines 形式で出力します。
- `argparse` の `choices` により、他の値は受理されません。値を省略した場合も parser の usage error になります（`strata_cli/update_cmd.py:30-40`）。
- `argparse` の通常の単一値引数であり、複数回指定時は最後に指定した値が採用されます。

## 実行時の動作

- `human` では更新元を示す見出し、結果概要を出力します。ダウンロード進捗は TTY では同じ行を更新し、非 TTY では進捗が 10 ポイント以上進んだ時または完了時に出力します。ダウンロード以外の phase と待機メッセージも表示します（`strata_cli/update_cmd.py:62-84, 211-224`）。
- `json` と `jsonl` はどちらも machine output として扱われ、人向けの進捗・phase 表示を抑制します。`json` は `--check` の report、または更新処理の結果全体を `schema_version` と `ok` を含む JSON で出力します（`strata_cli/update_cmd.py:63-71, 203-215`）。
- `jsonl` は updater が通知するイベントごとに `{"schema_version": 1, ...}` を stdout に1行ずつ flush し、処理終了時には最終結果 JSON も出力します。したがって最後の行はイベント行と同じ形とは限らず、機械処理側はイベントと結果を区別する必要があります（`strata_cli/update_cmd.py:62-69, 213-215`）。
- `--json` は共通 one-shot parser 群に後付けされるフラグで、指定時は `--output json` 相当に `a.output` を変更します。`--output jsonl --json` の組合せは one-shot 出力との不整合として拒否されます（`strata_cli/cli.py:510-515, 2232-2235`）。
- `--quiet` も共通 parser で追加されます。`--output human --quiet` では stdout を一時捕捉し、処理が失敗した場合は捕捉した出力を stderr に返します。machine output は quiet の分岐を通らず、JSON/JSONL をそのまま出します（`strata_cli/cli.py:512-515, 2236-2248`）。

## 適用条件と副作用

このオプションは出力表現を変えます。更新対象の選択や更新処理自体は `--output` では変わりません。更新処理は `strata_cli/update_cmd.py:213-224` で `updater.run_update(...)` に進みます。`--output jsonl` はイベントを逐次 stdout に書き出すため、stdout は純粋な最終結果 JSON だけにはなりません。

## 出力とエラー

- 更新処理内で捕捉される `UpdateError`、`FeedError`、署名エラー、取得拒否、割り込みは、`human` なら `strata: ...` を stderr に出し、`json` / `jsonl` なら `schema_version`、`ok: false`、エラーコードとメッセージを含む JSON を stdout に出します。終了コードは例外側のコードを使い、署名エラーと取得拒否は 5、割り込みは 130 です（`strata_cli/update_cmd.py:163-172, 225-234`）。
- 無効な format 値など parser 段階の引数エラーは `argparse` の usage error です。個別の `--output` 値検証用処理はなく、受理値は parser の choices で制限されます（`strata_cli/update_cmd.py:39`）。
- `jsonl` の処理中に出すイベントは stdout に即時 flush されます（`strata_cli/update_cmd.py:66-69`）。

## 根拠

- `strata_cli/update_cmd.py:30-59` — `--output` の choices・既定値と、トップレベル `update` / `components update` への共通登録。
- `strata_cli/update_cmd.py:62-84, 163-234` — 出力形式別の進捗・結果・失敗経路。
- `strata_cli/cli.py:510-515, 2135-2137, 2232-2248` — 共通 `--json` / `--quiet` の追加、update handler への委譲、quiet 出力処理。
- `docs/cli/README.md:244-262` — `strata update` の索引上のコマンド階層と `--output` の掲載。
- `docs/cli/001_investigation.md:62-69, 73-76` — revision 記録、parser と使用箇所の調査、文書作成基準。
