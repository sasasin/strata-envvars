# `STRATA_NODE_VERSION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

desktop アプリに同梱する Node.js 実行ファイルを取得・確認する開発・パッケージ作業用スクリプトのバージョン指定です。`apps/desktop/scripts/fetch-node.sh` と Windows 用の `fetch-node.ps1` が環境から直接読み取ります。Strata アプリの通常起動時にこの環境変数を読むコードは確認できません。Node runtime はバンドル内の `node` / `node.exe` を選び、開発時の候補パスにも `v24.12.0` が固定されています（`apps/desktop/src-tauri/src/main.rs:309-335`）。

## 値と判定

どちらのスクリプトも環境変数の文字列を数値や SemVer として parse せず、バージョン文字列として URL、アーカイブ名、アーカイブ内パスに埋め込みます。

| 実行経路 | 未設定・空文字 | 非空文字列 | 検査と結果 |
|---|---|---|---|
| Bash (`fetch-node.sh`) | `${STRATA_NODE_VERSION:-24.12.0}` により、未設定と空文字は `24.12.0` | 文字列全体をそのまま採用。形式・範囲検証なし | `--check` では installed Node の出力が厳密に `v${NODE_VERSION}` と一致するか確認。不一致は stderr に `fetch-node: expected v...`、終了コード 1。取得時は対象向けアーカイブを組み立てる。 |
| PowerShell (`fetch-node.ps1`) | `if ($env:STRATA_NODE_VERSION)` が偽になるため未設定と空文字は `24.12.0` | 文字列全体をそのまま採用。形式・範囲検証なし | `-Check` では installed Node の出力と `v${NodeVersion}` を完全一致比較。不一致は `Fail` の stderr 出力、終了コード 1。 |

空白だけの値や不正なバージョン表記も非空なら採用されます。入力を trim したり、semver の大小関係を判定したりする処理はありません。コメント上の App Host 要件は Node `>= 24.12.0` ですが、取得スクリプトはこの下限を検証しません（`apps/desktop/scripts/fetch-node.sh:18-21`, `apps/desktop/scripts/fetch-node.ps1:11-20`; 要件記載は `apps/host/package.json:47-49`）。

## 有効になる条件

- Bash スクリプトを明示的に実行した場合、または Windows で PowerShell スクリプトを明示的に実行した場合にだけ値が評価されます。`packaging/README.md:55-68` は同梱 Node の取得・確認手順として両スクリプトを案内しています。
- Bash は `--target` で対象 platform を選べます。Node version と対象名を組み合わせて URL とアーカイブ名を作ります（`apps/desktop/scripts/fetch-node.sh:40-53,63-75`）。PowerShell 側の対象は `win-x64` 固定です（`apps/desktop/scripts/fetch-node.ps1:20-25,37-49`）。
- `--check` / `-Check` ではダウンロードを行わず、既存の実行ファイルの version だけを比較します。`-FromFile` は PowerShell のダウンロード元を変えますが、期待するバージョンやアーカイブ内パスには同じ環境変数の値が使われます（`apps/desktop/scripts/fetch-node.sh:56-61`; `apps/desktop/scripts/fetch-node.ps1:29-35,37-45,64-67`）。これらの CLI 引数は環境変数の version 値を上書きしません。
- Bash の digest は対象 platform ごとの記録値で、version ごとの選択ではありません。対象に記録 digest があれば、別 version の正常なアーカイブでも通常その digest と一致せず拒否されます。対象に digest がなければ警告を出して未認証のまま続行します（`apps/desktop/scripts/fetch-node.sh:30-38,74-93`）。
- PowerShell は version が `24.12.0` と異なると、digest の一致確認を行わず警告を出して続行します。`24.12.0` では記録済み digest と異なるアーカイブを拒否します（`apps/desktop/scripts/fetch-node.ps1:22-23,51-60`）。

## 実行時の詳細

両スクリプトはプロセス開始後、スクリプト本体の冒頭で一度だけ値を変数に読み込み、その実行中はその値を使います。環境変更を再読込するループや cache はありません。子プロセスに環境変数を転送する処理も見つかりません。

取得モードでは version を使って nodejs.org の URL を作り、その URL を表示してダウンロードします。Bash では `curl` が失敗すると `set -e` により後続処理へ進まず、PowerShell では `$ErrorActionPreference = 'Stop'` のもとで Web request のエラーが停止経路になります（`apps/desktop/scripts/fetch-node.sh:19,63-80`; `apps/desktop/scripts/fetch-node.ps1:18,37-50`）。ハッシュ検証失敗は `REFUSING` を stderr に出して終了コード 1、digest 未登録または PowerShell の非既定 version は `WARNING` と計算済み SHA-256 を stderr に出し、その後インストールへ進みます（`apps/desktop/scripts/fetch-node.sh:81-103`; `apps/desktop/scripts/fetch-node.ps1:51-69`）。

`--check` / `-Check` の出力は、成功時に現在の Node version を表示して終了コード 0、不在時または version 不一致時にエラーを表示して終了コード 1 です（`apps/desktop/scripts/fetch-node.sh:56-61`; `apps/desktop/scripts/fetch-node.ps1:29-35`）。取得スクリプトは結果を desktop resource directory に配置します。通常アプリの起動コードはそこにある Node を選びますが、`STRATA_NODE_VERSION` 自体を起動時の runtime 選択に使いません（`apps/desktop/src-tauri/src/main.rs:309-335`）。

候補一覧 `docs/envvars/000_envvers.md:1131` に名前があります。候補名の全参照検索では上記2スクリプトに加えて、`packaging/README.md` の説明と `tests/desktop/test_fetch_node.py:26-27` の既定値整合確認が見つかりました。テスト参照は実装動作の根拠にはしていません。共通 env helper や動的な変数名を介した追加の読み取りは見つかりませんでした。

## 根拠

- 直接読み取りと既定値: `apps/desktop/scripts/fetch-node.sh:21`; `apps/desktop/scripts/fetch-node.ps1:20`
- CLI、取得 URL、digest、インストールとログ: `apps/desktop/scripts/fetch-node.sh:30-103`; `apps/desktop/scripts/fetch-node.ps1:22-71`
- packaging 手順: `packaging/README.md:55-79`
- App Host が要求する Node 下限: `apps/host/package.json:47-49`
- desktop runtime が選ぶ実行ファイル: `apps/desktop/src-tauri/src/main.rs:309-335`
