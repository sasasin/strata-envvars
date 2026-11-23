# `STRATA_HANDOVER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`strata` コマンドの起動直後に走る「新しい Control への引き継ぎ（hand-over）」を、この変数が設定されているプロセスでは行わないための目印。`strata update` は新しい Control を `<components>/control/<ver>/` に置き `active.json` を書き換えるが、PATH 上の Terminal は別インストールなので、旧 Terminal の `strata.py` が起動時に新しい Control の同梱 interpreter と `strata.py` で同じ引数を実行し直す。この引き継ぎは `terminal/strata_cli/handover.py` の `maybe_hand_over()` が担い、`terminal/strata.py:46` から呼ばれる。`STRATA_HANDOVER` は「引き継ぎ済みのプロセス」を示し、連鎖（無限ループ）を止める。

変数自体は値を解析しない。設定されている（空でない）だけで引き継ぎを抑止し、それ以外の CLI の挙動・生成結果・エンジン設定は変えない。`terminal/strata_cli/handover.py:22`（`ENV_GUARD`）、`:130`、`:181`。

同じ語を含むが無関係な実装: `app/host/src/lib/chat-sync.ts:170` の `HANDOVER_LEASE_MS`（チャットの持ち主交代）と `terminal/serve/split.py:357` の `wants_handover()`（split serve のセッション引き継ぎ）で、どちらも本変数を読まない。

## 値と判定

読み取りは `environ.get(ENV_GUARD)` の真偽値判定のみ（`handover.py:130`、`:181`）。`strip`・小文字化・数値変換・`"1"` との比較は行わない。したがって空でない文字列はすべて「設定あり」で、`1` 以外も効く。

| 値 | `maybe_hand_over`（`handover.py:130`） | `refuse_old_updater`（`handover.py:181`） |
|---|---|---|
| 未設定 | 引き継ぎを試みる | 条件が揃えば拒否する |
| 空文字 `""` | 未設定と同じ（引き継ぎを試みる） | 未設定と同じ |
| `1` | 引き継ぎしない | 拒否しない |
| `0` / `false` / `no` / `disable` | 引き継ぎしない（非空のため） | 拒否しない |
| 空白のみ `" "` | 引き継ぎしない（非空のため） | 拒否しない |

`refuse_old_updater` 側の判定は `list(argv) != ["--version"] or environ.get("STRATA_NO_ACQUIRE") != "1" or environ.get(ENV_GUARD)` の 3 条件（`:181`）。ここだけ `STRATA_NO_ACQUIRE` は文字列完全一致 `"1"` で比べる点が異なる。

## 有効になる条件

- `terminal/strata.py` の起動経路であること。`handover.py` の判定は `terminal/strata.py:43-48` で `refuse_old_updater()` の後、`maybe_hand_over()` として一度だけ走る。他のサブコマンド実装やエンジン・サーバーは本変数を読まない（テストを除く `rg` の参照は `handover.py` と `updater.py:1890` のみ）。
- 引き継ぎ対象が存在すること。`find_target()` が新しい Control を見つけない（`active.json` なし・同版以下・不完全）場合、`STRATA_HANDOVER` の有無で結果は変わらない（`handover.py:70-114`）。
- ソース checkout から実行していないこと。`(パッケージ親)/.git` がある場合は `root` 未指定かつ `STRATA_HANDOVER_IN_CHECKOUT` 未設定なら `:132-133` で即 `None` を返すため、checkout では本変数は意味を持たない。`STRATA_HANDOVER_IN_CHECKOUT` はテスト用（`:24` のコメント）。
- `STRATA_NO_HANDOVER` とは `:130` で同じ効果だが、`:181` では見ないため、ステージ済み Control の `--version` 拒否（後述）は抑止しない。
- プラットフォーム差は引き継ぎの実行方法のみ（`:151-163`）。判定規則は同じ。

## 実行時の詳細

- 評価時期: プロセス起動ごとに 1 回。`strata` の各コマンドは新しいプロセスなので、実行中に環境を変えても現在のプロセスには反映されない。`static` な cache は無い。
- 設定すると `maybe_hand_over()` は `:130` で即 `None` を返し、`terminal/strata.py:46-48` はそのまま `strata_cli` の通常処理へ進む（`execve` も `subprocess.call` も呼ばない）。
- 引き継ぎを行う側は、子プロセスの環境を `dict(environ)` に `STRATA_HANDOVER=1`・`PYTHONNOUSERSITE=1` を加え、`PYTHONHOME` と `PYTHONPATH` を削除して作る（`handover.py:117-123`）。POSIX では `os.execve` でプロセスを置き換え（`:153`）、Windows では `subprocess.call` の終了コードを `strata.py:47-48` の `SystemExit` で返す（`:157-158`、`KeyboardInterrupt` は 130）。
- 引き継がれた新しい Control も起動時に `maybe_hand_over()` を通るが、環境に `STRATA_HANDOVER=1` があるため `:130` で止まり、再引き継ぎは起きない。この値はその Control が起動する子プロセスにも引き継がれる（子環境は `dict(os.environ)` から作られる: `terminal/strata_control/updater.py:1019`、`terminal/strata_control/gpu_roles.py:542`）。本変数を削除する処理は無い。
- 更新側の用途: `strata update` はステージした Control を `--version` で試験起動するとき、`STRATA_NO_ACQUIRE=1` とともに `STRATA_HANDOVER=1` を渡す（`terminal/strata_control/updater.py:1889-1891`）。これにより新 Control は自分自身を検証して版を出力し、引き継ぎを試みない。古い Terminal（引き継ぎコードを持たない）はこの変数を渡さないため、`refuse_old_updater()` が `:181-187` で一文を出力して終了コード 7 を返し、旧 updater は旧 Control を残す。

## ログと測定値

本変数自体はログを出さない。設定されている場合、引き継ぎの試行・警告は一切出力されず、通常のコマンド出力だけになる（`handover.py:130-131` で `warn` に到達しない）。

`STRATA_HANDOVER` が無く、引き継ぎ先が壊れている／起動できない場合にだけ stderr へ 1 行出る（`handover.py:142-145`、`:155`、`:162`）:

- `strata: a newer Control <ver> was installed but <problem>; running <old> instead.` に続けて `` Run `strata update` again to repair it. ``（`problem` は `its pointer names a folder outside the control folder` / `its version (...) cannot be read` / `<folder> is missing its interpreter or entry point`）
- `strata: could not start the updated Control <ver> (<理由>); running <old> instead.`

`refuse_old_updater()` の一文は stdout へ出る（`:186`）: `This Terminal cannot switch to the new Control by itself. Run the Strata install command once more to update it.`（`:169`、終了コード 7 は `:170`）。

測定値の記載は無い。`docs/` に本変数の記述は無く、`docs/release-notes-0.2.2.md` は引き継ぎ機能自体（0.2.1.3 / Control 0.1.46.2）に触れるのみ。

## 根拠

- `terminal/strata_cli/handover.py:22-24`（変数名の定義）
- `terminal/strata_cli/handover.py:117-133`（子環境への設定、`:130` の真偽値判定、checkout 除外）
- `terminal/strata_cli/handover.py:138-163`（引き継ぎ本体、警告文言、POSIX/Windows の分岐）
- `terminal/strata_cli/handover.py:166-187`（`refuse_old_updater` の 3 条件と一文）
- `terminal/strata.py:43-48`（起動順と終了コードの反映）
- `terminal/strata_control/updater.py:1883-1901`（ステージ済み Control の試験起動に渡す環境）
- `terminal/tests/terminal/test_handover.py:62-80`（`STRATA_HANDOVER=1` で引き継がないことの確認）
