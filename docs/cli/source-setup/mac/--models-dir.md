# `--models-dir`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査、commit 日 2026-10-31）。調査対象の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` が Apple Silicon の通常モードで委譲） |
| オプション | `--models-dir` |
| 別名 | なし |
| 値 | 1 個のディレクトリパス文字列。parser で型・存在・書き込み可否は検証しない |

## 役割

Mac 用ソースセットアップで、モデルの GGUF shard を保存するルートディレクトリを指定します。モデルごとのファイルはこのディレクトリ直下ではなく、family tag とモデル名から決まるサブディレクトリに置かれます。指定を省略すると、選択された data folder の `models/` が使われます（`metal/setup_mac.py:365-367, 451-460`）。

## 使い方

Apple Silicon の Strata ソース checkout で、モデルをセットアップし、最後に自動起動しない例です。

```sh
./setup.sh --setup --yes --model Q2_0 --models-dir "$HOME/Strata-models" --no-start
```

`setup.py` は macOS かつ `STRATA_CONTROL_INSTALL` が `1` でない場合、全引数を `metal/setup_mac.py` に渡します。したがってこの指定はその経路で有効です。アプリの Control mode はこの委譲条件の対象外です（`setup.py:82, 9062-9069`）。

## 値と既定値

- `argparse` は `--models-dir` に値を要求しますが、`type`、`choices`、独自 validator、明示的な既定値はありません。値を省略すると parser の既定値 `None` になります（`metal/setup_mac.py:327-356`）。
- 値が truthy なら `Path(a.models_dir)` を使い、指定しない場合または空文字列の場合は `data / "models"` に戻ります。ユーザー指定パスの `~` 展開や絶対パス化はこの箇所では行いません。相対パスはプロセスの作業ディレクトリ基準の `Path` として扱われます（`metal/setup_mac.py:365-367`）。
- `--data-dir` は data folder を選びますが、`--models-dir` はモデル用ルートを独立に上書きします。`S.data_folder_for(a)` は先に実行されるため、`--models-dir` の指定だけでも data folder 側の既存設定・移動確認などの処理は別途行われます（`metal/setup_mac.py:365-367`; `setup.py:6378-6402, 6472-6475`）。

## 実行時の動作

- 通常のモデル取得では `models_dir = models_root / tag` を使い、そのディレクトリを `mkdir(parents=True, exist_ok=True)` で作成します。shard の各ファイルが既に存在し、`.done` マークもある場合はダウンロードをスキップし、それ以外は選択中の model source から取得します（`metal/setup_mac.py:452-460`）。
- `--gguf-dir` が指定されていると、モデル shard の場所は `Path(a.gguf_dir)` になり、`--models-dir` は shard 置き場として使われません。空き容量の必要量計算でも `--gguf-dir` 時はモデルのダウンロード容量を 0 として扱います（`metal/setup_mac.py:420-422, 452-454`）。ただし画像 encoder を有効にした場合、そのファイルは `models_root / fam["mmproj"]` に置かれるため、`--gguf-dir` と併用しても `--models-dir` が画像 encoder の保存先になります（`metal/setup_mac.py:466-474`）。
- `--update` 経路では、既存モデル shard の確認先に `models_root / tag` を使いますが、モデルファイルはダウンロードしません。未導入なら警告を出して `--setup` でのセットアップを案内します（`metal/setup_mac.py:435-448`）。
- このオプションが変えるのはモデル用ルートです。repack した Metal GGUF、モデル pack、MTP データは `data` 側に作成・検索されます（`metal/setup_mac.py:478-484, 496-506, 518-540`）。既存のファイルを `--models-dir` へ移す処理はこのオプション自体にはありません。
- すでに Metal config があり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていないと、セットアップは既存 config の起動へ進みます。この判定に `--models-dir` は含まれないため、保存先変更だけではセットアップ経路に入りません（`metal/setup_mac.py:369-371`）。

## 適用条件と副作用

- 適用範囲は `setup.py` が macOS 用 parser に委譲した実行です。Mac 用 parser は `parse_known_args` を使い、未知の引数を `not used on a Mac: ...` と警告して続行します（`setup.py:9068-9069`; `metal/setup_mac.py:356-358`）。
- 既定の必要空き容量を下回っても、この経路は警告して続行しようとします。ダウンロード・ディレクトリ作成の書き込みは指定先に対して発生し、アクセス不能なパスを事前に拒否する独自 validation はありません（`metal/setup_mac.py:420-423, 452-460`）。ファイルシステム上のエラーは `mkdir` などの実操作で発生します。
- `--models-dir` は setup の起動時に決まる場所であり、実行中の server が動的に参照先を変更する処理はありません。生成 config の作成・pack・repack は data folder 等の別パスを用います（`metal/setup_mac.py:478-506, 542-560`）。

## 出力とエラー

- ダウンロード時は進捗行が標準出力に表示され、通信失敗は最大 5 回試行後に `Setup stopped...` を含むエラーを出して終了コード 1 になります。ファイルサイズが pin と異なる場合も `fail()` で停止します（`setup.py:904-909, 3008-3014, 3035-3068`）。
- 必要容量不足は警告で、直ちに失敗にはなりません（`metal/setup_mac.py:420-423`）。
- 値を伴わない `--models-dir` は argparse の引数エラーになります。存在しないディレクトリは通常経路で作成を試みますが、作成できない場合の個別メッセージや fallback は実装されていません（`metal/setup_mac.py:342-343, 452-454`）。

## 根拠

- parser、既定値、解析後の警告、data folder と models root の決定: `metal/setup_mac.py:327-367`
- 既存 config の起動判定、空き容量、update 経路: `metal/setup_mac.py:369-448`
- shard 配置・作成・取得、画像 encoder 配置: `metal/setup_mac.py:450-474`
- pack/repack/MTP と data folder 側への保存: `metal/setup_mac.py:476-540`
- `setup.py` から Mac parser への委譲条件: `setup.py:82, 9062-9069`; 委譲関数: `setup.py:7703-7707`
- data folder の変更・既存ファイル処理: `setup.py:6378-6469, 6472-6475`
- downloader の再試行・失敗処理: `setup.py:904-909, 3008-3100`
- 索引上の Mac scope と当該リンク: `docs/cli/README.md:1594-1621`
- 利用者向け Mac CLI 概要: `docs/MAC.md:104-113`

調査は上記 commit のソースを対象としました。実機 macOS 上での実行、ファイルシステムごとの権限・容量不足時の例外表示、および実際のダウンロード結果は確認していません。
