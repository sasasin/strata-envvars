# `setup.py --output`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` からも起動） |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `jsonl`。既定値は `human` |

## 役割

`--output jsonl` は、セットアップが進行中に出す構造化イベントを標準出力へ1行1 JSON で流すための出力形式指定です。通常の進捗テキストやセットアップ中に起動されるプログラムの出力は標準エラーへ送り、機械処理用 stdout と混ざらないようにします。モデルのインストールなどセットアップ処理そのものを省略・変更する指定ではありません。通常利用では既定の `human` を使い、別プログラムから結果を読み取る場合は `jsonl` を指定します（parser: `terminal/setup.py:11309-11311`、出力切替: `terminal/setup.py:967-974`）。

## 使い方

```sh
# Linux/macOS の wrapper 経由で、推奨回答を選び、モデル導入後にサーバーを起動せず JSONL を受け取る
./setup.sh --output jsonl --yes --no-start

# Python を直接呼ぶ場合（Strata checkout のルートから）
python terminal/setup.py --output jsonl --yes --no-start
```

`START-HERE.bat` と `setup.sh` は引数を `setup.py` へ渡します（`setup.sh:6-17,81`、`START-HERE.bat:8-17,53-65`）。セットアップのダウンロードや設定書き込みは実行され得るため、上の例も実行すると環境を変更します。これは使用例であり、本調査中に実行していません。

## 値と既定値

- `human` / `jsonl` のみを受理し、省略時は `human` です。別名や短縮形はありません（`terminal/setup.py:11309-11311`）。
- 値がない場合や他の値を指定した場合は `argparse` の引数エラーになります。`parse_args()` より後で JSONL 出力を初期化するため、この parser エラー時には JSONL の `error` イベントへ変換されません（`terminal/setup.py:11309-11311,11385-11387`）。
- この引数の後続処理に固有の範囲数値・空文字検証はありません。重複指定時の詳細は標準 `argparse` の挙動に委ねられており、Strata 独自の処理は確認できません。

## 実行時の動作

既定の `human` では `_JSONL` が初期化されず、イベント出力関数は何も書きません。`jsonl` の場合は parser が引数を受理した直後、元の stdout を複製して JSONL 用に保持し、プロセスの fd 1 を stderr に付け替えます。イベントは `schema_version: 1` と `event` 名、個別フィールドを持つ JSON オブジェクトとして1行ずつ出力・flush されます（`terminal/setup.py:967-980,11385-11388`）。

イベント名は `step`、`ok`、`warning`、`progress`、`error`、`done` です。通常イベントには `step` 番号とタイトル、メッセージなどが含まれます。ダウンロードの `progress` は `label`、`done_bytes`、`total_bytes` を含み、同一ラベルでは完了前のイベントを最大1秒に1回に抑えつつ、最終更新は出します（`terminal/setup.py:986-1004,1040-1055`）。正常終了時の `done` には終了コードと、書き出された run config があればそのパスが含まれます（`terminal/setup.py:12344-12350`）。

ヘルプは `jsonl` がモデルをインストールするプログラム向けで、`--yes --no-start` と併用するよう案内していますが、ソース上でこの組み合わせを必須にする検査はありません（`terminal/setup.py:11306-11311`）。他のオプションとの優先順位を変える処理も確認できません。`--no-start` を付けない場合は、通常のセットアップ処理に続いて起動経路へ進むため、出力形式だけで起動を抑止することはできません（`terminal/setup.py:12342-12350` と `terminal/setup.py:12334-12341`）。

## 適用条件と副作用

JSONL モードはセットアップ全体の標準出力をリダイレクトするため、Python の `print` や子プロセスが標準出力へ出す人向け文字列も stderr 側に現れます。JSON イベントの書き込み先は、切替前に複製した stdout です（`terminal/setup.py:970-974,997-998`）。ファイルやネットワークを `--output` 自体が操作することはありませんが、セットアップ本体のダウンロード、設定作成、インストール等は通常どおり起こります。

## 出力とエラー

`fail()` 経由の失敗は人向けメッセージを stderr に出し、JSONL では `error` イベント（終了コード 1）を出した後、終了コード 1 で終了します（`terminal/setup.py:1049-1056`）。取得拒否と割り込みもそれぞれ `error` イベントを出して終了します。通常の戻り値が非ゼロなら `error` の後に `done` を出し、ゼロなら `done` のみです（`terminal/setup.py:12344-12358`）。

`argparse` の選択肢エラーは JSONL 初期化前のため JSON イベントを出さず、未捕捉の他例外についてもこのトップレベル処理から JSONL エラー出力される保証はありません（`terminal/setup.py:11309-11311,11385-11387,12344-12358`）。OS ごとの stderr 表示や端末の見え方は調査していません。

## 根拠

- `terminal/setup.py:11309-11311` — parser 定義、選択肢、既定値、利用目的。
- `terminal/setup.py:967-980` — stdout の複製・stderr への切替、JSON イベントの形式。
- `terminal/setup.py:986-1004,1040-1055` — progress、step、成功・警告・失敗イベント。
- `terminal/setup.py:11385-11388,12344-12358` — 初期化位置と正常終了・拒否・割り込み経路。
- `setup.sh:6-17,81`、`START-HERE.bat:8-17,53-65` — wrapper が引数を `setup.py` に渡す経路。
