# `--force`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真、未指定時は偽 |

## 役割

このコマンドでは `--force` を指定しても rollback の結果は変わりません。共通 parser から受理されますが、rollback 実装は force 値を参照しません。`--force` が実際に使われるのは `strata update` / `strata components update` の経路で、テスト起動に失敗した、または rollback 元として skip された engine version の再試行を許可します。

## 使い方

```sh
strata components rollback --force
```

rollback 自体に `--force` は不要であり、上記は通常の rollback と同じ動作です。通常は次のように使います。

```sh
strata components rollback
```

## 値と既定値

値を取らない `argparse` の `store_true` フラグです。未指定時の値は `False`、指定時は `True` になります。同じフラグを複数回指定しても値は `True` のままです。値を続けて渡す形式ではないため、`--force yes` のような入力は余分な引数として parser に拒否されます。rollback parser は共通オプション群 `_common()` を登録しており、その中に `--force` が含まれます。

## 実行時の動作

CLI は `--force` の値を `updater.Context.force` に渡します。しかし rollback 分岐では `updater.rollback_engine(ctx)` を呼び出し、この関数は `ctx.force` を参照しません。rollback は保存済みの前バージョンを検証し、engine の pin / previous / active 状態や履歴を更新しますが、`--force` はそれらの処理を上書き・強制しません。

一方、通常の update 経路では `update_engine()` が `ctx.force` を使い、状態が `failed-before` または `skipped` の engine を再試行対象に含めます。`_choose_engine()` も、rollback 済みの version は `--force` で再インストールするよう案内します。従って再試行したい場合は rollback コマンドでなく `strata update --force` を使います。

## 適用条件と副作用

`--force` の有無にかかわらず rollback は、保存された previous engine がなければ失敗します。対象 engine の manifest 読み込みと完全検証を行い、現在稼働中の engine があれば `--wait` の待機規則を適用します。成功時は前バージョンを pin して次回起動で選ばれる状態にし、engine 状態と履歴を保存します。必要に応じて保存済み tuning preset に再確認マークを付けます。更新ダウンロードは行いません。

## 出力とエラー

成功時は既定の human 出力で切替元・先と tuning preset の扱いを表示します。`--force` の指定有無で表示は変わりません。JSON / JSONL 系の共通出力オプションでは成功データを JSON で出力します。

前バージョンがない場合、または既にその engine に rollback 済みの場合は usage error（終了コード 2）です。前バージョンが検証できない場合、または現在の PC に適合しない場合は refusal（終了コード 5）です。失敗は JSON 系出力なら `ok: false` と error object、human 出力なら標準エラーの `strata: ...` として返されます。rollback 後に新しい方を再試行する案内は `strata update --force` です。

## 根拠

- `strata_cli/update_cmd.py:30-40` は `--force` を値なし `store_true` として共通 parser に追加します。`strata_cli/update_cmd.py:57-59` で rollback parser に `_common()` を適用しています。
- `strata_cli/update_cmd.py:174-195` は force を Context に渡した後 rollback を呼び出し、成功時の出力を行います。`strata_cli/update_cmd.py:167-172,225-234` は通常の失敗表示・終了コード処理です。
- `strata_control/updater.py:1033-1078` は rollback の検証・状態変更・履歴記録を行いますが、`ctx.force` は参照しません。
- `strata_control/updater.py:606-613,926-937` は update 側の force による failed / skipped version の再試行条件を示します。
- `strata_cli/cli.py:2135-2137` は `components rollback` を update command handler に振り分けます。

確認範囲は上記 checkout のソースです。実行可能な同一 revision の CLI help や Release artifact は調査に使用していません。
