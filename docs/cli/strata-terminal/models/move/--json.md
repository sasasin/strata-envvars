# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 取らない真偽値フラグ |

## 役割

人向け表示を、機械処理向けの JSON 出力に切り替える。`--output json` の別表記として実装されている。JSON 出力は stdout に書かれる。

## 使い方

中断された移動状態を変更せず JSON で確認する例:

```sh
strata models move --status --json
```

移動先を指定して事前計画を JSON で表示する場合は、`strata models move --plan --json NEW_FOLDER` とする。

## 値と既定値

- 引数値は不要。parser の `store_true` で、既定値は false。
- `--json` は `strata_cli/cli.py` の共通 one-shot parser 群に追加され、そこに `models_move` が含まれる。help 上の説明も `--output json` の alias。
- `--json` がなければ `--output` の既定値 `human` が使われる。`--output` は `human`、`json`、`jsonl` を受理する。
- `--json` と `--output json` の併記は同じ JSON モードを指す。`--json` と `--output jsonl` の併記は拒否され、失敗イベントを stdout に JSONL 形式で出して終了コード 2 となる。
- 値を付けた `--json=true` のような形式は受理されない。

## 実行時の動作

parser が `--json` を true にすると、引数解析後の共通処理で `a.output` が `json` に置き換えられる。そのため `strata models move` の処理本体は `--output json` と同じ分岐を通る。`--json` 自体は移動方法、移動元・先、キャンセル条件を変えない。

出力は操作モードごとに異なる:

- `--plan`: `schema_version`、`ok`、`plan` を含む JSON を1件出す。計画結果が不可なら終了コード 5。
- 通常移動、または `--resume`: 成功時は `schema_version`、`ok: true`、`event: "result"` と移動概要を出す。安全停止で完了しなかった場合も結果 JSON を出し、終了コード 6。
- `--status`: `schema_version`、`ok: true`、`interrupted`（状態がなければ null）を出す。終了コード 0。
- `--leave`: 成功時は `schema_version`、`ok: true`、`event: "result"`、`left: true` と後始末概要を出す。
- 移動で `MoveError` が起きた場合は `schema_version`、`ok: false`、エラーコード・メッセージ・詳細を JSON 化する。部分移動があれば移動概要も含み、終了コード 5。
- `--resume` / `--leave` 対象の中断状態がない場合は `ok: false` と `error.code: "nothing"` を JSON で出し、終了コード 5。

通常移動の `--output jsonl` は進捗イベントを逐次出して最後に結果を出す。一方 `--json` は one-shot の JSON として扱われるため、JSONL 進捗を出さない。JSON の選択は表示形式だけだが、`models move` 自体はファイル移動を実行し得る。`--plan` は移動しないものの、計画用の書き込み確認で移動先フォルダーを作成し、一時ファイルを作成・削除する。

## 適用条件と副作用

このフラグは `strata models move` のほかのオプションと併用できる。`--status` と `--plan` は読み取り中心の確認モードだが、上記のとおり `--plan` は移動先への書き込み確認を行う。通常移動・resume はモデルファイルを移し、設定ファイルのパスを書き換える場合がある。`--leave` は中断移動を取り消し、部分コピーを削除またはファイルを元へ戻す。これらの操作上の副作用は `--json` によって変化しない。

`NEW_FOLDER` を省略した通常移動は、`--json` を付けても JSON エラーにはならず、説明を stderr に出して終了コード 2 となる。これは移動処理本体の明示的な入力エラー分岐である。

## 出力とエラー

JSON の通常結果・アプリケーションエラーは stdout に1行で出力される。`--json` と `--output jsonl` の組み合わせでは、`--json` は one-shot 専用として拒否され、`event: "failed"`、終了コード 2、理由を含む JSONL 行が stdout に出る。未知の引数や不正なオプション値は argparse の引数エラーとなる。`NEW_FOLDER` の不足だけは前述のとおり人向け文面が stderr に出る。

## 根拠

- parser: `strata_cli/cli.py:162-171` で `models move` の階層、`--output` の選択肢・既定値を定義。`strata_cli/cli.py:508-515` で `models_move` を含む one-shot parser 群に `--json` を `store_true` として追加。
- 共通適用: `strata_cli/cli.py:2223-2235` で parser を実行し、`--json` と `--output jsonl` の併用を拒否したうえで、`--json` を `output=json` に変換。
- 出力経路: `strata_cli/cli.py:617-660` で plan、通常移動、進捗、MoveError、完了・安全停止時の JSON と終了コードを処理。`strata_cli/cli.py:668-705` で status、resume、leave と中断なしの経路を処理。`strata_cli/cli.py:829-835` は `jsonl` との併用拒否時の失敗イベント形式。
- コマンド側の効果: `strata_control/models_move.py:137-184` は計画と書き込み確認、`strata_control/models_move.py:223-258` はコピー検証、`strata_control/models_move.py:379-531` は移動・停止・失敗時の状態保存、`strata_control/models_move.py:534-573` は中断移動の取り消しを実装。
