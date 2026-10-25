# `strata profile set`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile set` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |

## 役割

名前付き serving profile に、型付きの設定 override を一つ以上保存します。対象は `host`、`port`、`parallel`、`batch_groups`、`max_queue`、`queue_timeout`、`offline`、`batch_telemetry` です。profile が参照する setup 生成 run config 自体は編集しません（parser: `strata_cli/cli.py:69-70,84-88`; override 定義: `strata_control/profiles.py:25-27,66-95`）。

## 使い方

profile を作成済みであることを前提に、保存前に差分を確認できます。

```sh
strata profile set four-gpu parallel=8 batch_groups=auto max_queue=32 queue_timeout=15 --plan
strata profile set four-gpu parallel=8 batch_groups=auto max_queue=32 queue_timeout=15
strata profile show four-gpu --effective
```

`name` の後に `KEY=VALUE` を1件以上指定します。例は `docs/TERMINAL_QUICKSTART.md:41-50` にもあります。`--plan` は差分を表示して保存を省略し、通常実行は保存します。`--output human|json` を指定でき、既定値は `human` です。one-shot コマンド共通の `--json` と `--quiet` も登録されています（`strata_cli/cli.py:84-88,508-515`; 実行分岐: `strata_cli/cli.py:986-997`）。

## 主な動作

1. profile を読み込み、すべての assignment を型変換・検証します。
2. 指定されたキーだけを現在の `overrides` に重ねます。省略した既存 override は保持され、同じキーを複数回指定した場合は後の値が残ります（`strata_control/profiles.py:304-309`）。
3. `--plan` なら変更前後の差分と `would_save` を返して終了します。通常実行では変更がある場合に保存し、以前の revision を `.history/<profile>/` に記録します。変更がなければ既存 revision を維持します（`strata_cli/cli.py:986-997`; `strata_control/profiles.py:266-295`）。

保存は profile store 内でロックし、revision が読み込み後に変わっていないことを確認します。profile の JSON を一時ファイル経由で atomic replace し、以前の内容を history に保存します（`strata_control/profiles.py:185-205,266-295`）。保存場所は Windows では `%APPDATA%/Strata/profiles`（`APPDATA` 未設定時はユーザーホーム配下）、Unix 系では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` で、`STRATA_PROFILE_DIR` があればそちらを使います（`strata_control/profiles.py:38-45`）。

## 値と適用条件

| キー | 受理値 |
| --- | --- |
| `host` | 空でなく、空白文字を含まない文字列 |
| `port` | 整数 `0..65535` |
| `parallel` | 整数 `1..1024` |
| `batch_groups` | `auto` または整数 `1..1024` |
| `max_queue` | 整数 `0..4096` |
| `queue_timeout` | 有限の秒数 `0.1..600` |
| `offline`、`batch_telemetry` | 小文字 `true` または `false` |

数値キーは指定文字列を整数または浮動小数点数へ変換し、boolean キーは `true` / `false` だけを受け付けます。`KEY=VALUE` 形式でない assignment、未知キー、変換失敗、範囲外の値は拒否されます（`strata_control/profiles.py:66-117`）。profile 名は小文字英字で始まり、その後は小文字英字・数字・`_`・`-` を使える最大64文字です（`strata_control/profiles.py:25,48-55`）。

このコマンドは値を profile に保存します。実効値の解決は利用時に行われ、CLI で明示した設定が保存済み override より優先し、保存済み override は run config の値より優先します。未指定時は既定値または一部環境変数が使われます（`strata_cli/cli.py:745-779`）。`queue_timeout` と `max_queue` の組み合わせなど実行時の整合条件も、値を適用する serving plan 側で確認されます（同所:770-778）。

## 副作用と注意点

- 保存は今後 profile を使って起動する serving 設定に反映されます。すでに稼働中の server の設定変更や再起動は行いません。再起動は別の明示的な `strata runtime restart` 操作です（`docs/TERMINAL_QUICKSTART.md:53-62`）。
- `--plan` は profile を保存しませんが、profile の読み込みと assignment の検証は行います。保存時は profile directory、lock、必要に応じて履歴ファイルを作成・更新します（`strata_cli/cli.py:986-997`; `strata_control/profiles.py:266-295`）。
- 保存対象の run config が読み取り可能で、有効な `args`、`exe`、`tokenizer` を持つことも保存時に再確認します（`strata_control/profiles.py:135-147,266-270`）。
- assignment に未指定のキーを削除する構文はこのコマンドにはありません。指定したキーの値を上書きする動作です（`strata_control/profiles.py:304-309`）。

## 出力とエラー

`--plan` は指定した output mode で差分と `would_save` を返します。`--output human` では `_success` の既定動作により整形 JSON、`--output json` または `--json` では一行 JSON が出力され、後者には schema version と `ok` も含まれます。通常保存時の human 出力には変更キーごとの前後値が出ます（`strata_cli/cli.py:986-997,535-542`; JSON 切替: `strata_cli/cli.py:2232-2237`）。

未保存 profile は終了コード `5`、入力検証エラーは通常 `2`、保存競合は `6` で失敗します。エラーは human 出力では stderr の `strata: ...`、JSON モードでは `ok: false` とエラー情報として返ります（`strata_control/profiles.py:30-35,157-165,273-275`; `strata_cli/cli.py:526-534,2166-2173`）。

## 関連文書

- [profile コマンド一覧](../README.md)
- [`strata profile show`](../show/README.md) — 保存値と実効値の確認
- [`strata profile create`](../create/README.md) — profile の作成
- [`strata runtime restart`](../../runtime/restart/README.md) — 稼働中 instance の明示的な再起動
- [CLI 索引](../../../README.md)

## 根拠

- `strata_cli/cli.py:69-70,84-88,508-515` — command hierarchy、位置引数、`--plan`、`--output`、one-shot 共通 option。
- `strata_cli/cli.py:986-997,2232-2237` — plan/save 分岐、差分出力、JSON mode。
- `strata_control/profiles.py:25-27,38-45,48-55,66-117` — profile 名、保存場所、assignment の型変換・validation。
- `strata_control/profiles.py:266-309` — revision 確認、history、atomic 保存、override merge。
- `strata_cli/cli.py:745-779` — 保存値と run config・CLI 値の優先順位、および実効値の追加条件。
- `docs/TERMINAL_QUICKSTART.md:41-62` — 利用例と再起動が別操作であること。
