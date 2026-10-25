# `STRATA_RUNTIME_PROFILE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata が起動した子プロセスの所有記録に runtime profile 名を付けます。runtime 管理のサーバーが engine や vision process を起動すると、その記録に同じ profile 名が保存されます。後で `strata runtime start` / `stop` / `cleanup` が profile を指定して孤児プロセスを探す際、該当 profile の記録だけを対象にできます。

この変数は起動するプログラムや推論設定を選びません。プロセス記録の分類用メタデータです。

## 値と判定

| 状態 | 記録に渡す値 | 結果 |
|---|---|---|
| 未設定 | `None` | プロファイルなしで記録 |
| 空文字 | `None` | プロファイルなしで記録 |
| 空でない文字列 | 文字列をそのまま渡す | その文字列を `profile` フィールドに保存 |

`serve/lifeline.py` は `os.environ.get("STRATA_RUNTIME_PROFILE") or None` を使います。値の trim、大小文字変換、形式検査はしません。したがって空白だけの値も空でない文字列としてそのまま保存されます。`strata_control.procs.records(profile=...)` は記録値と指定値を完全一致で比較します。

runtime 管理のサーバー起動では、環境を親からコピーした後に `STRATA_RUNTIME_PROFILE` を runtime の profile 名で上書きして子サーバーへ渡します。親環境に別の値があっても、この起動経路では使われません。

## 有効になる条件

- `serve.lifeline.popen()` を通じて子プロセスを起動したとき、その呼び出し元プロセスの環境値が記録に使われます。対象は server が起動する engine / vision process などです。
- runtime 管理サーバーは `STRATA_RUNTIME_PROFILE` を自身の profile 名に設定して起動するため、そのサーバーから起動される子の記録が管理対象 profile に結び付きます。
- foreground `strata serve` など runtime 管理外の起動でも、環境変数を明示すれば子の記録にその値が付く可能性があります。未設定なら profile なしです。
- profile で絞った cleanup は、記録の `profile` が完全一致した子だけを走査します。親 process がまだ同一 process として稼働中なら、その子は孤児ではなく終了対象になりません。

## 実行時の詳細

`STRATA_RUNTIME_PROFILE` の直接の読み取りは `serve/lifeline.py` の `popen()` 内です。各子プロセス起動のたびに参照し、値を static cache しません。起動時に設定した環境をプロセス中に変更した場合は、その後に `popen()` する子の記録に反映されます。すでに書かれた記録は変わりません。

`strata_control.procs.write_record()` は値を JSON 記録の `profile` に格納します。`records(profile)` は指定値が `None` なら全記録を返し、それ以外なら profile が等しい記録に絞ります。`leftovers()` は該当記録の PID、開始 token、command line、親の生存を照合し、親が失われたと確認できるものだけを `end_leftovers()` が終了対象にします。値が合致するだけで実行中プロセスを終了する仕組みではありません。

runtime host はサーバー子プロセス自身の記録も `profile=self.name` として直接作ります。この経路では環境変数を読みません。env var は主にサーバー配下の lifeline 子プロセス記録に profile を伝える役割を持ちます。

記録書き込みが失敗しても起動を失敗させない best-effort の処理です。lifeline 側は記録処理の例外を握りつぶし、`write_record()` も記録不能時に `None` を返します。その場合、将来の profile 絞り込み cleanup は該当子を記録から回収できません。

## 文書との照合

`docs/TERMINAL.md` は runtime が lost owner の server / engine を回収し、profile を指定できることを説明しています。以下の実装はその所有記録を profile 別に検索する仕組みと一致します。同文書は環境変数そのものの値規則までは記載していません。

## 根拠

- `serve/lifeline.py:235-269` — 子起動処理と、起動ごとの環境読み取り・記録呼び出し。
- `strata_control/procs.py:179-199,229-240` — `profile` を記録し、完全一致で検索。
- `strata_control/procs.py:245-267,307-318` — 親 process の生存を含む孤児判定と、検証済み記録の終了処理。
- `strata_control/runtime.py:793-827,835-840` — runtime profile 名をサーバー子環境へ設定し、サーバー自身を profile 付きで記録。
- `strata_control/runtime.py:505-516,600-628` — runtime の開始・停止・cleanup で profile 付き孤児回収。
- `docs/TERMINAL.md:61-67,94` — runtime の起動と lost owner 回収の説明。
