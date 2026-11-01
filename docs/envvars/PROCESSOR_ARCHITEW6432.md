# `PROCESSOR_ARCHITEW6432`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows 用の Terminal インストーラーが、実行環境のアーキテクチャ名を決める際に参照します。値が空でなければ `PROCESSOR_ARCHITECTURE` より優先されます。選ばれた名前が `AMD64` でなければインストールを停止します。これは Strata のモデル実行時設定ではなく、`packaging/install.ps1` 専用の判定です。

## 値と判定

| `PROCESSOR_ARCHITEW6432` | 選択される値 | 結果 |
|---|---|---|
| 未設定または空文字 | `PROCESSOR_ARCHITECTURE` の値 | 選択値が `AMD64` なら続行。それ以外は停止 |
| 空でない値 | この変数の値 | `AMD64` なら続行。それ以外は停止 |

値の trim、数値変換、別表記への変換はありません。PowerShell の既定の `-ne` 比較を使うため、大文字小文字は区別されません。たとえば `amd64` は `AMD64` と一致しますが、前後の空白は除去されず不一致になります。両方の変数が未設定または空なら選択値は空となり、`AMD64` 以外として停止します。

## 有効になる条件

- `packaging/install.ps1` が Windows 上で実行される経路で使われます。スクリプトはまず `STRATA_FEED` または既定 feed を検証し、その後 Windows 以外の OS を拒否してからアーキテクチャを調べます。
- `PROCESSOR_ARCHITEW6432` が空でなければ、`PROCESSOR_ARCHITECTURE` は判定に使いません。CLI 引数や他の Strata 設定による上書き経路はありません。
- 判定を通過するとプラットフォーム名は固定で `windows-x86_64` となり、その名前の manifest 項目を探します。この変数が選択するのはアーキテクチャ文字列であり、GPU やバックエンドの選択ではありません。

## 実行時の詳細

アーキテクチャの読み取りはインストーラースクリプトの実行中、feed と OS の検査後、GPU 情報の取得・表示、manifest のダウンロードより前に一度行われます。読み取った値は `$arch` に保持され、後続処理と表示に使われます。環境を後から変更して再評価する処理や、この値を子プロセスへ明示的に渡す処理はありません。

選択値が `AMD64` 以外の場合、`Die` が stderr に `strata installer: this computer (...) is a Windows on ARM PC...` のエラーを出し、例外でスクリプトを停止します。文言は非 AMD64 の値を一律に Windows on ARM と説明します。判定を通過した場合は `This computer: Windows <値> (windows-x86_64)` を表示し、release manifest 内で `windows-x86_64` の項目を検索します。その項目がなければ「this release has no Terminal for windows-x86_64.」として停止します。

## 根拠

- `packaging/install.ps1:1-14` — Windows 用 one-line installer と、その対象が Terminal であること。
- `packaging/install.ps1:29-37` — feed 検査、Windows 限定、対象変数からの読み取りと fallback、非 AMD64 の停止、プラットフォーム名の設定。
- `packaging/install.ps1:40-43` — 選択値とプラットフォーム名の表示。
- `packaging/install.ps1:50-55` — manifest のダウンロードと `windows-x86_64` 項目の選択。

候補一覧 `000_envvers.md` にはこの名前があります。Strata ソース内の実際の読み取りは `packaging/install.ps1:35` の一箇所です。`tests/terminal/test_install_scripts_env.py:50` にも名前がありますが、これはテスト用環境の構築であり、実装上の読み取り箇所ではありません。
