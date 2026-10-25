# `--boot-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--boot-timeout` |
| 別名 | なし |
| 値 | 秒数。`float` として解析される値 |

## 役割

再チェックの測定用 worker を起動した後、ローカルの `/health` が応答するまで待つ時間を指定します。測定リクエスト自体の待ち時間や、コマンド全体の実行時間を制限するオプションではありません。

## 使い方

```sh
strata presets recheck PRESET PROFILE --boot-timeout 1200
```

`PRESET` は再チェックする保存済み preset、`PROFILE` はその preset が属する profile 名または run configuration です。

## 値と既定値

- parser は `type=float`、既定値 `900.0` 秒（15 分）です。非数値の文字列は `argparse` の引数解析で拒否されます。
- 独自の正値・範囲検証はありません。0 以下も数値として受理されますが、worker 起動後の readiness 待ちループに入らず、`TIMEOUT` 扱いになります。
- 小数値は deadline の計算にそのまま使われます。エラー文に表示する秒数は `int()` で整数化されます。

## 実行時の動作

`strata presets recheck` の parser が受け取った値は、`_recheck()` から `WorkerSession(boot_timeout_s=...)` に渡されます。各 worker 起動では、GPU lock と起動前処理を終え、起動用ファイルを準備した後、プロセス起動直前に deadline の基準時刻を記録します。プロセス開始後は deadline まで、認証付きで `http://127.0.0.1:<port>/health` を最大 2 秒の要求として確認し、失敗時は 0.5 秒間隔で再試行します。HTTP 200 が返れば起動完了です。

この timeout は各 worker 起動ごとに適用されます。通常は preset 設定での起動に使われ、保存時より prompt 測定が遅い場合の再測定、および engine の `tuning_epoch` が変わっている場合の標準設定との比較にも、それぞれ起動があれば適用されます。コマンド全体の経過時間には上限を設けません。

再チェック開始前に preset と現在の PC の状態を照合し、状態が `hard` の場合は worker を起動せず終了します。soft stale を含むそれ以外の状態では測定に進みます。timeout 到達は `StartFailed("TIMEOUT", ...)` となり、再チェック結果は `retune` として記録されます。これは再調整の提案であり、保存済み設定を自動で差し替えません。

## 適用条件と副作用

- worker は `serve.server` の子プロセスとして起動し、loopback の host と空き port を使います。起動用 JSON、worker log、engine log を `--work-dir`（省略時は `strata-recheck-` 接頭辞の一時ディレクトリ）に作成します。
- 起動後は再チェック要求を測定します。終了時には worker を terminate し、60 秒以内に終了しなければ kill を試みます。GPU メモリーの解放待ちとして終了処理後に 3 秒待ちます。
- 完了した結果は preset に保存されます。`keep` の場合は最終成功時刻と identity を更新し、測定値が既存の decode 速度を 3% 超えた場合は測定値も更新します。その他の verdict も `last_result` として保存されます。
- `--output json` は `presets` parser 共通の出力指定です。`--gpu-lock` が使う lock、`--serve-dir`、`--work-dir`、`--status-file` は worker の排他・場所・進捗出力に関係しますが、boot timeout の値を変更しません。

## 出力とエラー

- worker が deadline までに `/health` で応答しない場合、失敗理由は `the engine was not ready within N s` となります。再チェック関数はこれを測定失敗として扱い、`retune` verdict を返し、preset に記録した後、human 出力では再調整を案内します。JSON 出力では verdict と理由を含む結果を stdout に出します。
- worker が先に終了した場合は log と return code から起動失敗種別を判定します。プロセス自体を開始できない場合は `FAIL_BOOT` です。これらも測定失敗として扱われます。
- preset が hard stale の場合は「この PC は変わりすぎている」と stderr（human）または JSON（`--output json`）に出し、終了コード 5 で終了します。これは boot timeout による失敗ではありません。
- その他の `PresetError` は終了コード 5、`OSError` / `ValueError` は例外の `exit_code`（なければ 2）で `_fail()` に渡されます。human 形式の失敗は `strata: ...` として stderr に出力します。

## 根拠

- `strata_cli/tune_commands.py:49-55,82-90` — `presets recheck` の parser 階層、共通 `--output`、`--boot-timeout` の型・既定値。
- `strata_cli/cli.py:486-488,2151-2152` — parser 登録と `presets_command()` への dispatch。
- `strata_cli/tune_commands.py:103-108,126-136,149-157,289-348,411-448` — 出力・失敗形式、worker 設定、hard-stale 判定、timeout の引き渡し、結果の保存。
- `strata_control/tune_session.py:420-435,443-489,491-522` — `boot_timeout_s`、GPU lock 順序、worker 起動、deadline・health 確認、失敗時の worker 終了処理。
- `strata_control/autotune.py:885-955` — preset 設定を適用した測定、再測定・baseline 起動条件、起動失敗の `retune` 化。
- `strata_control/presets.py:412-429` — 再チェック結果の保存と `keep` 時の更新。

調査範囲は上記 checkout の parser と Python 実装です。Release artifact や実機ごとの worker 起動時間は調査・測定していません。
