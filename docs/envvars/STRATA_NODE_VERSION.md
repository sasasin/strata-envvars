# `STRATA_NODE_VERSION`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、デスクトップアプリに同梱する Node.js を取得する `app/desktop/scripts/fetch-node.sh` と Windows 用 `fetch-node.ps1` が使うバージョン文字列です。未設定または空文字なら `24.12.0` を選び、値をアーカイブ名・取得 URL・展開対象パス・`--check` の期待バージョンに埋め込みます。これは Strata エンジンの実行時設定ではなく、Node sidecar を準備するパッケージ作業用の入力です（`app/desktop/scripts/fetch-node.sh:21,63-72,95-103`; `app/desktop/scripts/fetch-node.ps1:20-24,37-45,64-69`）。

取得スクリプトがインストールする sidecar は `resources/node` に置かれ、Tauri の resource 設定でアプリへ同梱されます。アプリは同梱 Node が存在すればそれを選び、なければ開発用候補を探します（`app/desktop/scripts/fetch-node.sh:22-23,95-103`; `app/desktop/src-tauri/tauri.conf.json:33-40`; `app/desktop/src-tauri/src/main.rs:350-379`）。

## 値と判定

両スクリプトとも、プロセス開始時に環境から文字列を読みます。数値・形式の parse、trim、大文字小文字変換はありません。未設定と空文字は既定値になり、それ以外の文字列はそのまま使われます。たとえば `24.12.0`、`0`、`false`、`24.12.0 ` はいずれも非空の設定値として採用されます。妥当な Node バージョンかどうかの検査はなく、文字列が URL やファイル名に反映されます（`app/desktop/scripts/fetch-node.sh:21,63-72`; `app/desktop/scripts/fetch-node.ps1:20-21,37,45`）。

`--check` の比較は Bash では大文字小文字を区別する文字列比較、PowerShell の `-ne` では既定で大文字小文字を区別しない比較です（`app/desktop/scripts/fetch-node.sh:56-61`; `app/desktop/scripts/fetch-node.ps1:29-34`）。

| 実行経路 | unset | 空文字 | 設定時に使われる値 | 既定値以外での digest 判定 |
|---|---|---|---|---|
| Bash `fetch-node.sh` | `24.12.0` | `24.12.0`（`${VAR:-...}`） | 任意の非空文字列をそのまま使用。たとえば `24.13.0`、`0`、`false` | `digest_for` は target ごとの記録済み digest を返す。記録のある target は別バージョンの archive も同じ digest と比較して不一致なら取得物を拒否する。記録のない target は警告を出して続行する（`app/desktop/scripts/fetch-node.sh:21,30-38,74-93`）。 |
| Windows PowerShell `fetch-node.ps1` | `24.12.0` | `24.12.0`（空文字は条件偽） | 任意の非空文字列をそのまま使用。たとえば `24.13.0`、`0`、`false` | バージョンが `24.12.0` 以外なら警告を出し、digest を比較せず続行する。`24.12.0` の場合は固定 digest と照合し、不一致なら拒否する（`app/desktop/scripts/fetch-node.ps1:20-23,51-60`）。 |

既定版 `24.12.0` 以外へ変更する場合、Bash では target 用 digest の更新も必要です（`app/desktop/scripts/fetch-node.sh:25-38,82-93`）。PowerShell は非既定版を認証なしとして警告する実装です（`app/desktop/scripts/fetch-node.ps1:51-60`）。

## 有効になる条件

