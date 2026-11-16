# `strata launch --speed`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--speed` |
| 別名 | なし |
| 値 | `WORD` を1つ取る。parser に型・選択肢・個別の既定値指定はない |

## 役割

旧 DeepSeek 起動用スクリプトとの互換性のために parser が受理する隠しオプションです。現行の `strata launch` で速度設定を変更する機能ではありません。通常の起動処理では値が空でなければ DeepSeek は提供されなくなったという案内を返して起動を拒否します（`strata_cli/launch/cmd.py:109`, `strata_cli/launch/cmd.py:217-220`, `strata_control/retired.py:4-7`, `strata_control/retired.py:42-43`）。

## 使い方

このオプションを現行起動で使う方法はありません。たとえば次の呼び出しは `faster` を速度設定として適用せず、廃止案内で失敗します。

```sh
strata launch --model iq3_xxs --speed faster
```

## 値と既定値

- `--speed` は `WORD` という metavar だけを持ち、`type`、`choices`、`action`、`default` の指定がありません。値の内容を検証・変換する Strata 側の処理もありません（`strata_cli/launch/cmd.py:109`）。
- 値を省略すると通常は引数解析エラーになります。非空値は内容にかかわらず廃止案内の拒否条件になります（`strata_cli/launch/cmd.py:109`, `strata_cli/launch/cmd.py:218-219`）。
- `--speed=` のように空文字を明示すると、拒否判定の `any(...)` は偽になります。その場合、このフラグ自体は設定に反映されず、通常の `strata launch` 処理が続きます（`strata_cli/launch/cmd.py:218-220`）。
- 複数回指定時の値の扱いを Strata は独自に定めていません。parser に繰り返し指定の処理はありません（`strata_cli/launch/cmd.py:109`）。

## 実行時の動作

通常の起動経路では `settings_from_args()` が `speed` を他の DeepSeek 専用フラグとともに調べ、値が truthy なら `retired.NOT_OFFERED` を `ValueError` として送出します。速度設定への変換、エンジン引数への転送、保存済み設定への書き込みは行いません（`strata_cli/launch/cmd.py:206-220`）。

ただし preset 一覧・削除、停止、状態表示、キー表示などの管理モードは、この検査より前に処理を終える場合があります。したがって、それらの管理フラグとの併用では `--speed` の拒否判定に到達しない経路があります（`strata_cli/launch/cmd.py:723-769`, `strata_cli/launch/cmd.py:798`）。

`--backend` を併用した場合は処理順に注意が必要です。backend の値は `settings_from_args()` による `--speed` の拒否判定より前に処理され、`--plan` なしでは選択が保存されます。したがって `--speed faster --backend nvidia` のような通常起動は失敗しますが、backend の保存だけが先に行われる可能性があります。`--plan` の場合は backend を保存しない分岐です（`strata_cli/launch/cmd.py:771-798`, `strata_cli/launch/cmd.py:217-220`）。

## 適用条件と副作用

- `--speed` 自体に現行の速度調整効果はありません。非空値は通常の起動を止めます。parser 登録時に `argparse.SUPPRESS` が指定されているため、`strata launch --help` にも表示されません（`strata_cli/launch/cmd.py:109`）。
- 拒否判定は `settings_from_args()` に到達した起動経路で行われます。上記のとおり、管理モードが先に終了する場合や、拒否判定より前に処理される `--backend` の副作用は別に考慮してください（`strata_cli/launch/cmd.py:723-798`）。

## 出力とエラー

非空値を通常の起動経路で指定すると、案内は `Strata no longer offers DeepSeek models. Run \`strata launch\` to choose one of the Qwen models.` です。人向け出力では `strata: ` を付けて標準エラーに出し、終了コード `2` を返します。`--output json` では同じメッセージを `ok: false` の JSON エラーとして標準出力に出します（`strata_control/retired.py:43`, `strata_cli/launch/cmd.py:716-721`, `strata_cli/launch/cmd.py:963-964`）。

## 根拠

- `strata_cli/launch/cmd.py:73-110` — `launch` parser と、値 `WORD`・help 非表示で登録される `--speed`。
- `strata_cli/launch/cmd.py:206-220` — 受理した値を検査し、非空値を廃止案内で拒否する箇所。
- `strata_cli/launch/cmd.py:723-798` — 管理モードと backend 処理が拒否判定より先に行われる制御フロー。
- `strata_cli/launch/cmd.py:716-721`, `strata_cli/launch/cmd.py:961-964` — 人向け / JSON エラー処理と終了コード。
- `strata_control/retired.py:4-7`, `strata_control/retired.py:42-43` — DeepSeek を現行版で実行しない説明と、専用フラグに使う案内文。

調査は上記 commit のソースを対象に行いました。同一 revision の CLI `--help` は実行していません。parser の登録・分岐と索引の `strata launch` 節（`docs/cli/README.md:809-855`）を照合し、対象オプションと配置 scope の一致を確認しました。
