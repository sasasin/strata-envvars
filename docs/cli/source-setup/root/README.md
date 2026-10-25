# `setup.py` / `setup.sh` / `START-HERE.bat`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（POSIX: `./setup.sh`、Windows: `START-HERE.bat`） |
| 主な実装 | `setup.py` |
| 委譲 wrapper | `SETUP.bat`、`update.sh`、`UPDATE.bat` |

## 役割

Strata のモデル環境を初回に準備し、以降は保存済み設定でモデルを起動するためのセットアップ入口です。通常の初回実行では PC と GPU を確認し、モデルなどを選び、Python 依存関係と推論 engine を用意し、モデルファイルを取得・検証して実行設定と起動スクリプトを保存します。既存モデルがある状態で引数なしに実行すると、通常はセットアップ工程を繰り返さず保存済みモデルを起動します（`setup.py:8412-8420, 8602-8619, 8677-8691`）。

`setup.py` は root parser で `--setup`、`--check`、`--update` などを受け付けます。POSIX/Windows wrapper は引数を `setup.py` に渡します。`SETUP.bat` は `--setup` を付け、`update.sh` / `UPDATE.bat` は git clone の場合 `git pull --ff-only` の後に `--update` を付けて実行します（`setup.py:8420-8553`; `setup.sh:6-12, 76`; `START-HERE.bat:8-10, 44-55`; `SETUP.bat:1-3`; `update.sh:7-9, 16-17, 62`; `UPDATE.bat:11-20, 79`）。

## 代表的な使い方

```sh
# Linux: 初回セットアップ。質問に答えてモデルを準備し、起動する
./setup.sh

# 設定画面を開き、モデルを追加するか設定を変更する
./setup.sh --setup

# この PC の GPU、ドライバー、メモリーなどを確認して終了する
./setup.sh --check

# Windows: installed model / Python packages / engine を更新し、モデルは起動しない
UPDATE.bat

# 質問を省略して推奨回答を使い、準備後に起動する
./setup.sh --yes
```

`setup.sh` は利用可能な同梱 Python または `.venv` を使って `setup.py` を起動し、必要な場合は Python と仮想環境も準備します。Windows の `START-HERE.bat` も同梱 Python / `.venv` を優先し、なければ Python 3.10 以上を探して仮想環境を作ります（`setup.sh:7-13, 14-76`; `START-HERE.bat:8-10, 11-18, 36-55`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 初回セットアップ | `./setup.sh` または `START-HERE.bat` | PC を調べ、対話式に設定を選びます。依存関係・engine・モデル関連ファイルを準備し、設定と起動スクリプトを保存した後、モデルを起動します。 |
| 既存モデルの起動 | `./setup.sh` または `START-HERE.bat` | 保存済み設定のモデルを起動します。インストール済みファイルの不足は `--setup` での修復を案内し、起動中の工程ではインストール・ダウンロード・コンパイルを行いません。 |
| 再セットアップ | `./setup.sh --setup`、`SETUP.bat` | 既存環境を確認してモデルを追加するか設定を変え、必要な取得・準備を行います。`--no-start` を付けるとセットアップ後にモデルを起動せず終了します。 |
| PC 確認 | `./setup.sh --check` | GPU、RAM、モデルサイズの適合見込みなどを表示して終了します。適合するモデルがないと判定した場合は終了コード 1 です。 |
| 更新 | `./update.sh`、`UPDATE.bat` | wrapper は git clone なら先に fast-forward の `git pull` を行い、その後 `setup.py --update` を実行します。インストール済みモデルを起動せず、モデルファイルは変更せずに runtime package、必要な engine、モデル設定と draft subset を更新します。 |
| `setup.py --update` 直接実行 | `./setup.sh --update` | `update.sh` / `UPDATE.bat` と同じ setup 側の更新処理を行いますが、wrapper が行う git pull は含みません。 |
| macOS / Intel SYCL 分岐 | `./setup.sh`（macOS）、`./setup.sh --backend sycl` | macOS の通常経路は Metal 用 setup へ、`--backend sycl` は Intel Arc 用 setup へ引数を渡します。通常の NVIDIA/AMD 経路とは別の実装です。 |

既存設定の起動時には更新可能な engine がある旨を表示することがありますが、その表示だけで更新は行われません（`setup.py:5208-5233, 6737-6742`）。

## 主な動作と副作用

