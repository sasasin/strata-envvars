# `STRATA_NODE_VERSION`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソース。Node.js 本体の環境変数や動作は対象外。

## 役割

デスクトップアプリに同梱する Node.js のバージョンを、取得スクリプト `apps/desktop/scripts/fetch-node.sh` と Windows 用 `fetch-node.ps1` で選びます。どちらも未設定または空文字なら `24.12.0` を使います。値はダウンロード URL、アーカイブ名、展開先アーカイブ内のパスに使われます。スクリプトは `apps/desktop/src-tauri/resources/node` に実行ファイルを配置し、Tauri の bundle 設定はそのディレクトリを `node` リソースとして同梱します。実行時の Rust コードはそのリソース内の `node` / `node.exe` を探して App Host を起動します。根拠: `apps/desktop/scripts/fetch-node.sh:21,63-73,95-103`, `apps/desktop/scripts/fetch-node.ps1:20-25,37-45,61-69`, `apps/desktop/src-tauri/tauri.conf.json:32-39`, `apps/desktop/src-tauri/src/main.rs:297-326`。

これはデスクトップ用 Node 取得・検査スクリプトの設定です。エンジン実行時や App Host がこの環境変数を読む箇所はありません。候補名の他の参照は `tests/desktop/test_fetch_node.py` のスクリプト確認用テストと `packaging/README.md` の説明で、実装上の追加読み取りではありません。

## 値と判定

| 経路 | 未設定・空文字 | 非空文字列 | 判定方法 |
|---|---|---|---|
| Bash `fetch-node.sh` | `24.12.0` | その文字列をそのままバージョンとして使う | Bash の `${STRATA_NODE_VERSION:-24.12.0}`。値の形式や数値性は検査しない |
| PowerShell `fetch-node.ps1` | `24.12.0` | その文字列をそのままバージョンとして使う | `if ($env:STRATA_NODE_VERSION)` の真偽判定。空文字は false、空白だけの文字列や文字列 `0` は true。形式検査なし |

両スクリプトは `--check` / `-Check` の場合、インストール済み実行ファイルの `--version` 出力を `v${STRATA_NODE_VERSION}` と完全一致で比較します。不一致なら `fetch-node: expected v...` をエラー出力して失敗します。値は trim されず、たとえば `24.12.0 ` は一致しません。Bash は `--check` のとき `node --version` の出力をそのまま比較し、PowerShell は出力に `.Trim()` を適用してから比較します。根拠: `apps/desktop/scripts/fetch-node.sh:21,56-61`; `apps/desktop/scripts/fetch-node.ps1:20,29-34`。

## 有効になる条件

- Bash スクリプトまたは PowerShell スクリプトを実行したときだけ読み取られます。起動後の環境変更を再評価する常駐処理ではありません。
- Bash の自動 target 判定は macOS arm64、Linux x64 / arm64、Windows x64（MSYS/Cygwin 系を含む）です。`--target` では `darwin-x64` もアーカイブ名として扱えますが、自動判定対象ではありません。PowerShell 版は `win-x64` 固定です。根拠: `apps/desktop/scripts/fetch-node.sh:40-49,63-71`; `apps/desktop/scripts/fetch-node.ps1:21,37`。
- App Host の `engines.node` は `>=24.12.0` です。スクリプトは環境変数の値がこの条件を満たすか事前検査しません。古い/不正な値は URL・アーカイブ取得や後続処理で失敗する可能性があり、要件違反のバージョンでもスクリプト自体が拒否する実装ではありません。根拠: `apps/host/package.json:47-49`; `apps/desktop/scripts/fetch-node.sh:18,63-80`; `apps/desktop/scripts/fetch-node.ps1:11,37-49`。
- バージョンを `24.12.0` 以外にすると、ハッシュ認証の挙動は OS 版で異なります。PowerShell は固定値との比較をせず、未登録バージョンとして警告を出してインストールを続けます。Bash は選択 target の `24.12.0` 用 digest が存在する場合、その digest と取得物を比較するため、別バージョンは通常ハッシュ不一致で拒否されます。digest が未登録の `darwin-x64` では警告を出し、未認証のまま続けます。根拠: `apps/desktop/scripts/fetch-node.sh:25-38,74-93`; `apps/desktop/scripts/fetch-node.ps1:22-23,51-60`。

## 実行時の詳細

Bash 版は値から `https://nodejs.org/dist/v<VERSION>/<archive>` を組み立てて取得します。Windows zip では `node.exe` を、他の対応アーカイブでは `bin/node` をリソースディレクトリへ展開・コピーします。既定の `24.12.0` について Bash は target ごとに記録済み SHA-256 があれば一致を必須にし、不一致で `fetch-node: REFUSING ...` を出して終了します。digest 未登録時は `fetch-node: WARNING — no recorded digest ... this download is NOT authenticated.` と計算値を stderr に出して続行します。

PowerShell 版は `-FromFile` があれば指定 zip を使い、なければ同じバージョンを含む nodejs.org URL から取得します。`24.12.0` では zip の SHA-256 が固定値と異なると拒否し、それ以外のバージョンでは未認証の警告と計算値を stderr に出して続行します。両版とも一時ディレクトリを処理後に削除します。根拠: `apps/desktop/scripts/fetch-node.sh:72-103`; `apps/desktop/scripts/fetch-node.ps1:37-71`。

`packaging/README.md` はバージョン更新時に `STRATA_NODE_VERSION` を変更し、新しい digest を追加する手順を案内しています。現行 Bash 実装では既知 target の digest がバージョン別に引かれていないため、別バージョンに変えただけでは新バージョン用 digest を使わず、既存値との比較になります。更新時には実装の digest 表も合わせて更新する必要があります。根拠: `packaging/README.md:47-51`; `apps/desktop/scripts/fetch-node.sh:25-38,74-87`。

## 根拠

- `apps/desktop/scripts/fetch-node.sh:18-21,25-38,40-49,56-103` — Bash 版の既定値、target、取得・検査・配置。
- `apps/desktop/scripts/fetch-node.ps1:11-25,29-71` — Windows 版の既定値、ハッシュ判定、取得・配置。
- `apps/host/package.json:47-49` — App Host の Node バージョン要件。
- `apps/desktop/src-tauri/tauri.conf.json:32-39`, `apps/desktop/src-tauri/src/main.rs:297-326` — バンドル対象と実行時の Node パス解決。
- `packaging/README.md:34-51` — パッケージング上の目的と更新手順。
