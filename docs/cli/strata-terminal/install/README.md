# `strata install`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata install` |
| 主な実装 | `strata_cli/cli.py`、委譲先 `setup.py` |

## 役割

`strata install` は、モデル・推論エンジン・Python パッケージの取得や既存インストールの更新を、Terminal CLI から明示的に実行する入口です。通常の起動・serve コマンド自体はこのインストール処理を行いません（`strata_cli/cli.py:190-196`）。このコマンドは CLI 内で `setup.py` に委譲し、setup/update の実作業は委譲先が担います（`strata_cli/cli.py:2064-2082`）。

## 代表的な使い方

```sh
# 新規セットアップ、またはモデル追加の引数を setup.py に渡す
strata install --family qwen --model Q2_0 --yes

# 既存インストールを更新する（モデルを起動しない）
strata install --update
```

`strata install` の後続引数は `setup.py` に渡されます。サブコマンド固有の `--update` を付けない場合、CLI は委譲先を `--setup` モードで起動します（`strata_cli/cli.py:193-196,2074-2082`）。更新では `setup.py --update` が呼ばれ、既存モデルの設定・関連ファイルと必要な Python package / engine を更新する経路です（`setup.py:6682-6709,8617-8619`）。後続オプションの詳細と値の規則は `setup.py` 側の parser に依存します。

## 実行モードと主な動作

| モード | CLI の動作 |
| --- | --- |
| setup（既定） | `setup.py --setup` と後続引数を実行します。委譲先はモデルの選択・追加や設定変更を行い、通常の新規/明示セットアップ経路ではモデルファイル等の準備を行います。 |
| update | `strata install --update` を `setup.py --update` に変換して実行します。委譲先の更新処理はモデルを起動せず、モデルファイル自体を変更せずに、インストール済みモデル設定、必要な runtime packages、必要に応じた engine を更新します。 |

CLI は `STRATA_INSTALL_DIR` が設定されていればそのディレクトリの `setup.py` を選び、未設定なら CLI の `ROOT` にある `setup.py` を選びます。該当ファイルが見つからない場合は処理を開始せず、完全な Strata フォルダーで `SETUP.bat` / `setup.sh` または `UPDATE.bat` / `update.sh` を使う方法、あるいは `STRATA_INSTALL_DIR` の設定を案内して終了コード 5 を返します（`strata_cli/cli.py:2068-2073`）。

インストール済み Terminal bundle として実行され、CLI の `ROOT` に `python/` と `VERSION` がある場合、子プロセスへ `STRATA_CONTROL_INSTALL=1` を設定し、未設定なら `STRATA_INSTALL_DIR` を `install_root()` に設定します。この Control install 経路では、setup 側の説明上、モデルファイルの取得・準備と run config 作成を行い、Python package や engine の取得・コンパイルは行いません（`strata_cli/cli.py:2075-2080`、`setup.py:75-86`）。これは起動元 bundle の構成に依存します。

## 注意点

- `strata install` は読み取り専用の確認コマンドではありません。委譲先の選択・引数・環境に応じ、モデルや package のダウンロード、engine の準備、インストール設定の書き込みが起こり得ます（`strata_cli/cli.py:2064-2082`、`setup.py:6682-6709`）。
- `--update` は Terminal 自身を更新する操作として実装されていません。Terminal の CLI は `setup.py --update` に引数を渡します。署名済み update feed から engine と Control を更新するには `strata update` を使うよう、installer 不在時のエラー案内にも記載されています（`strata_cli/cli.py:2070-2073`）。
- 更新時にモデルが稼働中なら、engine 更新関数はその engine を保持し、モデルを閉じて再実行するよう案内します。更新が完了したという表示だけから、稼働中プロセスが切り替わったとは判断できません（`setup.py:6682-6687`）。
- Release 配布物や各 OS 上での実際のセットアップ実行は、このソース調査では検証していません。Terminal bundle と完全な Strata folder では installer の選択・処理範囲が異なるため、上記は記載 commit のソースで確認できた条件に限ります。

## 関連文書

- [`--update`](--update.md) — `strata install` の更新モード。
- [`--help`（alias: `-h`）](--help.md) — install parser のヘルプ。
- [CLI 文書索引](../../README.md) — コマンド階層とオプション文書。
- Strata `docs/TERMINAL_LAUNCH.md` — Terminal の導入方法と `strata launch` の説明（調査対象 repo 内の資料）。

## 根拠

- Strata `strata_cli/cli.py:190-196` — `install` parser、`--update` と `setup.py` 引数の定義。
- Strata `strata_cli/cli.py:2064-2082` — installer の解決、未発見時のエラー、bundle 用環境設定、`setup.py` の起動。
- Strata `strata_cli/cli.py:2120-2124` — install コマンドから `_install` への dispatch。
- Strata `setup.py:75-86` — Control install 時の書き込み先と処理範囲。
- Strata `setup.py:6682-6709` — update 処理、更新対象、モデルファイルを変更しない旨、モデルを起動しない旨。
- Strata `setup.py:8617-8619` — `--update` が更新処理へ分岐する箇所。
