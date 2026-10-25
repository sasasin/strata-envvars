# `--attempt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply` |
| オプション | `--attempt` |
| 別名 | なし |
| 値 | 改訂 attempt の番号。整数 |

## 役割

Time-skip run が保持する checkpoint の代わりに、利用者がレビューして選んだ改訂 attempt を workspace に適用します。既定では run の `selected_checkpoint` が適用されるため、このオプションはその選択を明示的に上書きしたい場合に使います。

## 使い方

```sh
strata timeskip apply RUN_ID --attempt 1 --dry-run
strata timeskip apply RUN_ID --attempt 1
```

まず `--dry-run` で書き込み・削除予定を確認できます。実適用では run が記録した workspace が宛先です。別の宛先を使う場合は `--workspace DIR` を併用します。

## 値と既定値

`--attempt` は `int` に変換され、未指定時は `None` です。正の範囲や上限は parser では検証されず、指定した整数と一致する attempt が run に記録され、その候補ディレクトリが存在する必要があります。一致する attempt がない場合、または候補ディレクトリがない場合は `TimeSkipError` になります。非整数は argparse の引数エラーです。同じオプションを複数回指定した場合の追加処理はなく、通常の argparse の値保持に従います。

## 実行時の動作

CLI は `--attempt` の値を `TimeSkipRun.apply(..., attempt=...)` に渡します。指定があると、run 内の attempt を `index` で検索し、その `path` を適用元にします。選んだ attempt の判定結果が `keep` であることは適用条件ではありません。番号が存在し候補ディレクトリがあれば、明示選択として適用元になります。省略時は run の `selected_checkpoint` を使います。

宛先は `--workspace` があればそのディレクトリ、なければ run に記録された workspace です。適用前に現在の宛先 inventory の digest を baseline の digest と比較し、不一致なら競合として上書きを拒否します。一致すれば、baseline と選択した候補の内容を比較して変更ファイルを書き、候補にない baseline のファイルを削除します。通常適用前には宛先の rollback copy を run のディレクトリ内に作り、書き込み中に例外が発生するとそこから宛先を復元します。`--dry-run` は `would_write` / `would_remove` を返すだけで、候補ファイルの適用と rollback copy 作成を行いません。

`--restore` を同時に指定すると CLI は `restore_original()` の分岐へ進むため、`--attempt` は適用に使われません。`--state-dir` が指定されていればその run 保存先を使い、省略時は `STRATA_TIMESKIP_DIR`、さらに未設定なら Strata の state base 配下 `time-skip` を使います。

## 適用条件と副作用

- run の記録から指定番号の attempt が復元でき、attempt のディレクトリが残っている必要があります。
- destination は run 開始時の baseline と一致している必要があります。変更が検出されると、利用者の編集を保護するため適用しません。
- 成功時は宛先のファイルを作成・上書き・削除し、run 配下に `rollback` copy を残します。失敗時は rollback copy から復元を試みます。
- `--attempt` は run の `selected_checkpoint` や decision を更新しません。適用元として一時的に選択され、成功結果には `attemptN` として記録されます。

## 出力とエラー

Human 出力では dry-run 時に `would write:` と必要に応じ `would remove:`、実適用成功時に `applied ...` と `rollback copy: ...` を表示します。`--output json` では成功結果を `apply` オブジェクトに包んで JSON 出力します。

run が見つからない、番号に対応する attempt がない、attempt の候補ディレクトリがない、または baseline がない場合はエラーコード 2 です。宛先 digest の競合、または適用失敗（rollback を試行）ではコード 6 です。Human エラーは stderr に `strata: ...`、JSON モードでは `ok: false` と `error.code` / `error.message` を出力します。

## 根拠

- `strata_cli/cli.py:380-393` — `apply` parser の引数定義。`--attempt` は `type=int`、既定値 `None`。
- `strata_cli/cli.py:1524-1555` — run の再読込、`--restore` 分岐、attempt の転送、競合・失敗の終了コード、出力。
- `strata_cli/cli.py:527-532,535-542,1605-1618` — Human/JSON のエラー・成功出力と、永続化した attempt/checkpoint の復元。
- `strata_control/time_skip.py:302-310,442-472` — attempt の index/path と attempt 番号の生成、保持。
- `strata_control/time_skip.py:597-652` — 適用元の選択、候補確認、baseline digest 比較、dry-run、rollback とファイル反映。
- `strata_control/time_skip.py:654-664` — `--restore` に対応する baseline 復元処理。
