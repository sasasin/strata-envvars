# `--data-dir`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.sh` → `setup.py` → macOS Apple Silicon では `metal/setup_mac.py` |
| オプション | `--data-dir DIR` |
| 別名 | なし |
| 値 | データ用フォルダーのパス（文字列、必須） |

## 役割

モデル関連データを置く Strata data folder を指定します。Mac 用 setup では、このフォルダー直下を基点として `models/`（GGUF の既定保存先）、`packs/`、`mtp/`、Metal 用の再パック済みモデルが扱われます。GGUF だけ別の場所に置く場合は `--models-dir` または既存 GGUF を使う `--gguf-dir` が別にあります。parser は `metal/setup_mac.py:339-343`、各保存先の組み立ては同 `:365-367,451-454,476-505,518-539` です。

## 使い方

Strata ソース checkout のディレクトリで、例のパスを使ってモデルをセットアップし、完了後に自動起動しない例です。

```sh
./setup.sh --setup --data-dir ~/Strata-data --no-start
```

`setup.sh` は引数を `setup.py` に渡し、通常の macOS では `setup.py` が独自 parser の `metal/setup_mac.py` に全引数を渡します（`setup.sh:76`、`setup.py:9068-9069,7703-7707`）。Mac parser は `--data-dir` を文字列引数として受け付けます（`metal/setup_mac.py:328-356`）。

## 値と既定値

- `DIR` は `argparse` の string 値で、parser 上に `choices`、`type`、既定値、専用 alias はありません。繰り返し指定した場合の parser 値は最後の指定です（`metal/setup_mac.py:339`）。
- 指定時は共通処理が `expanduser()` と `resolve()` を行ってから検査するため、`~` と相対パスも絶対パスに変換されます。省略時は設定済み `data_dir`、未設定なら `home().parent / "Strata-data"` が使われます（`setup.py:6387-6391`）。非 Control の Mac setup では `home()` は Strata checkout のルートです（`setup.py:82-88`）。
- 空文字を値に渡した場合は共通処理で未指定と同じ扱いになります。空でないパスは、システム用ディレクトリでないこと、ファイルではなくディレクトリであること、既存先または作成に必要な親ディレクトリへ書き込めることを共通 validator が調べます。存在しないパスは、最も近い既存親で書き込み可能性を試します（`setup.py:6389-6393`; `strata_control/folders.py:63-100`）。

## 実行時の動作

Mac 用 `main()` はモデル選択などに進む前に `S.data_folder_for(a)` を呼び、data folder と、別の場所に残っている既存モデルデータの一覧を得ます（`metal/setup_mac.py:364-367`）。指定した新しいフォルダーへ、既存モデルが自動的に移動するわけではありません。

- 既存データが同じドライブにあり、移動を選ばない場合は、既存データを元の場所に残し、新規ダウンロードは指定先に置きます。Mac parser の `--yes` は既定 false なので、対話可能なら選択を尋ねます。`--yes` を付けると既存データを残す側になり、`--move-data` を付けると移動側になります（`metal/setup_mac.py:340,344`; `setup.py:6381-6386,6410-6434,6472-6475`）。
- `--set-default-data-dir` は、データを移動せず指定先を記憶する指定です。既存データが残る分岐でも指定先を設定に保存します（`metal/setup_mac.py:341`; `setup.py:6430-6432`）。それ以外も、data folder 処理の最後に選択先と Strata install path の一覧を設定へ保存します（`setup.py:6466-6469`）。既存設定は `setup.py:6251-6265` の共通設定読み書き処理で扱われます。
- 移動が選ばれた場合、同じドライブ上の `models/`、`packs/`、`mtp/` を既存の宛先を保ちながら移し、参照先ファイルが移動して元に残らない場合は設定ファイルのパスも更新します。移動できなかったデータは元の場所に残り、警告されます。別ドライブにあるデータは大容量コピーを避けるため元の場所で使われます（`setup.py:6301-6327,6441-6465`）。
- `--data-dir` はモデル保存先だけでなく、ディスク空き容量の表示・検査に使う場所にも影響します（`metal/setup_mac.py:380-382,420-422`）。ただし `--models-dir` を指定すると GGUF 保存先だけはそちらになり、data folder 側の pack や MTP などの用途は引き続き残ります（同 `:367,451-454,466-478,518-539`）。
- 既存の設定があり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定しない場合、data folder 処理の後に既存設定でサーバーを起動します。この早期起動条件には `--data-dir` 自体は含まれません（`metal/setup_mac.py:364-371`）。

## 適用条件と副作用

`setup.py` が `sys.platform == "darwin"` かつ `STRATA_CONTROL_INSTALL` が `1` でない場合に限り Mac parser へ委譲します。Control install mode はこの委譲条件の対象外です（`setup.py:82,9068-9069`）。

指定先が無効と判定された場合は `S.fail()` が停止し、既定の案内ではダウンロードも設定変更もしない旨を表示します（`setup.py:6391-6393,904-909`; 検証条件は `strata_control/folders.py:63-100`）。検査後のディレクトリ作成で `OSError` が起きた場合は警告して `home()` にフォールバックします（`setup.py:6398-6402`）。

有効な指定先はディレクトリ作成、設定ファイル更新、選択内容に応じたモデルデータ移動を伴うことがあります。`--data-dir` 単独で既存ファイルを移動する指定ではありませんが、`--move-data` との組み合わせでは移動が発生します（`setup.py:6398-6402,6410-6469`）。

## 出力とエラー

- 無効な指定先は理由と対処案を表示して終了コード 1 で停止します（`setup.py:6391-6393,904-909`）。
- 指定先の作成時に失敗すると警告を出し、`home()` を使って続行します（`setup.py:6398-6402`）。設定保存の失敗も警告されます（`setup.py:6258-6265`）。
- 同じドライブの既存データについて移動選択が必要なときは、保持または移動を尋ねます。`--yes` の場合は確認を行わず保持側になります（`setup.py:6418-6429`; Mac parser の既定は `metal/setup_mac.py:344`）。

## 根拠

- Mac 側 parser と引数処理: `metal/setup_mac.py:327-367`。
- setup.py から Mac 実装への委譲: `setup.py:7703-7707,9062-9069`、shell wrapper: `setup.sh:76`。
- data folder の既定値、検証、選択、移動、設定保存: `setup.py:6251-6265,6301-6327,6378-6475`。
- パス validator: `strata_control/folders.py:63-100`。
- Mac 側の `models/`、pack、Metal/MTP の利用: `metal/setup_mac.py:365-367,451-505,518-539`。

## 調査範囲

対象 revision は上記 SHA で、確認時の `git status --short --branch` は `## main...origin/main`（working tree clean）でした。Mac 実機での動作、実際のファイルシステム条件による失敗挙動、CLI `--help` の出力は実行していません。説明はこの revision の parser と共通実装の静的確認に基づきます。
