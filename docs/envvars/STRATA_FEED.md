# `STRATA_FEED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

POSIX 用 `packaging/install.sh` と Windows 用 `packaging/install.ps1` が、Strata Terminal のリリースファイルを取得するフィードフォルダーを選びます。既定は GitHub Releases の `latest/download` フォルダーです。これはインストーラーの設定であり、Strata の通常起動時やサーバーの設定として `STRATA_FEED` を読むコードは見つかりませんでした。`strata update` が使う別変数は `STRATA_UPDATE_FEED` です（`strata_cli/update_cmd.py:23-26,97-107`）。

## 値と判定

| 実装 | 未設定・空文字 | 設定値 | 正規化・判定 |
|---|---|---|---|
| POSIX `install.sh` | 既定 URL にする | その文字列をフィードとして使う | 末尾の `/` を最大 1 文字取り除く。URL 形式や文字列全体は検証しない。正規化後に空ならエラー。 |
| Windows `install.ps1` | 既定 URL にする | PowerShell で truthy な値を使う（空文字は既定。`0` など空でない文字列は値として使う） | 末尾の `/` をすべて取り除く。URL 形式や文字列全体は検証しない。正規化後に空ならエラー。 |

POSIX 側の `${STRATA_FEED:-既定値}` は未設定と空文字の両方で既定値を選びます。値が `/` なら一文字除去後に空となり、インストールを始める前に stderr へ `this installer does not know where the Strata release folder is...` を出して終了コード 1 になります。`//` は一文字だけ除去され `/` が残るため、空値エラーにはならずその値で取得を試みます。Windows 側は未設定・空文字で既定値を選び、`/` や `///` は `TrimEnd('/')` 後に空となって同様の案内を出して停止します。空白だけの値などは空とは判定されず、URL として取得を試みます。

根拠: `packaging/install.sh:24-32`、`packaging/install.ps1:29-34`。

## 有効になる条件

- `install.sh` は Linux x86_64、Linux aarch64、macOS Apple silicon の対応プラットフォームを選んだ後にフィードへアクセスします。Windows は `install.ps1` を使います（`packaging/install.sh:53-61`、`packaging/install.ps1:34-37`）。
- 両スクリプトとも、まず `<feed>/install-manifest.txt` を取得し、対象プラットフォームの行に記載されたアーカイブを同じフィードから取得します。従って値は任意の「フォルダー URL」として連結され、マニフェストやアーカイブが存在しない場合はインストールできません（`packaging/install.sh:86-95`、`packaging/install.ps1:50-62`）。
- インストール後の署名確認でも、選択した値を `strata update --check --no-engine --feed <feed>` に渡します。この明示的な `--feed` が `STRATA_UPDATE_FEED` より優先されます。CLI の解決順は `--feed`、`STRATA_UPDATE_FEED`、記憶済み feed、既定 feed です（`packaging/install.sh:117-121`、`packaging/install.ps1:109-118`、`strata_cli/update_cmd.py:97-107`）。
- `STRATA_FEED` の値に応じた別の OS/backend/build macro 条件はありません。プラットフォーム選択はインストーラー自身の OS/CPU 判定に従います。

## 実行時の詳細

値はインストーラースクリプトの実行時に一度だけ読み、既定値の選択と末尾スラッシュ処理を行います。プロセス起動後の環境変更を再読する処理やキャッシュはありません。選択値は stdout に `Release folder: ...` と表示され、マニフェスト、アーカイブ、署名確認用の feed として使われます（`packaging/install.sh:24-27,81-86,93,117-118`、`packaging/install.ps1:29-30,41-50,59,109-112`）。

取得できないマニフェストでは POSIX 版は stderr に `could not read <feed>/install-manifest.txt...` を出して終了し、Windows 版も取得例外を捕捉して同趣旨のエラーを出します。アーカイブ取得失敗や署名確認失敗もそれぞれ停止経路があり、署名確認に失敗すると未確定の展開先を削除します（`packaging/install.sh:86-96,117-122`、`packaging/install.ps1:50-62,109-119`）。

`STRATA_FEED` はインストーラー内で直接読み取られます。`packaging/UPDATES.md:186-191` もインストーラー用の値として区別し、`strata update` の `--feed` / `STRATA_UPDATE_FEED` とは別の指定として説明しています。候補一覧にある名前と実装の間に食い違いは見つかりませんでした。

## 根拠

- `packaging/install.sh:17-25,29-32,81-96,112-123` — 既定値、入力判定、フィードの表示・取得、署名確認と失敗処理。
- `packaging/install.ps1:16-19,24-34,41-62,104-120` — Windows 側の既定値、入力判定、取得、署名確認と失敗処理。
- `strata_cli/update_cmd.py:23-26,37-38,97-107` — 別名の `STRATA_UPDATE_FEED` と `--feed` を含む CLI の優先順位。
- `packaging/UPDATES.md:186-191` — フィード URL とインストーラー用 `STRATA_FEED` の説明。
