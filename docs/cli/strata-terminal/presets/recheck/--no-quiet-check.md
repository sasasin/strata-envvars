# `--no-quiet-check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--no-quiet-check` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は parser の値が `True` になる |

## 役割

このオプションは `strata presets recheck` の parser で受理されます。しかし、このコマンドの実行経路では値が参照されず、指定しても省略しても recheck の動作は変わりません。特に、指定によって待機が無効になるわけではありません。現行実装では recheck が tuner の quiet check を実行しないためです。

同じ名前のフラグは `strata tune auto` にもありますが、そちらでは別の parser scope で `check_busy` に反映されます。この文書は索引の配置どおり `strata presets recheck` のフラグだけを扱います。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config> --no-quiet-check
```

`<preset>` は保存済み preset、`<profile-or-config>` は preset が属する profile 名または run configuration です。これらは必須位置引数です。フラグを付けた呼び出しは受理されますが、同じ引数からフラグだけを外した呼び出しと同じ recheck 処理になります。

## 値と既定値

`argparse` の `action="store_true"` で定義されているため、値は不要で、未指定時は `False`、指定時は `True` です。列挙値や数値範囲の validation はありません。値を後置すると余分な引数として拒否されます。

## 実行時の動作

parser は `--no-quiet-check` を `Namespace` に格納しますが、`_recheck()` はその属性を読みません。同関数は preset と対象設定を読み、識別情報・staleness・engine の tuning epoch を調べた後、`autotune.Options` を preset の `use` だけで構成し、`autotune.recheck()` を呼び出します。したがってこのフラグは recheck の実行設定に伝わりません。

`autotune.recheck()` の各測定は `session.engine(a, e)` を呼び、quiet check を行う `pre_start` callback を渡しません。quiet check は `WorkerSession.engine()` に callback が渡された場合だけ呼ばれる仕組みです。一方、`--gpu-lock` が指定されているか環境変数 `STRATA_TUNE_GPU_LOCK` から既定値を得ている場合は、そのファイルロックはフラグに関係なく engine 実行時に使用されます。

参考として、`strata tune auto` 側では同名フラグを `check_busy=not a.no_quiet_check` に渡し、quiet check の有効・無効を切り替えています。この挙動を `presets recheck` に適用する根拠はありません。

## 適用条件と副作用

現在の `presets recheck` 実装では、このフラグに固有の適用条件や副作用はありません。recheck 自体は通常どおり測定を行い、preset の recheck 結果を保存します。指定の有無で、work directory、status file、GPU lock、測定内容、preset 更新は変わりません。

## 出力とエラー

フラグだけを理由とした警告・エラー・出力変更はありません。recheck の人間向け進捗は stderr、最終メッセージは stdout に出力され、`--output json` を選ぶと JSON 結果になります。

このフラグとは独立して、preset が hard-stale と判定されると `_fail()` が code `5` で失敗を返します。測定 engine が起動できない場合などは recheck 結果が `retune` になり、結果と preset 更新を出力します。コマンド parser が未定義の引数を受け取った場合は CLI の引数エラー経路で拒否されます。

## 根拠

- `strata_cli/tune_commands.py:82-90` — `presets recheck` の必須位置引数とオプション定義。`--no-quiet-check` は `store_true` で、help 文も個別の validation もない。
- `strata_cli/tune_commands.py:411-438` — `_recheck()` が preset・設定・context を用意し `autotune.recheck()` を呼ぶが、`a.no_quiet_check` は参照しない。
- `strata_control/autotune.py:885-915` — recheck が preset 設定で測定し、`session.engine()` に `pre_start` を渡さない。
- `strata_control/tune_session.py:443-449` — WorkerSession は `pre_start` がある場合にのみ callback を実行する。lock はその前に別途取得する。
- `strata_cli/tune_commands.py:132-136`、`strata_control/tune_session.py:196-233` — `--gpu-lock` が設定された場合の FileLock 構成と取得・待機経路。
- `strata_cli/tune_commands.py:41`、`strata_cli/tune_commands.py:194-197` — 同名フラグは `strata tune auto` では `check_busy` に渡されるが、これは別コマンド scope。
- `strata_cli/tune_commands.py:419-420`、`strata_cli/tune_commands.py:443-447` — hard-stale 時の失敗 code と recheck 完了時の結果出力。
- `strata_cli/cli.py:2223-2231` — CLI が parser を実行し、余分な引数をエラーとして扱う経路。

調査範囲は上記 checkout のソースコードです。既存バイナリの `--help` 出力や Release 配布物は照合していません。parser 定義と参照検索の範囲では、このオプションが `presets recheck` で受理されること、およびその実行関数内で未使用であることを確認しました。
