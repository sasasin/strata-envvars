# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile edit` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる。既定値は偽（属性自体は未指定時に作られない） |

## 役割

編集後に表示する人間向けの成功メッセージを抑制します。プロフィール編集そのものや保存結果は変えません。

## 使い方

```sh
strata profile edit Office --quiet
```

`Office` は編集する保存済みプロフィール名です。編集には `VISUAL` または `EDITOR` 環境変数で指定されたエディターが必要です。

## 値と既定値

`--quiet` は `argparse` の `store_true` フラグで、引数値を受け取りません。省略時は偽です。無効値や重複指定に対する個別 validation はありません。parser に同じフラグが登録されており、複数回指定しても真のままです（`strata_cli/cli.py:508-515`）。

## 実行時の動作

`--quiet` は profile edit 用 parser に one-shot コマンド共通オプションとして追加されます。編集処理は通常どおり、現在のプロフィールを一時 JSON ファイルへ書き、`VISUAL` または `EDITOR` のプログラムを起動し、編集結果を検証して保存します。成功すると通常は `Saved profile ...` を stdout に出しますが、quiet 時は CLI の `main` が `_run` 中の Python stdout を捕捉し、終了コードが 0 のときは捕捉内容を表示しません。JSON 出力（`--json` または `--output json`）との組み合わせでは quiet による捕捉を行わず、JSON 結果を stdout に出します（`strata_control/profiles.py:349-379`、`strata_cli/cli.py:998-1005,2232-2247`）。

quiet はプロフィール編集処理の内容、保存、revision 更新、エディター起動を無効にしません。また、`contextlib.redirect_stdout` による Python stdout の捕捉であり、OS 標準出力を差し替える処理ではありません。したがって外部エディターの出力抑制はソース上確認できません。

## 適用条件と副作用

`VISUAL` が空でない場合は `EDITOR` より優先されます。両方とも未設定または空なら編集は失敗します。環境変数を `shlex.split` でコマンドと引数に分けて一時 JSON のパスを末尾に付けて起動します。編集結果が有効ならプロフィールを保存し、一時ファイルを削除します。quiet はこれらの副作用に影響しません（`strata_control/profiles.py:349-379`）。

## 出力とエラー

成功時は人間向け完了行を抑制します。`--output json` では JSON 出力が残ります。失敗時は `_run` の終了コードが非ゼロで、Python stdout に捕捉内容があれば stderr へ戻します。捕捉が 64 KiB を超えて切り詰められた場合は `strata: earlier human output omitted in quiet mode` も stderr に出ます（`strata_cli/cli.py:2196-2214,2236-2248`）。

エディターが非ゼロ終了すると終了 status を含むエラーになり一時ファイルは draft として残ります。編集内容が JSON として不正、または保存時の検証・revision 条件で失敗した場合も draft を残します。`VISUAL` / `EDITOR` がない場合や空の場合も失敗します（`strata_control/profiles.py:351-379`）。例外は CLI の `_run` でエラー出力と終了コードに変換されます（`strata_cli/cli.py:2166-2193`）。quiet が抑制するのは Python stdout であり、stderr のエラーメッセージを抑制しません。

## 根拠

- `strata_cli/cli.py:96-98` — `profile edit` parser と位置引数、`--output` の定義。
- `strata_cli/cli.py:508-515` — `profile_edit` を含む one-shot parser 群への `--quiet` 後付け定義。
- `strata_cli/cli.py:998-1005` — edit 実行と成功時の人間向け結果。
- `strata_cli/cli.py:2196-2214,2232-2248` — quiet 時の stdout 捕捉、成功時破棄、失敗時 stderr 再出力、JSON 出力の例外。
- `strata_control/profiles.py:349-379` — エディター選択、起動、一時ファイル、JSON 検証、保存、失敗時 draft 保持。
