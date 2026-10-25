# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると有効 |

## 役割

人向け出力を成功時に表示しないようにします。モデルファイルの移動方法や設定更新には影響しません。`--quiet` は `move` 専用 parser の宣言ではなく、`strata_cli/cli.py` が one-shot コマンド群へ後から追加する共通オプションです。

## 使い方

```sh
strata models move /path/to/new-models-folder --quiet
```

人向け出力形式（既定値 `--output human`）での例です。移動を開始せず計画だけ確認する場合は、`--plan` と併用できます。

## 値と既定値

- `action="store_true"` のため値は不要です。値を付ける形式は parser が受理しません。省略時は属性自体が作られず、実行時には無効として扱われます。繰り返し指定しても真偽値は変わりません。
- この parser で `--output` の既定値は `human`、選択肢は `human`、`json`、`jsonl` です。`--json` も共通 one-shot オプションとして追加され、指定時は出力形式を `json` にします。
- `--quiet` に固有の追加 validation はありません。

## 実行時の動作

`main()` は `--quiet` が有効で出力形式が `human` のとき、`_run()` 中の stdout を捕捉します。コマンドが終了コード 0 なら捕捉した内容を表示しません。`models move` の進捗表示と完了・停止メッセージはいずれも stdout へ出すため、成功した移動の進捗行と最終メッセージは隠れます。移動処理自体は通常どおり実行されます。

`--output json` または `--output jsonl`（`--json` を含む）では `main()` が quiet 捕捉を通さず `_run()` を呼びます。したがって JSON 結果や JSONL 進捗イベントは `--quiet` でも抑制されません。`--plan` も同じ human/json 分岐を使います。

## 適用条件と副作用

- 対象は人向け stdout の表示制御だけです。ファイルの移動・検証、移動状態ファイル、run config の更新、キャンセル処理には変更を加えません。移動経路では同一ドライブなら rename、別ドライブならコピーと検証を行い、確認後に元ファイルを削除します。`--quiet` はこれらの挙動を変えません。
- `_run()` が非 0 で終わり、stdout に捕捉内容があれば、最後の最大 64 KiB を stderr に書き戻します。捕捉内容がその上限を超えた場合は、省略があった旨も stderr に出ます。`models move` の失敗メッセージは通常から stderr に出るため、quiet でも維持されます。
- argparse による構文エラーは `_run()` より前に処理されるため、`--quiet` で隠れません。

## 出力とエラー

`models move` の通常移動は、成功時 `0`、安全に停止した場合 `6`、`MoveError` の場合 `5` を返します。quiet の human 出力では成功メッセージを隠しますが、停止（非 0）時は捕捉済みの進捗・停止メッセージが stderr に書き戻されます。移動エラーの説明は stderr に直接出力されます。JSON/JSONL のエラー出力は quiet で抑制されません。

## 根拠

- parser と引数: `strata_cli/cli.py:162-171`（`move` の引数）、`strata_cli/cli.py:508-515`（one-shot parser への `--quiet` / `--json` 追加）。
- 共通 quiet 処理と JSON との関係: `strata_cli/cli.py:2196-2214`（stdout 捕捉の 64 KiB 上限）、`strata_cli/cli.py:2223-2248`（parser 実行後の出力形式選択、quiet 捕捉、失敗時 stderr 書き戻し）。
- 移動コマンドの分岐、進捗、結果・エラー出力と終了コード: `strata_cli/cli.py:617-660`。中断済み移動の status/resume/leave は `strata_cli/cli.py:668-705`。
- quiet とは独立した移動処理: `strata_control/models_move.py:379-390`（計画検証と初期化）、`strata_control/models_move.py:423-432`（進捗イベント）、`strata_control/models_move.py:441-531`（移動・停止・失敗時の処理）。