- `fetch-node.sh` または `fetch-node.ps1` を実行する必要があります。Strata の通常起動時にこの変数を読む箇所は見つかりません（全参照の検索結果では、実装読み取りは上記 2 スクリプトのみ）。
- Bash スクリプトは実行ホストを `uname` で判定し、macOS arm64、Linux x64/arm64、Windows互換 shell を自動選択します。`--target` で対象を指定できます。archive 分岐には `darwin-x64` もありますが、digest 一覧にはありません（`app/desktop/scripts/fetch-node.sh:30-47,51-74`）。未対応 host は `unsupported host: ...` で終了コード 2、archive 分岐にない target は `fetch-node: no archive known for ...` で終了コード 2 です。
- PowerShell スクリプトは target を `win-x64` に固定しています（`app/desktop/scripts/fetch-node.ps1:20-23,37`）。
- `--check`（PowerShell は `-Check`）では既存ファイルの Node `--version` と `v<変数値>` を照合します。ファイルがない場合、またはバージョンが一致しない場合は失敗します。通常の取得時は、指定バージョンの Node 配布 archive が取得可能である必要があります（`app/desktop/scripts/fetch-node.sh:56-61`; `app/desktop/scripts/fetch-node.ps1:29-35`）。
- Bash の記録済み digest がある target では、環境変数だけを既定値以外に変えても digest は連動更新されず、不一致で拒否されます。記録のない target は認証なし警告後に処理を続けます。PowerShell は既定版以外について同じく認証なし警告を出し、処理を続けます（`app/desktop/scripts/fetch-node.sh:30-38,74-93`; `app/desktop/scripts/fetch-node.ps1:22-23,51-60`）。
- バンドル後のアプリは `STRATA_NODE_VERSION` を再評価しません。同梱 Node が見つかればそれを使用します（`app/desktop/src-tauri/src/main.rs:364-379`）。

## 実行時の詳細

値は各スクリプトの起動時に一度シェル変数へ代入されます。スクリプト実行中に親プロセス側の環境値を変更しても、その代入値は変わりません。子プロセスへ環境変数を設定し直す処理はなく、Node archive の URL、展開先の名前などを組み立てるために値を使います（`app/desktop/scripts/fetch-node.sh:19-23,63-79,95-103`; `app/desktop/scripts/fetch-node.ps1:18-24,37-49,61-69`）。

Bash の通常取得では `curl` で archive を取得し、記録済み digest があれば SHA-256 不一致時に展開前に終了します。PowerShell は `-FromFile` の指定時にローカル zip を使い、それ以外は URL から取得します。いずれも展開後に `resources/node` へ Node 実行ファイルを配置します（`app/desktop/scripts/fetch-node.sh:74-103`; `app/desktop/scripts/fetch-node.ps1:37-69`）。

## ログと測定値

Bash は URL、digest の検証結果、認証なしの警告、インストール先を `fetch-node:` 付きで出力します。記録済み digest との不一致では `fetch-node: REFUSING — ...` を stderr に出して終了コード 1、digest 未記録では `fetch-node: WARNING — no recorded digest for ...; this download is NOT authenticated.` を stderr に出して続行します（`app/desktop/scripts/fetch-node.sh:78-93,103`）。`--check` は未導入またはバージョン不一致の場合に stderr へ理由を出して終了コード 1 です（同:56-61）。

PowerShell は URL と成功結果を標準出力へ、認証なしの警告を stderr へ出します。既定版の hash 不一致、`-Check` で未導入・版不一致、または zip に `node.exe` がない場合は `Fail` 経由で stderr に `fetch-node: ...` を出して終了コード 1 です（`app/desktop/scripts/fetch-node.ps1:27-35,45-59,64-69`）。

対象変数に関する Strata の性能測定値はありません。

## 根拠

- Bash での既定値、target 別 digest、archive 取得・検証・配置: `app/desktop/scripts/fetch-node.sh:21-38,40-103`
- PowerShell での既定値、Windows target、digest 分岐、取得・展開: `app/desktop/scripts/fetch-node.ps1:18-72`
- Node sidecar のバンドルと選択: `app/desktop/src-tauri/tauri.conf.json:33-40`; `app/desktop/src-tauri/src/main.rs:350-379`
- パッケージ手順と digest 更新の説明: `tools/packaging/README.md:41-54`
