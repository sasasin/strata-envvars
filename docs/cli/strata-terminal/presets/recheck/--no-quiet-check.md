# `strata presets recheck --no-quiet-check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--no-quiet-check` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ（`store_true`） |

## 役割

このコマンドではフラグを指定しても実行時の効果はありません。recheck の parser は受理しますが、ハンドラーから値を参照せず、recheck の測定関数にも「他のエンジンや CPU 負荷を待つか」という設定を渡していません。通常の `strata tune auto` で同名フラグが静穏確認を無効化する動作とは異なります。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config.json> --no-quiet-check
```

`<preset>` は保存済み preset の識別子、2つ目の引数は対応する profile 名または実行設定 JSON です。このオプションは指定しても結果に影響しません。静穏確認の有効・無効を切り替える用途には使えません。

## 値と既定値

値は不要です。parser は `action="store_true"` で登録しており、省略時は偽、指定時は真になります。数値などの値を付ける形式ではありません。recheck 処理でこの値は読み取られないため、省略時と指定時の実行動作は同じです。別名はありません。【`terminal/strata_cli/tune_commands.py:88-96`】

## 実行時の動作

`strata presets recheck` は保存済み preset と対象設定を読み、preset の状態と選択条件を確認した後、`autotune.recheck` で保存時の設定を短時間測定し、結果を preset に記録します。recheck ハンドラーは `--no-quiet-check` の値を参照せず、`autotune.Options` にも値を設定しません。【`terminal/strata_cli/tune_commands.py:615-655`】

同名フラグが実際に使われるのは `strata tune auto` の経路です。そこでは `check_busy=not a.no_quiet_check` として tuner に渡され、`check_busy` が偽なら `_wait_for_quiet()` は即時に戻ります。静穏確認を有効にした場合は別の Strata engine 実行と CPU 負荷を調べ、該当時には最大300秒待ってから測定を続けます。【`terminal/strata_cli/tune_commands.py:45`, `terminal/strata_cli/tune_commands.py:342-345`, `terminal/strata_control/autotune.py:69-72`, `terminal/strata_control/autotune.py:252-275`】この `tune auto` の動作は本書の `presets recheck` スコープには適用されません。

recheck は保存済み測定値との比較から `keep`、`retune`、`inconclusive` のいずれかを返し、その結果を preset に記録します。`--no-quiet-check` は判定、設定値、ロック処理、測定手順を変更しません。【`terminal/strata_control/autotune.py:937-946`, `terminal/strata_control/autotune.py:970-1012`, `terminal/strata_cli/tune_commands.py:652-661`】

## 適用条件と副作用

このフラグの有無にかかわらず、preset が現在の PC と大きく異なる場合や保存時と対象の選択条件が違う場合、測定前にエラーで終了します。【`terminal/strata_cli/tune_commands.py:621-631`】実際に recheck を行うと、測定用 worker/server と engine プロセスを起動して終了し、作業ディレクトリに実行設定・ログを作成します。`--work-dir` 省略時は一時ディレクトリを使い、終了時に削除します。`--gpu-lock` が指定されていれば各 engine 実行をそのロックで保護します。これらはフラグの有無では変わりません。【`terminal/strata_cli/tune_commands.py:640-644`, `terminal/strata_cli/tune_commands.py:654-657`, `terminal/strata_cli/tune_commands.py:185-189`, `terminal/strata_control/tune_session.py:527-550`, `terminal/strata_control/tune_session.py:563-610`】

## 出力とエラー

フラグの有無で出力は変わりません。通常の human 出力では進捗を stderr に出し、完了時の判定を stdout に表示します。`--output json` では進捗を抑え、結果またはエラーを JSON で stdout に出します。【`terminal/strata_cli/tune_commands.py:635-639`, `terminal/strata_cli/tune_commands.py:647-661`, `terminal/strata_cli/tune_commands.py:101-114`】

hard stale 状態や対象選択の不一致は終了コード `5` のエラーになります。preset エラーも `5`、ファイル・値エラーは例外に `exit_code` があればその値、なければ `2` で返されます。【`terminal/strata_cli/tune_commands.py:527-530`, `terminal/strata_cli/tune_commands.py:623-631`】

## 根拠

- `terminal/strata_cli/tune_commands.py:55-60` — `presets` 配下のサブコマンドと共通 `--output` parser。
- `terminal/strata_cli/tune_commands.py:88-96` — `recheck` parser と `--no-quiet-check` の真偽値登録。
- `terminal/strata_cli/tune_commands.py:615-661` — recheck ハンドラー。該当フラグを読まずに測定・記録・出力する経路。
- `terminal/strata_cli/tune_commands.py:342-345` — `tune auto` ではフラグを `check_busy` に反映する箇所。
- `terminal/strata_control/autotune.py:252-275` — `check_busy` による待機の有無と静穏確認条件。
- `terminal/strata_control/autotune.py:937-1012` — recheck の測定と verdict の決定。`check_busy` を使う tuner 待機処理を通らない。
- `terminal/strata_control/tune_session.py:527-610` — engine 起動時のロック、worker 起動・終了、作業ファイルの処理。
