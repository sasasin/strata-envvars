# `--restore`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply <run_id>` |
| オプション | `--restore` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。既定値は無効 |

## 役割

run の開始時に保存した `baseline` checkpoint を、指定した destination に戻します。通常の `apply` が保持された結果を適用するのに対し、このフラグを付けると元の checkpoint の復元を選びます。

## 使い方

```sh
strata timeskip apply <run_id> --restore
```

既定では run 記録の workspace に戻します。別の destination を指定する例:

```sh
strata timeskip apply <run_id> --workspace ./project-copy --restore
```

## 値と既定値

値は不要で、parser は `action="store_true"` として登録しています。省略時は `False` で通常の `apply` 経路です。引数値の validation はありません。`--workspace` を省略した場合は記録された workspace、指定した場合はそのパスが復元先です。run の読み込みに使う `--state-dir` は別オプションです（`strata_cli/cli.py:380-393,1467-1485,1524-1533`）。

## 実行時の動作

CLI はまず `--state-dir`、`STRATA_TIMESKIP_DIR`、OS ごとの state base に `time-skip` を加えた場所の順で run store を決め、`run_id` の記録を読み込みます。記録から checkpoint 一覧などを復元した後、`--restore` が有効なら通常の `run.apply(...)` より先に `run.restore_original(destination)` を呼びます（`strata_cli/cli.py:1467-1485,1524-1538,1605-1618`）。

復元処理は checkpoint の `label == "baseline"` を選び、そのディレクトリを destination にコピーします。baseline がなければ `this run has no baseline to restore` で拒否します。成功時は `selected_checkpoint` を baseline ID に更新し、既存の decision があれば再計算して run 記録を保存します（`strata_control/time_skip.py:654-664`）。baseline は run 開始時の workspace を snapshot したものです（`strata_control/time_skip.py:408-420`）。

## 適用条件と副作用

- `--restore` は `--dry-run` を確認せず復元関数を実行します。したがって `--restore --dry-run` でも実際にファイル操作します。
- 同様に `--attempt` は復元分岐では参照されません。revision attempt を指定しても baseline 復元が行われます（`strata_cli/cli.py:1529-1538`）。
- 通常の `apply` が destination の digest を baseline と照合し、変更を conflict として拒否するのに対し、restore 側にはこの照合がありません（`strata_control/time_skip.py:597-627,654-664`）。復元先の現在内容を確認せず置き換えます。
- `copy_tree()` はコピー先が存在すればそのディレクトリ全体を `shutil.rmtree()` で削除して作り直します。baseline snapshot 作成・コピー時の除外対象は `.git`、`__pycache__`、`.strata` で、symlink もコピーしません。そのため復元先にのみ存在するファイルや除外ディレクトリも保持されず、baseline 内の通常ファイルだけが戻ります。復元先の選択を慎重に行ってください（`strata_control/time_skip.py:241-261,271-284,408-420,654-664`）。
- ファイルコピー後、run 記録 `run.json` も更新されます。記録は `--state-dir` 以下の当該 run ディレクトリにあります（`strata_control/time_skip.py:345-372,654-664`）。

## 出力とエラー

- 成功時は human 出力で `restored <checkpoint-id> to <destination>` を表示し、終了コード 0。`--output json` では `schema_version: 1`、`ok: true`、`restore`（`restored: true` と `checkpoint`）を含む JSON を出し、終了コード 0 です（`strata_cli/cli.py:1532-1537,535-542`）。
- run 記録が見つからない場合、または baseline がない場合はエラーとして終了コード 2 です。human 出力は stderr の `strata: ...`、JSON 出力は `ok: false` と `error` を含みます（`strata_cli/cli.py:1524-1528,1532-1540,527-532`; `strata_control/time_skip.py:374-379,654-660`）。
- コピーや記録保存で `OSError` が発生した場合、CLI 共通処理がエラーを表示して終了コード 6 を返します。復元処理自体に rollback copy を作る処理はなく、途中失敗時に destination を元へ戻す保証はソース上確認できません（`strata_control/time_skip.py:654-664`; `strata_cli/cli.py:2174-2183`）。

## 根拠

- `strata_cli/cli.py:380-393` — `timeskip apply` parser、`--restore` の型と既定値、同じ parser の関連オプション。
- `strata_cli/cli.py:1467-1485,1524-1540,1605-1618` — state store の選択、restore 分岐、run 記録からの再構成。
- `strata_control/time_skip.py:241-261,271-284,408-420,654-664` — baseline snapshot、コピー時の除外と destination 全削除、復元と run 記録更新。
- `strata_control/time_skip.py:597-627` — 通常 apply の destination 変更検出との違い。
- `strata_cli/cli.py:527-542,2174-2183` — human/JSON エラー・成功出力と共通 `OSError` 経路。

調査範囲は上記 revision のソース checkout です。同一 revision の `--help`、Release 配布物、各 OS での実行結果は確認していません。記載した挙動は parser と実装コードに基づきます。
