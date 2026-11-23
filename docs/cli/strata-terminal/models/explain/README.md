# `strata models explain`（Strata Terminal）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models explain` |
| 入口 | `terminal/bin/strata`（POSIX ランチャー）→ `terminal/strata.py` → `strata_cli.cli.main` |
| 主な実装 | parser: `terminal/strata_cli/cli.py`、説明処理: `terminal/strata_cli/models_explain.py`、モデルフォルダー探索: `terminal/strata_cli/launch/catalog.py` |

## 役割

モデル名から family とサイズを解決し、`strata launch` と共通のカタログ探索を使ってデータフォルダーと `models/` 内の候補フォルダーを調べます。見つかったフォルダー、その中の `.gguf` ファイルとサイズを表示し、見つからない場合はダウンロード先となるフォルダーを示します。通常は `strata launch` が使うデータフォルダーを参照し、`--data-dir` で別の場所を調べられます。ソースの parser はこのコマンドを「変更なし」と説明していますが、起動前処理やデータフォルダー解決には条件付きの書き込みがあります（「主な動作」参照）。

## 基本的な使い方

```sh
# モデルサイズから family を自動解決して、launch が見る場所を確認する
strata models explain IQ3_S

# family とサイズを明示する（NAME に family/size を指定）
strata models explain qwen/IQ3_S

# 同じサイズを --family で指定する
strata models explain IQ3_S --family qwen

# 別のデータフォルダーを調べ、結果を JSON で受け取る
strata models explain IQ3_S --data-dir ./model-data --output json
```

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 人が読む形式（既定） | `strata models explain IQ3_S` | 探索したパス、存在状況、選ばれるフォルダーと確認できた `.gguf` を文章で標準出力へ表示する。 |
| JSON | `strata models explain IQ3_S --output json` | 同じ探索結果を `schema_version` と `ok` を含む JSON オブジェクトで標準出力へ表示する。 |

どちらもモデルのダウンロードや移動を実行するモードではありません。`--family` と `--data-dir` は探索対象の解決・場所を指定します。

## 主な動作

1. `NAME` が `family/size` 形式で `--family` がない場合は、スラッシュより前を family、後ろをサイズとして分けます。サイズ名は大文字・小文字を区別せず照合されます。family を省略して候補が複数ある場合は `qwen` を優先し、それが候補でなければ先頭の候補を使います。
2. `--data-dir` が空でない場合は `~` を展開した指定パスを調査先にします。省略時は、モデルのインストール済み run config が指すデータフォルダーを優先し、それが得られなければ Terminal と Desktop が共有するデータフォルダー選択規則を使います。
3. 通常の family では `models/<setup 表記>`, `models/<小文字 tag>`, 大文字・小文字だけが異なる既存ディレクトリの順に確認し、どれもなければ setup 表記のパスをダウンロード先として返します。Hy4-Flash と Inkling-2-Mini は `models/<family>` を確認します。
4. 選ばれたフォルダー直下の `*.gguf` ファイルを名前順に列挙し、ファイル名・サイズ・`mmproj` で始まるファイルかどうかを結果に含めます。探索先が未発見なら `models/` 直下のディレクトリ名も最大10件まで表示します。

## 主な動作と副作用

- 説明処理はファイルをダウンロード・移動せず、run config も書き換えません。読み取るのはモデル表、run config、ディレクトリ名、および発見した `.gguf` のサイズです。ディレクトリの列挙で `OSError` が起きた場合、その箇所では空の結果として扱われます。
- ただし `strata.py` は CLI parser に入る前に RAM budget の一回限りの移行を走らせます。対象 run config に旧形式の `--resident-budget-gib` があり `ui_budget_work_gib` がない場合、移行後の config と `.bak` を作り、調査済み install に `ram-budget-0217.done` を書きます。対象条件に当てはまらない config は書き換えないと実装コメントにあります。
- `Catalog` の初期化では install root に `mkdir(parents=True, exist_ok=True)` を実行します。また、モデルに対応する installed config がなく、通常のデータフォルダーを解決する経路では、Terminal と Desktop の設定が異なる場合に更新時刻の新しい側へ同期するため、設定ファイルを書き換えることがあります。
- Windows では CLI 起動前に、Strata 管理の古い `strata.ps1` が PATH 上の `strata.cmd` と同じフォルダーにある場合、`strata-direct.ps1` へ名前を変更しログを追記する処理も呼ばれます。
- `.gguf` 以外のファイルは説明結果のファイル一覧には含まれません。特に Hy4-Flash / Inkling-2-Mini の探索先は `.strata` を使うモデルフォルダーですが、このコマンドの一覧処理は `.gguf` だけを列挙するため、そのファイル構成を検証する用途には使えません。

## オプションの文書

各オプションの値と詳細は [CLI 索引の `strata models explain` 節](../../../README.md#strata-models-explain-modelsexplain) を参照してください。

## 根拠

- `terminal/strata_cli/cli.py:178-182` — `explain` parser、`NAME`、`--family`、`--data-dir`、`--output` の定義と既定値。
- `terminal/strata_cli/cli.py:581-589` — 説明処理の呼び出し、`ValueError` の終了コード 2、human / JSON 出力。
- `terminal/strata_cli/models_explain.py:16-36` — 名前形式の分解、モデル解決、データフォルダーの選択。
- `terminal/strata_cli/models_explain.py:37-61` — 候補探索結果、`.gguf` 列挙、JSON payload の組み立て。
- `terminal/strata_cli/models_explain.py:64-84` — human 出力と未発見時の表示。
- `terminal/strata_cli/launch/catalog.py:550-572` — サイズ・family の照合と family 省略時の選択規則。
- `terminal/strata_cli/launch/catalog.py:592-621` — 通常モデルと Hy4 / Inkling の探索規則および fallback。
- `terminal/strata_cli/launch/catalog.py:347-375` — カタログ初期化時の install root 作成とデータフォルダー関数の設定。
- `terminal/strata_cli/launch/catalog.py:730-736, 762-775` — installed config の参照と、該当 config がない場合の共有データフォルダー選択。
- `terminal/strata_control/discovery.py:228-260, 278-290` — Terminal / Desktop 設定の同期書き込みと、データフォルダー決定。
- `terminal/strata.py:35-62`、`terminal/strata_cli/ram_budget_move.py:23-39, 55-72` — CLI 前の RAM budget 移行、マーカー作成、条件付き config 更新。
- `terminal/setup.py:4018-4038` — 移行対象 config のバックアップ作成と一時ファイル経由の更新。
- `terminal/strata.py:49-52`、`terminal/strata_cli/launcher_heal.py:55-78` — Windows 起動前の旧 PowerShell ランチャー修復。
- `terminal/strata_cli/cli.py:558-573, 2248-2275` — 人向けエラーの stderr 出力、JSON エラー包絡、一般的な `OSError` の終了コード 6。