- セットアップは PC の GPU、driver、RAM、CPU、空きディスクなどを調べ、選択内容と環境に応じて Python package を仮想環境へ導入します。engine は既製配布物を利用するか、条件や指定によりソースからビルドします（`setup.py:8697-8710, 9258-9275`; `setup.py:3295-3317, 5472-5475`）。
- モデル、vision encoder、必要な draft layer などをネットワークから取得する場合があります。ファイルの既存状態を確認・検証して、不足分だけ取得する経路があります（`setup.py:9285-9335, 9384-9398`）。選択されたモデルや backend により必要なファイルと準備工程は異なります。
- モデルを使える形式に準備し、`strata-<model>.json` の run config と `run-<model>.bat` / `.sh` を書きます。設定変更前の config がある場合、差分があれば `.bak` に退避します（`setup.py:9341-9375, 9402-9421, 9729-9730`; `setup.py:6312-6345`）。
- `--no-start` はセットアップ完了後に 0 で終了し、モデル起動へ進みません（`setup.py:9759-9766`）。通常のセットアップでは完了案内を表示し、最終的に server 起動関数へ進みます（`setup.py:9740-9766`）。
- `--yes` は推奨回答を採用して質問を省きますが、単独でリスクのある選択を許可するものではありません。通常なら停止して確認する選択を続けるには、該当する明示フラグも必要です（`setup.py:34-37, 5853-5854`）。
- `--update` は設定更新や runtime package の導入、engine の更新判定・取得、設定の upgrade、draft subset の更新を行います。実行中のモデルがある場合、その engine は更新せず、モデルを閉じて再実行するよう案内します（`setup.py:6682-6709`）。一方、`update.sh` / `UPDATE.bat` は git pull も行うため、未コミット変更などで fast-forward できない場合は失敗して止まります（`update.sh:16-53`; `UPDATE.bat:19-70`）。

## 注意点

- `--check` はセットアップを進めず PC の適合性を報告します。`--inspect SOURCE [VARIANT]` も別経路で GGUF の header を調べる用途であり、モデル導入とは異なります（`setup.py:8506-8508, 8559-8560, 8860-8909`）。
- CLI 全オプションの値、既定値、個別の相互作用は [`docs/cli/README.md`](../../README.md) の `source-setup` 節と各オプション文書を参照してください。特に [`--setup`](--setup.md)、[`--update`](--update.md)、[`--check`](--check.md)、[`--no-start`](--no-start.md)、[`--yes`](--yes.md) を参照してください。
- backend ごとの対応や制約は異なります。macOS と SYCL は別 setup に委譲され、AMD は Windows と Linux で engine の準備経路も異なります（`setup.py:8418-8419, 8561-8564, 8731-8734`; `setup.py:9263-9276`）。全 OS / backend の実行はこの調査では行っていません。

## 関連資料

- [Strata `docs/INSTALL.md`（調査対象 commit）](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/INSTALL.md) — セットアップ利用者向け説明。
- [Strata `docs/AMD_HIP.md`（調査対象 commit）](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/AMD_HIP.md) — AMD backend。
- [Strata `docs/OLDER_GPUS.md`（調査対象 commit）](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/OLDER_GPUS.md) — 旧世代 NVIDIA GPU と CUDA 12。
- [Strata `docs/MULTI_GPU.md`（調査対象 commit）](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/docs/MULTI_GPU.md) — 複数 GPU の設定。

## 根拠

- `setup.py:1-37, 8412-8420, 8421-8553` — CLI の役割説明、root parser と option 定義。
- `setup.py:8553-8564, 8602-8620, 8677-8695` — 引数処理、通常起動と setup / update 分岐。
- `setup.py:8697-8909, 9258-9335, 9341-9398, 9402-9425, 9729-9766` — 環境確認、取得・準備、config 作成と start / no-start。
- `setup.py:6312-6345, 6682-6709, 6737-6752` — config の退避・更新処理、start と不足ファイル時の案内。
- `setup.sh:6-13, 14-76`; `START-HERE.bat:8-18, 36-55`; `SETUP.bat:1-3`; `update.sh:7-17, 62`; `UPDATE.bat:11-20, 79` — POSIX / Windows wrapper の引数委譲と更新経路。
- `setup.py:825-830, 8553-8556, 8565-8570, 8860-8909, 9769-9777` — parser error、validation、check の結果、共通失敗・中断処理。

この文書はソース checkout の上記 commit を対象にしています。既存 CLI の `--help` は実行せず、parser 定義と wrapper の引数委譲を根拠にしました。異なる OS / backend の実動作および現在配布される Release artifact はこの調査では確認していません。
