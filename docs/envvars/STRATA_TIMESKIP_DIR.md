# `STRATA_TIMESKIP_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で変更なし。

## 役割

Time-skip の実行記録（run state）を置くディレクトリを指定します。端末 CLI と App Host の両方で使われ、run の作成、一覧・状態の読み取り、適用時の保存先を同じ場所にします。モデルや GPU backend の条件ではなく、Time-skip CLI または App Host の Time-skip 経路で使われるパス設定です。

## 値と判定

| 状況 | 保存先 |
|---|---|
| CLI の `--state-dir` が空でない | その引数を `Path` として使用。環境変数より優先 |
| `--state-dir` が未指定または空、環境変数が空でない | `STRATA_TIMESKIP_DIR` の値をそのまま `Path` として使用 |
| `--state-dir` が未指定または空、環境変数が未設定または空文字 | OS ごとの既定 state 配下の `time-skip` |

値は真偽値や数値として parse されず、空かどうかだけ判定されます。空白だけの値も空文字ではないためパスとして採用されます。値の trim、絶対パス化、存在確認、範囲制限はこの選択箇所では行いません。相対パスもそのまま使われます。

既定パスは POSIX では `$XDG_STATE_HOME/strata/time-skip`（`XDG_STATE_HOME` が空または未設定なら `~/.local/state/strata/time-skip`）、Windows では `%LOCALAPPDATA%\Strata\time-skip`（`LOCALAPPDATA` が空または未設定ならユーザー home の `AppData\Local\Strata\time-skip`）です。`HOME` / `homedir()` は POSIX の home fallback に関係します。

根拠: `strata_cli/cli.py:366-368,1476-1484`; `strata_control/paths.py:13-21`; `apps/host/server/platform-paths.mjs:16-33`。

## 有効になる条件

- `strata timeskip run`, `list`, `status`, `apply` の state store が対象です。各サブコマンドには `--state-dir` があり、空でない指定が環境変数より優先します（`strata_cli/cli.py:366-393,1476-1485`）。
- App Host の Time-skip 経路でも有効です。Host は起動時に `process.env` をコピーして `createTimeSkip` に渡し、`STRATA_TIMESKIP_DIR` が未設定なら空文字を明示した環境スナップショットを作ります（`apps/host/server/index.mjs:907-912`）。Node 側では空文字を未指定と同じ扱いにします。
- Host は `timeSkipDir()` の選択結果を Python 子プロセスの `STRATA_TIMESKIP_DIR` として上書きして渡します。従って Host 経由では子 CLI の `--state-dir` は Host から付与されず、保存先は Host が選んだ値になります（`apps/host/server/timeskip.mjs:302-309,446-455`）。
- Host 既定値も CLI と同じ state-base 規則を使います。OS 差は POSIX / Windows のパス組み立てだけで、GPU backend や build macro の条件はありません（`apps/host/server/platform-paths.mjs:17-33`; `strata_control/paths.py:13-21`）。

## 実行時の詳細

CLI は `_timeskip()` の実行時に `os.environ.get("STRATA_TIMESKIP_DIR")` を読みます。設定値は同じ呼び出し内で `TimeSkipStore` の root に使われ、`run` ではさらに `TimeSkipRun` に渡されます。CLI プロセス起動時の module-level cache はありません。保存先ディレクトリは `TimeSkipStore` / `TimeSkipRun` の初期化時に `mkdir(parents=True, exist_ok=True)` で作成されます（`strata_cli/cli.py:1476-1485,1570`; `strata_control/time_skip.py:341,695-700`）。

App Host の Node 側は `platform-paths.mjs` の関数呼び出し時に渡された env object から値を選びますが、通常の Host 起動経路でその object は `index.mjs` 初期化時に作ったコピーです。Host の起動後に `process.env` を変更しても、この Time-skip インスタンスの保存先には反映されません。各コマンド起動時には選択済み root を子プロセスに設定し、Python CLI がその値を読み直します（`apps/host/server/index.mjs:907-912`; `apps/host/server/timeskip.mjs:25-27,302-309,446-455`）。

環境変数値の内容を通知する専用ログは見当たりません。CLI は空の一覧なら `no Time-skip runs recorded` を表示します（`strata_cli/cli.py:1487-1498`）。保存先に作成・読み書きできない場合はディレクトリ I/O が失敗し、Host は子コマンドの終了コードと stderr をエラー応答に使います。Host の detached 起動は新しい run record が 20 秒以内に現れなければ起動失敗または記録未作成として失敗を返します（`apps/host/server/timeskip.mjs:302-321,446-483`）。

相対値はこの変数の処理で絶対化されません。CLI は自身の current working directory 基準で扱い、Host 子 CLI は `cwd: repoRoot` で起動されます。一方 Host 自身のファイル操作は Node プロセスの working directory 基準です。したがって相対値を指定した場合、Host と子 CLI の working directory が異なる構成では同じ文字列が別の場所を指す可能性があります（`apps/host/server/timeskip.mjs:304-308,454-455`; `strata_cli/cli.py:1479-1485`）。

## 根拠

候補名の全参照は `rg` で確認しました。実際の環境読み取りは `strata_cli/cli.py:1479` と Host の `apps/host/server/index.mjs:911`、Host の path helper `apps/host/server/platform-paths.mjs:31-32` です。`apps/host/server/timeskip.mjs:308,455` は選択済み root を子プロセスへ転送する箇所です。その他の候補名参照には CLI help、テスト用 env fixture、Harness の説明コメントが含まれますが、それらを本番の読み取り根拠にはしていません。

関連記述として `strata_control/paths.py:1-5` は CLI と Node Host が同じ state folder 規則を使うと説明しています。`docs/work/QUALIFICATION-KIT.md:218` に Time-skip 実装への言及はありますが、`STRATA_TIMESKIP_DIR` の値判定・優先順位に関する追加説明は見つかりませんでした。
