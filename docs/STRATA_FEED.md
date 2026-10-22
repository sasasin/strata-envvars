# `STRATA_FEED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux/macOS 用 `packaging/install.sh` と Windows 用 `packaging/install.ps1` が、Strata Terminal をインストールするときに使うリリースフォルダーを指定します。既定値は Strata の GitHub Releases の `latest/download` です。これはインストーラー専用で、`strata` の通常実行時に読み取られる設定ではありません。

## 値と判定

| 実装 | 未設定または空文字 | 設定値の加工 | 空になった場合 |
|---|---|---|---|
| `install.sh` | 既定 URL を使う（`${STRATA_FEED:-...}` のため空文字も既定値扱い） | 末尾の `/` を最大1個削除する（`${FEED%/}`） | 通常は既定値または設定値になる。結果が空ならエラー終了する |
| `install.ps1` | 既定 URL を使う（PowerShell の条件式で空文字は false） | 末尾に連続する `/` をすべて削除する（`.TrimEnd('/')`） | エラー終了する |

値は URL やフォルダー文字列としてそのまま使われます。形式の検証や URL の正規化はありません。空白だけの値や、`0`、`false` のような非空文字列も設定値として扱われます。シェル版と PowerShell 版では複数の末尾 `/` の処理が異なります。どちらも変数が未設定または空文字なら既定値に戻るため、空文字で明示的に feed を無効化することはできません。

## 有効になる条件

各インストーラースクリプトを実行した場合にだけ参照されます。Linux/macOS ではシェル版、Windows では PowerShell 版を使います。環境変数が有効値でも、実際にインストールへ進むには対応プラットフォームの判定、必要ツール、feed 上の `install-manifest.txt` と対象 Terminal アーカイブの取得など、後続条件を満たす必要があります。

`strata update` はこの変数を読みません。更新先の指定は CLI の `--feed` または `STRATA_UPDATE_FEED` であり、インストーラーは算出した feed の値を `strata update --check --no-engine --feed "$FEED"`（PowerShell では `$feed`）に引数として渡します。

## 実行時の詳細

値はスクリプト開始時に一度決定され、標準出力の `Release folder: ...` に表示されます。その後、同じ feed から `install-manifest.txt`、manifest 記載の Terminal アーカイブを取得し、署名 feed の検証時にも同じ場所を `--feed` で渡します。したがって、誤った値や到達できない場所では manifest 取得または後続取得が失敗し、インストールは進みません。シェル版は manifest 取得失敗時に `could not read ...` を stderr に出して終了し、PowerShell 版も同趣旨のエラーを出します。

実装から確認できるのは、インストーラーが URL/パスを組み立てて取得処理と検証コマンドへ渡すところまでです。サーバー側や通信ツールの内部動作はこの変数の説明対象外です。起動後に親プロセスの環境を書き換えた場合の再読込はなく、値はスクリプト中の `$FEED` / `$feed` に保持されます。

## 根拠

- `packaging/install.sh:17-25` — 変数の用途、既定値、空文字時の既定値処理、末尾スラッシュ1個の削除。
- `packaging/install.sh:29-32` — 空 feed のエラー処理。
- `packaging/install.sh:71-85,104-114` — feed の表示、manifest とアーカイブの取得、署名確認への引き渡し。
- `packaging/install.ps1:16-19,29-34` — Windows 版での用途、既定値、末尾スラッシュ処理、空 feed のエラー。
- `packaging/install.ps1:41-60,92-102` — feed の表示、manifest とアーカイブの取得、署名確認への引き渡し。
- `strata_cli/update_cmd.py:25-31,88-94` — `strata update` 側の既定 feed と `STRATA_UPDATE_FEED` の読み取り。`STRATA_FEED` とは別の変数。
- `packaging/UPDATES.md:175-180` — リリースフォルダーと `STRATA_FEED` / `STRATA_UPDATE_FEED` の役割の説明。
