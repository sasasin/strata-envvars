# `--yes`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査対象リポジトリの `git status --short --branch` は `## main...origin/main` で、変更表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | Apple Silicon Mac 用 `metal/setup_mac.py`（`setup.py` から委譲。通常は `./setup.sh` 経由） |
| オプション | `--yes` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真、未指定では偽。 |

## 役割

Mac 用セットアップ中の対話質問に、質問ごとの既定・推奨回答を使います。確認を一律に省略したり、全ての安全確認を承認したりするフラグではありません。`setup.py` は `darwin` かつ `STRATA_CONTROL_INSTALL` が `1` でない場合、独自 parser を実行する前に引数を `metal/setup_mac.py` へそのまま渡します。したがってこの文書の scope は `source-setup/mac` です（`setup.py:9062-9069`、`setup.py:7702-7707`）。

## 使い方

```sh
./setup.sh --yes --no-start
```

`setup.sh` は引数を `setup.py` に渡し、macOS ではそこから Mac 用実装へ委譲します（`setup.sh:6-13, 76`、`setup.py:9068-9069`）。この例でもセットアップ処理は実行され、`--no-start` が最後のサーバー起動を止めます。設定やモデルのダウンロード・準備まで省略する指定ではありません（`metal/setup_mac.py:424-475, 542-570`）。

## 値と既定値

- `argparse` の `store_true` で、引数値はありません。省略時は `False`、指定時は `True` です（`metal/setup_mac.py:327-356`）。重複指定しても同じ真偽値です。`--yes=value` のように値を付ける書式は parser の定義にありません。
- モデルを `--model` で指定しない場合、`--yes` はメモリ量から推奨されたモデルを選びます。`--model` を指定した場合、この質問は行われません（`metal/setup_mac.py:389-402`）。
- `--vision` を指定しない場合、`--yes` は画像対応を有効にする既定回答 `y` を選びます。`--vision yes|no|gpu|cpu` を指定すると質問は行われません（`metal/setup_mac.py:353-355, 404-410`）。`cpu` は警告後、画像対応を有効にし CPU reader を選ぶ扱いです。
- 共通 helper `ask()` は `yes=True` なら質問を表示せず、渡された `default` を返します。通常の質問入力で EOF になればエラー終了しますが、`--yes` が効くこの2つの質問では入力自体を読みません（`setup.py:930-945`）。

## 実行時の動作

Mac parser の `a.yes` は、モデルと画像対応の質問に渡されます。モデルの推奨は `recommend_model()` の結果、画像対応の推奨は `yes` です。選択後は通常どおり Python 依存関係の導入、Metal engine の確認・build、必要なモデルや画像 encoder のダウンロード、モデル準備、設定・起動スクリプトの作成へ進みます。`--yes` はこれらの処理をスキップしません（`metal/setup_mac.py:389-410, 424-475, 542-570`）。

また、`setup_mac.py` は初めに `S.data_folder_for(a)` を呼ぶため、共有の `--data-dir` 処理にもフラグが影響します（`metal/setup_mac.py:364-368`、`setup.py:6472-6475`）。新しい `--data-dir` と同じドライブに既存モデルがある場合、`--yes` だけなら移動確認を出さず、既存ファイルをその場所に残して新規ダウンロードを指定先へ置きます（`setup.py:6410-6432`）。`--move-data` を併用すれば移動が指定され、`--set-default-data-dir` は既存ファイルを残す場合にも指定先を既定として保存します（`setup.py:340-342`、`setup.py:6427-6434, 6466-6469`）。

既存の設定済みモデルがあり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定していない場合、データフォルダー処理の後に既存モデルを起動する短絡経路へ進みます。この経路で `--yes` はモデル選択を行いません（`metal/setup_mac.py:364-371`）。

## 適用条件と副作用

- `setup.py` からの通常の macOS 実行で有効です。`STRATA_CONTROL_INSTALL=1` の Control モードは Mac parser へ委譲せず、別経路です（`setup.py:77-83, 9068-9069`）。
- `--yes` は推奨回答を選ぶだけです。明示したモデルが推奨より大きい場合などの警告・適合性判定、Mac の問題検査、download/build/prepare の失敗を無視する仕組みではありません（`metal/setup_mac.py:373-385, 392-403, 424-475`）。
- `--data-dir` の相互作用を除き、`metal/setup_mac.py` 内で `a.yes` が参照される箇所はモデルと画像対応の質問です（`metal/setup_mac.py:400-405`）。
- 選ばれた画像対応に応じて encoder の取得・build と生成設定が変わります（`metal/setup_mac.py:466-475, 547-550`）。データ移動を明示した場合は共有 helper が同一ドライブ上のモデルデータ等を移し、設定先を保存することがあります（`setup.py:6446-6469`）。

## 出力とエラー

- 自動回答された質問の入力プロンプトは表示されません。進行状況など他のセットアップ出力は通常どおりです（`setup.py:930-945`、`metal/setup_mac.py:364-405`）。
- Mac parser は `parse_known_args()` を使います。認識されない引数は `not used on a Mac: ...` と警告して処理を続けるため、PC 用 option を誤って付けても自動適用されるとは限りません（`metal/setup_mac.py:356-358`）。
- `--yes` 自体に値を付けるなど parser が解釈できない形式は `argparse` のエラーになります。モデル選択・画像対応以外の失敗条件はこのフラグでは回避されません。セットアップ共通の `fail()` は理由と案内を表示して終了コード `1` で停止します（`setup.py:904-909`）。

## 根拠

- Mac 用 parser、未知引数の扱い、フラグを使う質問: `metal/setup_mac.py:327-358, 389-410`。
- Mac 用処理の入口と既存モデル起動条件: `metal/setup_mac.py:364-371`。
- 質問 helper の自動回答・EOF 処理: `setup.py:930-945`。
- Apple Silicon への委譲: `setup.py:7702-7707, 9062-9069`。
- データ保存先と `--yes` / `--move-data` の相互作用: `setup.py:6378-6386, 6410-6469, 6472-6475`。
- セットアップ後半の画像 encoder・設定・起動: `metal/setup_mac.py:424-475, 542-570`。
