# `strata profile show`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile show` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |

## 役割

保存済み serving profile の内容と revision を表示します。`--effective` を付けると、profile の override、参照先 run config、環境値、既定値を反映した有効設定と起動計画も表示します。profile や run config の変更、推論サーバーの起動は行いません。

## 基本的な使い方

```sh
# profile の内容と revision を表示
strata profile show local

# 有効設定と起動計画も表示
strata profile show local --effective

# JSON 出力を指定
strata profile show local --output json
```

`name` は必須の位置引数です。`--effective` と `--output` はこの `show` サブコマンドの parser に属します。個別の説明は [`--effective`](--effective.md) と [`--output`](--output.md)、一覧は [CLI 索引](../../../README.md)を参照してください。

## 表示内容と動作

- `--effective` なしでは、profile オブジェクトと revision を表示します。既定の `--output human` は整形 JSON、`--output json` は `schema_version` と `ok` を含む JSON envelope です。
- `--effective` を付けると、上記に `plan` を追加します。計画には参照 run config、選択された有効値とその由来、server 引数、engine 実行ファイルと引数などが含まれます。API key は計画を組み立てる際に検査され、engine 引数は表示用に redact されます。
- 有効値の選択では、コマンド指定値、保存 profile の override、run config、`STRATA_BATCH_TELEMETRY` 環境変数、既定値の順に採用されます。`show` には値指定 option がないため、通常は保存 profile・run config・環境変数・既定値が使われます。`--effective` は `queue_timeout` と `max_queue` の組合せ、run config の batch/slot 引数との競合、offline 条件なども検査します。
- profile は `STRATA_PROFILE_DIR` が設定されていればその場所から読みます。未設定時は Windows では `%APPDATA%/Strata/profiles`、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定なら `~/.config/strata/profiles`）が使われます。
- `--json` は one-shot コマンド共通で追加される `--output json` の alias です。`--quiet` も共通 parser に追加され、human 出力を抑制します。JSON 出力は quiet の対象外です。

## 注意点と失敗

profile 名は小文字英字で始まり、その後は小文字英数字、`_`、`-` を使えます（最大 64 文字）。profile ファイルは通常ファイルでなければならず、サイズ上限は 1 MiB です。欠落、JSON の破損、schema・ID・override の不正などではエラーになります。`--effective` では参照先 run config を読めない場合や有効値の組合せが不正な場合、API key が不正な場合も失敗します。

profile 読み込み時には `read_bytes_repairing` を使い、管理者権限で残った profile ファイルの所有権・アクセス権を必要に応じて修復します。通常の表示では profile や run config の内容を書き換えません。エラーは既定で stderr に `strata: ...` と表示され、profile ファイルの欠落・読込不能は exit code 5、その他の `ProfileError` は原則 exit code 2 です。`--effective` 中の不正な API key は exit code 5 です。`--output json` または `--json` の場合はエラーを JSON で stdout に出します。

## 関連文書

- [`strata profile` の概要（CLI 索引）](../../../README.md)
- [`strata profile show` の全オプション（CLI 索引）](../../../README.md)
- [`strata launch` の概要](../../launch/README.md)

## 根拠

- Strata `strata_cli/cli.py:69-80` — `profile show` parser、必須 `name`、`--effective`、`--output`。
- Strata `strata_cli/cli.py:508-515` — one-shot コマンドへの `--json`、`--quiet` 追加。
- Strata `strata_cli/cli.py:958-968,1015-1020` — profile の読込、戻り値、effective 計画の条件、成功出力。
- Strata `strata_cli/cli.py:745-779,782-826` — 有効値の優先順位、組合せ検査、起動計画の構築。
- Strata `strata_cli/cli.py:2166-2183,2232-2248` — 例外の出力・終了コード、JSON alias と quiet の処理。
- Strata `strata_control/profiles.py:25-55,120-166` — profile 名・保存場所・schema 検査・読み込みと権限修復 helper の呼出し。

この調査は上記 commit の checkout ソースに基づきます。Release 配布物や Windows での実行結果は別途確認していません。
