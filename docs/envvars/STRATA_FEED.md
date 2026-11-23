# `STRATA_FEED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_FEED` は、Strata Terminal の POSIX シェル版および Windows PowerShell 版インストーラが、Terminal のリリースファイルを取得するベース URL を指定する。未設定または空文字なら GitHub Releases の `latest/download` を使う。指定値は `install-manifest.txt` と、manifest が指定するアーカイブの取得先になり、展開後の Terminal に署名付き feed を確認させる `strata update --check --no-engine --feed <値>` にも渡される（`tools/packaging/install.sh:24-25,132-146,163-174`、`tools/packaging/install.ps1:29-30,119-137,184-195`）。

これはインストーラが読む変数であり、通常起動中の Strata が `STRATA_FEED` を直接読む実装は見つからなかった。インストーラの署名確認時は明示的な `--feed` が使われるため、`strata update` の `STRATA_UPDATE_FEED` や記憶済み feed よりもインストーラが選んだ feed が優先される（`terminal/strata_cli/update_cmd.py:142-151`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| POSIX `install.sh` | `https://github.com/Niko1221/Strata/releases/latest/download` を使用 | 空でない任意の文字列。例: `https://example.org/strata` | 空文字は無効値エラーにならず既定 URL を選ぶ。非空値でも形式の事前検証はなく、URLや取得内容が不正なら後続の取得・manifest・チェックで失敗する |
| Windows `install.ps1` | `https://github.com/Niko1221/Strata/releases/latest/download` を使用 | PowerShell の条件式で真となる文字列。例: `https://example.org/strata` | 空文字は既定 URL を選ぶ。空白だけの値は空文字ではないので採用され、URLとしての妥当性は事前検証されない |

POSIX 版は `${STRATA_FEED:-<既定値>}` を用いるので、未設定と空文字のどちらも既定値になる。続けて末尾の `/` を 1 個だけ取り除く。したがって `https://host/feed///` は `https://host/feed//` となる。PowerShell 版は `if ($env:STRATA_FEED)` で未設定または空文字を除外し、採用した値から末尾の `/` をすべて取り除く（`tools/packaging/install.sh:24-25`、`tools/packaging/install.ps1:29-30`）。

値全体への真偽値・数値・大小文字変換はなく、`true`、`0`、空白などを特別扱いしない（ただし空文字は上記のとおり既定値）。URL構文も読み取り時点では検証されない。POSIX 版の後続チェック `[ -n "$FEED" ]` は既定値が非空なので通常の unset/empty 入力では通り、PowerShell 版の `if (-not $feed)` も既定 URL 選択後の空値確認となる（`tools/packaging/install.sh:32`、`tools/packaging/install.ps1:100-102`）。

## 有効になる条件

- POSIX では `tools/packaging/install.sh`、Windows では `tools/packaging/install.ps1` を実行すること。変数の読み取りはこの2つのインストーラにある。
- インストーラが対応 OS / CPU を受け付けること。POSIX 版は Linux x86_64、Linux aarch64、macOS arm64 を分岐で扱い、PowerShell 版は Windows x64 を扱う（`tools/packaging/install.sh:59-67`、`tools/packaging/install.ps1:103-106`）。
- 指定先が必要な `install-manifest.txt` とそこに記載された Terminal アーカイブを返すこと。manifest に現在の platform の行がなければインストールを止める（`tools/packaging/install.sh:137-146`、`tools/packaging/install.ps1:119-137`）。
- アーカイブの SHA-256 が manifest の値と一致し、展開後に Strata の起動ファイルが見つかること。これらは feed の値を有効にする条件ではなく、インストールを続行するための後続条件である（`tools/packaging/install.sh:145-160`、`tools/packaging/install.ps1:136-138,172-177`）。
- 展開後の署名確認は同じ feed に対して明示的な `--feed` を渡す。`update_cmd._feed_source` は `a.feed` が真ならそれを返し、その後に `STRATA_UPDATE_FEED` を見る（`tools/packaging/install.sh:168-170`、`tools/packaging/install.ps1:184-188`、`terminal/strata_cli/update_cmd.py:142-151`）。

## 実行時の詳細

各インストーラスクリプトの開始時に feed の値をローカル変数へ一度取り込み、その実行中は `$FEED` / `$feed` を使う。実行中にプロセス環境を変更して読み直す処理はない（`tools/packaging/install.sh:24-27`、`tools/packaging/install.ps1:29-32`）。

POSIX 版は `FEED/install-manifest.txt` を取得し、platform に一致する manifest 行の相対パスを使って `FEED/<相対パス>` からアーカイブを取得する。展開後は同じ FEED を `--feed` 引数で新しい Terminal に渡して `update --check --no-engine` を実行し、取得したリリースの署名付き feed を確認する（`tools/packaging/install.sh:132-146,163-174`）。PowerShell 版も同じ順序で manifest、アーカイブを取得し、`--feed $feed` を指定して署名確認する（`tools/packaging/install.ps1:119-137,184-195`）。

この feed は初回インストールに使う取得先である。インストール後の通常の `strata update` の既定値を環境変数として設定する処理は確認できない。署名確認コマンドの `--feed` は `STRATA_UPDATE_FEED` より優先されるが、以降の CLI 実行では `--feed`、`STRATA_UPDATE_FEED`、記憶済みの HTTPS feed、既定 feed の順に選択される（`terminal/strata_cli/update_cmd.py:142-151,154-158`）。

## ログと測定値

インストーラは選択した値を `Release folder: <値>` と表示する（`tools/packaging/install.sh:130`、`tools/packaging/install.ps1:110-112`）。取得失敗時は POSIX 版で `... did not answer ...`、platform 行がない場合は `this release has no Terminal for <platform>.`、チェックサム不一致時は `the download does not match the release's checksum ...` を stderr に出して終了する（`tools/packaging/install.sh:137,139,146`）。PowerShell 版も取得失敗、platform 行欠落、チェックサム不一致で停止し、署名確認が失敗すると新たに展開した内容を削除して、失敗した `strata` の出力と `the release folder's signed feed could not be verified ...` を表示する（`tools/packaging/install.ps1:120-125,132-137,190-193`）。

成功した署名確認は `Signature ok.`（POSIX）または `Signature ok.`（PowerShell）と表示される（`tools/packaging/install.sh:168-174`、`tools/packaging/install.ps1:184-195`）。性能測定値は該当しない。

## 根拠

- `tools/packaging/install.sh:24-32` — POSIX 版の既定値、末尾 slash 処理、空値確認。
- `tools/packaging/install.sh:132-174` — feed からの manifest / アーカイブ取得、検査、署名確認と失敗処理。
- `tools/packaging/install.ps1:29-32,100-102` — PowerShell 版の既定値、末尾 slash 処理、空値確認。
- `tools/packaging/install.ps1:119-137,179-195` — feed からの取得、チェックサム確認、署名確認と失敗処理。
- `terminal/strata_cli/update_cmd.py:142-151` — `--feed`、`STRATA_UPDATE_FEED`、記憶済み feed、既定 feed の選択順。
