# `--check`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（Apple Silicon の macOS では `metal/setup_mac.py` に委譲） |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`、既定値 `False`） |

## 役割

Mac のセットアップ前提を調べ、モデル選択やエンジン build に進まず終了します。ここでいう「check」は Mac の基本条件の確認であり、モデルがメモリに収まるかの判定や、モデルファイル・エンジンの検査ではありません。

## 使い方

Strata checkout のルートで実行します。

```sh
./setup.sh --check
```

macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない場合、`setup.py` は引数を `metal/setup_mac.py` にそのまま渡します。別の条件では共通 `setup.py` parser の `--check` となり、挙動が異なります（[共通 parser の `--check`](../root/--check.md)）。

## 値と既定値

値を取りません。指定すると真、未指定なら偽です。繰り返し指定しても結果は変わりません。macOS parser は `parse_known_args` を使うため、認識できない引数は `not used on a Mac: ...` と警告され、処理は継続します。未知の引数が `--check` の結果に加わるわけではありません。

## 実行時の動作

1. 既存の Metal 用設定があっても通常起動へ進まず、Mac の確認へ進みます。
2. `mac_info()` でチップ名、搭載メモリ、macOS バージョン、Command Line Tools のパスを取得します。
3. `mac_problems()` が Apple Silicon であること、macOS 15.0 以降であること、Command Line Tools があることを確認し、問題を列挙します。
4. 空きディスク容量を表示し、問題があれば終了コード `1`、なければ `0` で終了します。モデル選択、Python package の導入、Metal engine build、ダウンロード、モデル準備、server 起動の各段階には進みません。

## 適用条件と副作用

- この文書の挙動は `sys.platform == "darwin"` かつ `STRATA_CONTROL_INSTALL=1` でないときに適用されます。Apple Silicon でない Mac も委譲先へ進みますが、check の結果は問題ありになります。
- 確認項目に問題があっても、`--check` の場合は最初の問題で通常セットアップを停止する経路へ進まず、問題一覧を出して終了コードを返します。
- 判定より前に `data_folder_for()` が呼ばれます。共通処理はデータフォルダを作成し、既定では同じドライブ上にある既存モデル等をそこへ整理し、設定を保存する場合があります。別の `--data-dir` を指定して既存ファイルがある場合は移動するか尋ねます（`--yes` または入力できない場合は保持、`--move-data` は移動）。`--set-default-data-dir` も保存動作に影響します。`free_gb()` も確認に使うパスが存在しない場合はディレクトリを作成します。そのため、`--check` はファイルシステムに一切書き込まない確認専用フラグではありません。これらを併用する場合は特に、共通処理の条件を確認してください。
- `free_gb()` の空き容量は表示されますが、Mac 用 `--check` の終了コード判定には使われません。
- `mac_info()` は macOS の情報取得に `sysctl`、`sw_vers`、`xcode-select` を呼び出します。値の取得に失敗したときの詳細な表示・終了条件は、取得関数内の例外処理と `mac_problems()` の判定に従います。

## 出力とエラー

標準出力に製品名、確認ステップ、チップ・メモリ・OS 情報、問題ごとの警告、空きディスク容量を表示します。問題があれば `1`、なければ `0` を返します。解析不能な引数値を `--check` 自身が検証する場面はありません。argparse が認識する不正な構文は parser 側のエラーになりますが、`--check` に値を取らせる定義はありません。

## 根拠

- parser、真偽値の既定値、未知引数の警告: `metal/setup_mac.py:327-358`
- 既存設定時の通常起動を抑止し、確認後に早期 return: `metal/setup_mac.py:369-385`
- 確認情報と問題条件（Apple Silicon、macOS 15.0、Command Line Tools）: `strata_control/mac_fit.py:81-124`
- macOS からの委譲条件と argv 転送: `setup.py:7703-7707`, `setup.py:9062-9069`
- データフォルダ作成・移動・設定保存の条件: `setup.py:6378-6469`, `setup.py:6472-6475`
- 空き容量確認がディレクトリを作成しうること: `setup.py:2319-2321`; macOS 側の呼び出し: `metal/setup_mac.py:365-381`
- 指定 revision と作業ツリー状態: checkout の `git rev-parse HEAD` は上記 SHA、`git status --short --branch` は `## main...origin/main`（変更行なし）を確認。
