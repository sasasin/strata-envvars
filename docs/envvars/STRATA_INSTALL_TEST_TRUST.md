# `STRATA_INSTALL_TEST_TRUST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

これは Strata Terminal 自体の通常実行時設定ではなく、配布用インストーラーの署名確認をローカル・テスト用 feed で行うためのスイッチです。Linux/macOS 用 `tools/packaging/install.sh` と Windows 用 `tools/packaging/install.ps1` がこの環境変数を読みます。値が有効な場合、インストーラーは feed の `test-trust.json` を一時領域へ取得し、そのファイルを `STRATA_UPDATE_TRUSTED_KEYS` として検証用 `strata update --check` に渡します（`tools/packaging/install.sh:163-169`, `tools/packaging/install.ps1:179-187`）。

説明コメントにはテスト鍵「だけ」を信頼するように読める箇所がありますが、実装は組み込み鍵を残したまま追加鍵ファイルを読み込みます。署名鍵の読込順と合成は `terminal/strata_control/signing.py:194-216` を参照してください。

## 値と判定

両スクリプトとも数値変換はせず、文字列比較で判定します。Shell 版は unset と空文字を `${...:-}` で同じ空文字にし、文字列 `1` との完全一致だけを有効にします（`tools/packaging/install.sh:164`）。PowerShell 版も環境変数文字列を `'1'` と比較します。PowerShell の `-eq` は既定で大文字小文字を区別しませんが、比較対象が数字のみのため結果に差はありません（`tools/packaging/install.ps1:179`）。

| 実行経路 | unset | 有効になる値 | 無効になる値の例 |
|---|---|---|---|
| Linux / macOS (`install.sh`) | 無効 | `1` | 空文字、`0`、`true`、`01`、` 1`、`1 `、`0anything` |
| Windows (`install.ps1`) | 無効 | `1` | 空文字、`0`、`true`、`01`、` 1`、`1 ` |

空白除去、大文字小文字以外の正規化、真偽値・整数としての変換はありません。無効な値はエラーにならず、この分岐を通りません。unset または無効値の場合でも、親プロセスから `STRATA_UPDATE_TRUSTED_KEYS` が渡されていれば、それを消去せず検証コマンドへ継承します（Shell 版はこの環境変数を設定する分岐に入らず、PowerShell 版も同様です）。

## 有効になる条件

- `tools/packaging/install.sh` を Linux または macOS で実行するか、`tools/packaging/install.ps1` を Windows PowerShell 5.1 以降で実行すること。OS ごとのインストール経路は `docs/INSTALL.md:64-74` に記載されています。
- インストーラーがアーカイブを展開し、署名確認ステップまで到達すること（`tools/packaging/install.sh:149-169`, `tools/packaging/install.ps1:153-187`）。
- 値が完全一致で `1` であること。
- `STRATA_FEED` で選んだ feed の直下に取得可能な `test-trust.json` があること。feed の既定値と `STRATA_FEED` による選択は `tools/packaging/install.sh:24-25`, `tools/packaging/install.ps1:29-30` にあります。

CLI の `--feed` 引数は検証対象 feed を選びますが、`STRATA_INSTALL_TEST_TRUST` の判定を変更しません。ビルド backend、GPU、モデル、サーバーモードには依存しません。

## 実行時の詳細

インストーラーは署名確認ステップでこの値を読みます。Shell 版はスクリプト実行中に一度条件評価し、PowerShell 版も当該ステップで一度条件評価します。読み取った値を static cache や設定ファイルへ保存する処理はなく、インストーラー開始後にプロセス環境を書き換えた場合の再評価経路もありません。

値が `1` の場合、両スクリプトは `$FEED/test-trust.json` または `$feed/test-trust.json` を一時ディレクトリに取得し、成功時にそのパスを `STRATA_UPDATE_TRUSTED_KEYS` として、直後の `strata update --check --no-engine --feed ...` 子プロセスへ渡します（`tools/packaging/install.sh:164-169`, `tools/packaging/install.ps1:179-187`）。CLI は `terminal/strata_control/signing.py:198-216` で `STRATA_UPDATE_TRUSTED_KEYS` のファイルを読み、組み込み `update_keys.json` の鍵に追加します。重複する key ID は後から読み込む追加ファイルの値で辞書に設定されます。CLI は `terminal/strata_cli/update_cmd.py:351-363` で検証用の鍵集合を作り、`--check` の検査を実行します。

したがって `STRATA_INSTALL_TEST_TRUST=1` は feed を選ばず、鍵データも直接解釈しません。テスト鍵ファイルを取得して別の環境変数へ渡すインストーラー側の分岐を有効にします。値が `1` でないときはこの取得・上書きがなく、既存の `STRATA_UPDATE_TRUSTED_KEYS` があればそれが引き続き検証に使われます。

## ログと測定値

有効な値で test key ファイルの取得に失敗すると、Shell 版は展開中のファイルを削除して `strata installer: the test feed has no test-trust.json` を stderr に出し終了します（`tools/packaging/install.sh:164-165`, `tools/packaging/install.sh:29-30`）。PowerShell 版も同じ文言を `Die` 経由で stderr に出し、展開物を削除して停止します（`tools/packaging/install.ps1:24`, `tools/packaging/install.ps1:179-182`）。

取得後の署名検査に失敗した場合、両インストーラーは `strata update --check` の出力を stderr に転記し、展開物を削除して「the release folder's signed feed could not be verified...」で終了します。成功すると Shell 版は `Signature ok.`、PowerShell 版は `  Signature ok.` を表示し、インストールを続けます（`tools/packaging/install.sh:168-174`, `tools/packaging/install.ps1:184-195`）。測定値はありません。

## 根拠

- `tools/packaging/install.sh:20-21`, `tools/packaging/install.sh:163-174` — POSIX 系インストーラーの用途説明、厳密な値判定、test key の取得、子プロセスへの引き渡し、失敗・成功時の処理。
- `tools/packaging/install.ps1:18-19`, `tools/packaging/install.ps1:179-195` — Windows インストーラーの用途説明と同等の処理。
- `terminal/strata_control/signing.py:31-32`, `terminal/strata_control/signing.py:194-216` — 子プロセス側の別環境変数名、組み込み鍵と追加鍵の読み込み・合成。
- `terminal/strata_cli/update_cmd.py:351-363` — `strata update --check` の署名鍵ロードと check の実行。
- `docs/INSTALL.md:64-74`, `tools/packaging/UPDATES.md:118-127`, `tools/packaging/UPDATES.md:184-187` — インストーラー起動方法と更新 feed の鍵検査についての照合資料。動作の根拠は上記ソースコード。

候補名の直接参照は上記2つのインストーラーのほか、`terminal/tests/terminal/test_launch_install.py:113-117`, `terminal/tests/terminal/test_launch_install.py:183-187` にあります。後者はテスト環境の設定で、本番動作の根拠には用いていません。Strata の実行時コードが `STRATA_INSTALL_TEST_TRUST` を直接読む箇所は見つからず、この名前を読むのはインストーラーです。
