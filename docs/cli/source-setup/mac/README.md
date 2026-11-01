# `metal/setup_mac.py`（Apple Silicon / Metal setup）

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（通常は `./setup.sh` 経由） |
| 主な実装 | `metal/setup_mac.py`、共有処理は `setup.py` |
| 適用範囲 | macOS で `STRATA_CONTROL_INSTALL=1` を設定せず `setup.py` を起動した場合 |

## 役割

Apple Silicon Mac 向けに Metal engine とモデル環境を準備し、Strata の server を起動する setup です。Mac の chip・unified memory・macOS・空き容量を確認し、モデルを選び、Python package と Metal engine を用意した後、モデルファイルの取得・準備、起動設定と起動 script の作成へ進みます。必要な工程は既存ファイルや指定内容によって省略されます（`metal/setup_mac.py:1-16, 373-386, 424-475, 476-570`）。

`setup.py` は macOS かつ `STRATA_CONTROL_INSTALL=1` でない場合、受け取った全引数を `metal/setup_mac.py` に渡して終了します。Control install mode はこの委譲条件から外れ、`setup.py` 側の parser 経路を使います（`setup.py:82-83, 7703-7707, 9062-9070`）。

## 代表的な使い方

```sh
# リポジトリのルートで Mac の適合性を確認して終了
./setup.sh --check

# setup 画面を開き、モデル環境を準備する。完了後の server 起動は省略
./setup.sh --setup --no-start

# 既定の選択を使って初回準備し、完了後に server を起動
./setup.sh --yes

# Metal engine 等を更新する。モデルファイルがなければ取得せず案内して終了
./setup.sh --update
```

`setup.sh` は `setup.py` に引数を渡します。既存 Metal 設定がある状態で setup・check・update などの選択引数がなければ、通常は最初の設定を使って server を起動します（`setup.sh:6-13, 76`; `metal/setup_mac.py:369-372`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 既存設定の起動 | `./setup.sh` | Metal config が見つかり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれもなければ、保存済み設定で server を起動します。 |
| 初回準備・再セットアップ | `./setup.sh --setup` または `./setup.sh --model IQ3_XXS` | Mac を確認し、モデルを選択または指定して、必要な engine・モデル・補助ファイルを準備し、設定と起動 script を作ります。通常は最後に server を起動します。 |
| 準備後に起動しない | `./setup.sh --setup --no-start` | 上記の準備と設定作成を行い、server を起動せず終了します。 |
| Mac の確認 | `./setup.sh --check` | Mac の情報と適合上の問題を表示して終了します。問題がある場合は status `1`、なければ `0` です。 |
| 更新 | `./setup.sh --update` | Python package と engine の更新確認・準備をし、選んだモデルが既にあり必要な pack もある場合に続行します。モデルファイル自体は取得せず、不足があれば setup を案内して `0` で終了します。 |
| engine 再 build | `./setup.sh --build` | engine の build stamp を削除して、現在のソースから Metal engine を再 build します。 |

## 主な動作と副作用

- モデルを指定しないと unified memory に基づく推薦を提示し、対話で選択します。`--yes` を使うと推薦値を選ぶため、対話を省略できます。明示したモデルはメモリに対する注意が出ても選択されたままです（`metal/setup_mac.py:389-403`）。
- Python package を導入し、必要に応じて metal-cpp、llama.cpp/ggml を使った Metal engine、画像 encoder を取得または build します。build log や build metadata も作成します（`metal/setup_mac.py:82-97, 126-150, 165-189, 424-448`）。
- モデルや vision encoder を必要に応じて取得・検証し、モデル pack や MTP draft layer を準備します。複数 shard のモデルでは Metal 用 GGUF を別に生成する場合があります。ディスク空き容量不足などで任意の streaming copy を作れない場合は警告して元の GGUF を使う経路へ進みます（`metal/setup_mac.py:450-475, 476-540, 212-236`）。
- `strata-<model>.json` と `run-<model>.sh` を作成し、通常はその設定で server を起動します。vision を有効にした場合は encoder と projector 情報も config に記録されます（`metal/setup_mac.py:542-570`）。
- モデルの repack / pack 作業中に既存 engine が実行中なら、Mac の高負荷・停止を避けるため準備を失敗させて停止します。反対に engine 起動時、関連ファイルが不足している場合や repack が実行中の場合も起動を中止します（`metal/setup_mac.py:302-323, 476-495`）。

## 注意点

- これは Apple Silicon / Metal 用の独自 parser scope です。`setup.py` の通常 parser と同名の option があっても、受理される値や動作が同じとは限りません（索引 [`docs/cli/README.md`](../../README.md) の `source-setup` 節）。
- parser は `parse_known_args` を使います。認識されない引数は `not used on a Mac: ...` と警告されますが、未知引数だけを理由に parser が終了する動作ではありません（`metal/setup_mac.py:327-358`）。
- `--check` は Mac の問題を調べた後、モデル選択や通常の setup に進まず終了します。問題があれば終了 status `1` です（`metal/setup_mac.py:373-385`）。
- setup はネットワーク取得、仮想環境 package の導入、build、モデル関連ファイルの作成・更新を伴う場合があります。macOS 実機での実行、Release 配布物、OS の異なる挙動はこの調査では確認していません。

個別 option の値・既定値・相互作用は、[`docs/cli/README.md`](../../README.md) の `source-setup` 節にある [`--check`](--check.md)、[`--setup`](--setup.md)、[`--no-start`](--no-start.md)、[`--update`](--update.md) などの文書を参照してください。Apple Silicon 側の全 option と予定リンクも同索引に列挙されています。

## 関連資料

- [Strata `docs/INSTALL.md`（調査対象 commit）](https://github.com/Niko1221/Strata/blob/c62d5e3a15b40ea51c96aae9e8d36928965f53ab/docs/INSTALL.md) — setup 利用者向け説明。
- [Strata `metal/setup_mac.py`（調査対象 commit）](https://github.com/Niko1221/Strata/blob/c62d5e3a15b40ea51c96aae9e8d36928965f53ab/metal/setup_mac.py) — Apple Silicon 用 setup 実装。

## 根拠

- `setup.py:82-83, 7703-7707, 9062-9070` — Control install mode と macOS setup への委譲。
- `metal/setup_mac.py:1-16, 327-371` — コマンドの目的、parser、未知引数処理、既存設定の起動分岐。
- `metal/setup_mac.py:373-448` — Mac 適合確認、モデル選択、Python package・engine と update 処理。
- `metal/setup_mac.py:450-540` — モデル・vision・pack・MTP の取得と準備。
- `metal/setup_mac.py:542-570` — config と起動 script の作成、起動／no-start 分岐。
- `metal/setup_mac.py:302-323, 476-495` — 起動前検査と準備中 engine の競合時の停止。
- `setup.sh:6-13, 76` — POSIX wrapper の `setup.py` 呼び出し。

調査は上記 commit のソースと checkout 内の文書に限定しています。Mac 実機での動作確認、help の実行、Release artifact の照合は行っていません。
