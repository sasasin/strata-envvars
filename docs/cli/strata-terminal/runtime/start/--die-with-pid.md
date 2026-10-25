# `--die-with-pid`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--die-with-pid` |
| 別名 | なし |
| 値 | `PID`（整数） |

## 役割

指定したプロセスが終了したとき、起動した runtime instance も停止させます。通常 `runtime start` は呼び出した端末や CLI プロセスが終了しても動作し続けます。このオプションを付けると、アプリケーションなど所有プロセスの寿命に runtime を結び付けられます（`strata_cli/cli.py:197-208`、`strata_control/runtime.py:522-530`）。

## 使い方

```sh
strata runtime start --profile my-profile --die-with-pid 12345
```

`--profile` は必須です。`12345` は実際に実行中で、Strata が開始時刻を読み取れるプロセスの PID に置き換えてください（`strata_cli/cli.py:203-212`、`strata_control/runtime.py:531-539`）。

## 値と既定値

値を1つ取り、`argparse` の `type=int` で整数に変換されます。省略時は `None` で、プロセス追跡は行われません（`strata_cli/cli.py:207-208`、`strata_control/runtime.py:518-521`）。

通常起動では、PID が正の整数で、開始時刻 token を取得できる実行中のプロセスである必要があります。0、負数、存在しない PID、終了済みプロセス、または開始時刻を読み取れないプロセスは `start_token()` が `None` を返し、「the process to follow with --die-with-pid is not running」として拒否されます。開始時刻 token は Linux の `/proc`、Windows の process 情報、または `psutil` 等を使って取得します（`strata_control/procs.py:47-75`、`strata_control/runtime.py:532-537`）。

## 実行時の動作

runtime の起動処理は指定 PID の開始時に token を記録し、owner host の起動引数へ PID と token の両方を渡します。監視中は現在の PID の token と記録値を比較し、一致しなくなると追跡対象が終了したものとして owner host を終了させます。PID が再利用されても、開始時刻が異なる新しいプロセスを元の対象と誤認しない設計です（`strata_control/runtime.py:531-537`、`strata_control/runtime.py:561-574`、`strata_control/runtime.py:1293-1296`、`strata_control/procs.py:47-50`）。

owner host の終了処理は稼働中の engine/server 子プロセスを停止します。POSIX では子プロセスへ `SIGTERM` を送り、Windows では owner pipe を閉じます。`--shutdown-timeout` の期限に追加の8秒を加えた時間内に終了しない場合は子プロセスツリーを kill し、停止 deadline 超過を記録します（`strata_control/runtime.py:990-1012`、`strata_control/runtime.py:1328-1351`）。

`--plan` を同時に指定すると、plan 経路は `die_with_pid` を runtime 起動処理に渡しません。そのため plan は PID の存在を検証せず、表示する計画にも PID 追跡は含まれません（`strata_control/management.py:202-230`）。

## 適用条件と副作用

- 対象は `strata runtime start` です。`runtime start` は saved profile の owner host をバックグラウンドサービスとして起動し、指定がなければ端末・呼び出し元プロセスから独立して稼働します（`strata_cli/cli.py:197-208`、`strata_control/runtime.py:522-530`）。
- 通常起動では対象 PID を確認してから profile の起動候補を検査し、owner host を作成します。PID が無効な場合は runtime instance の起動前に失敗します（`strata_control/runtime.py:531-547`）。
- 対象プロセスが終了すると、owner host は runtime instance を終了させ、状態ファイルや制御 socket 等を終了処理で片付けます（`strata_control/runtime.py:1293-1296`、`strata_control/runtime.py:1328-1351`）。
- オプション単独の環境変数・設定ファイルによる上書きは確認できません。

## 出力とエラー

PID 値を整数にできない場合は `argparse` の引数エラーになります。整数でも通常起動時に実行中プロセスとして確認できなければ、`ProfileError` が CLI のエラー処理に渡され、human 出力では stderr に `strata: ...`、JSON 出力では JSON の error object が出て、既定の終了コード 2 になります（`strata_cli/cli.py:527-532`、`strata_cli/cli.py:2166-2173`、`strata_control/runtime.py:532-537`）。

owner host が起動に失敗した場合は runtime log の場所を示すエラー（終了コード 6）、起動待機中に期限を超えた場合は `startup_wait_expired`（終了コード 8）を返します。これらは `--die-with-pid` 固有のエラーではなく、runtime start の失敗経路です（`strata_control/runtime.py:577-599`）。

## 根拠

- `strata_cli/cli.py:197-212` — `runtime start` parser と `--die-with-pid` の定義。
- `strata_cli/cli.py:1345-1356` — CLI から management 層への引数転送。
- `strata_control/management.py:188-230` — 通常起動と `--plan` の分岐、通常起動から runtime への転送。
- `strata_control/runtime.py:518-547` — PID token の取得と未実行 PID の拒否。
- `strata_control/runtime.py:561-574` — owner host 子プロセスへの PID/token 引き渡し。
- `strata_control/runtime.py:990-1012`、`strata_control/runtime.py:1293-1296`、`strata_control/runtime.py:1328-1351` — 対象終了の検知、子プロセス停止、終了時の後処理。
- `strata_control/procs.py:47-75` — PID の開始時刻 token の取得方法。
- `strata_cli/cli.py:527-532`、`strata_cli/cli.py:2166-2173` — CLI の human/JSON エラー出力と終了コード。
- `docs/cli/README.md:388-400` — `strata runtime start` の階層と索引リンク。

## 調査範囲

記載は上記 commit のソースコードに基づきます。同一 revision の `--help` は実行していません。Release artifact や各 OS 上での実際のプロセス情報取得可否は確認していません。
