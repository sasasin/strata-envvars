# `strata launch --model-path`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--model-path` |
| 別名 | なし |
| 値 | `PATH`。既存の `.gguf` / `.strata` ファイル、またはモデルファイルを含むフォルダー |

## 役割

手元にあるモデルファイルを使って起動するための指定です。パスから既知モデルを判定し、通常はそのモデルの setup を既存ファイルに対して実行します。モデルの種類が曖昧な場合は `--model NAME`（必要なら `--family NAME`）で指定できます。起動前にパスとファイルを調べ、使えない入力はエンジンの取得や setup より前にエラーにします（`terminal/strata_cli/launch/cmd.py:86,215-237`、`terminal/strata_cli/launch/runner.py:1956-2006,3296-3317`）。

## 使い方

```sh
# フォルダー内の既存モデルを使って起動し、対話画面を出さずに戻る
strata launch --model-path /data/models/IQ3_XXS --no-tui

# 1つの GGUF ファイルを指定し、変更内容だけを確認する
strata launch --model-path /data/models/model.gguf --plan

# フォルダー内に複数モデルがある場合、使うモデルを明示する
strata launch --model iq3_xxs --family qwen --model-path /data/models --plan
```

`--plan` は入力ファイルを検査して計画を表示しますが、何も変更しないと実装に記載されています（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 値と既定値

`PATH` は必須の文字列引数です。parser では `metavar="PATH"` のみを指定し、型変換や既定値の上書きはしていません（省略時は `None`）。このオプション専用のパーサー段階の形式検査はなく、値がない呼び出しは `argparse` の引数エラーになります（`terminal/strata_cli/launch/cmd.py:73-87`）。

値は設定時に `~` を展開します。相対パスも parser では拒否されず、実ファイル検査では絶対パスへ変換されます。ディレクトリ、`.gguf`、`.strata` ファイル、およびモデルが入った上位フォルダーを探索対象にできます。複数のモデル群が見つかって一意に選べない場合、`--model` で対象を指定するか、対象ファイルまたはそのモデルのフォルダーを選びます（`terminal/strata_cli/launch/cmd.py:222-225`、`terminal/strata_control/models.py:813-827,830-851,854-905,930-951`）。

空文字列は parser では受理されますが、後続コードは真偽値で有無を判定するため、未指定と同様に扱われます。複数回指定した場合の拒否・統合処理は実装にありません。`argparse` の通常の `store` 動作に従い最後の値が残ります（`terminal/strata_cli/launch/cmd.py:86,222-237`）。

## 実行時の動作

- `--model-path` を指定し、同時に `--model` を指定しない場合、保存済み preset から引き継いだモデル名と family を消し、モデルファイルの調査結果から選びます。`--model` を指定した場合はカタログでモデルを解決し、指定パスを保持します（`terminal/strata_cli/launch/cmd.py:215-239`）。
- `--plan` と通常起動のどちらも、`check_own_files()` がパスを調べます。モデルを指定していないときは、モデルが判定できない・複数候補がある・ファイル群に問題がある場合に失敗します。明示的に `--model` を指定したときは候補の不一致を通知しつつ、setup に指定モデルのファイルを探させる経路があります（`terminal/strata_cli/launch/runner.py:1956-2006`）。
- setup 呼び出しでは通常 `--gguf-dir` に変換されます。指定がディレクトリならそのディレクトリ、ファイルなら親ディレクトリを渡します。例外として `inkling-2-mini` のファイル指定はそのファイル自体を渡します（`terminal/strata_cli/launch/runner.py:1406-1412`）。
- `--model-path` または `--data-dir` がある場合、既存設定のモデルファイルが指定フォルダー外にあると、その設定の再利用を避けて指定場所に対する setup を行います（`terminal/strata_cli/launch/runner.py:1486-1512`）。
- 指定モデルの準備が必要なら setup プロセスを起動し、成功後に設定を書いて、通常起動ではチューニング・サーバー起動へ進みます。既存ファイルが利用される場合でも、モデル設定や別途必要な準備ファイルの作成があり得ます（`terminal/strata_cli/launch/runner.py:1679-1721,1798-1805,3296-3343`）。

## 適用条件と副作用

パスが存在しない場合、フォルダー内やその配下に `.gguf` / `.strata` がない場合、非対応の候補、欠落 shard、複数モデル群などは検査結果に応じて拒否または追加指定を求めます。DeepSeek の退役済みファイルは専用の理由を表示して拒否します。通常の誤ったパスは、エンジンや setup に触れる前に拒否されます（`terminal/strata_control/models.py:830-851,854-905,920-951`、`terminal/strata_cli/launch/runner.py:1963-2003,3300-3317`）。

この指定だけで元のモデルファイルを移動・コピーする処理は確認できません。読み取り専用とは限らず、通常の起動経路では設定ファイルの保存、プロファイル作成、チューニングやサーバー起動が続きます。ファイルの隣に Strata 用データを置けない、またはその場所が Hugging Face cache 内の場合は、モデルファイルはその場で使い、Strata のデータを既定の data folder に置く旨を通知します（`terminal/strata_cli/launch/runner.py:1514-1562,1710-1730,3322-3343`）。Intel backend など内蔵 installer で扱えない環境では、事前準備済みファイルから設定を組み立てる別経路があります（`terminal/strata_cli/launch/runner.py:1698-1707,1894-1953`）。

## 出力とエラー

- パス不在・無効なファイルの検査結果は人が読めるメッセージと次の手順を返し、`LaunchError` の終了コードを用いて失敗します。通常はパス不在がコード `2`、解析できない／利用できないモデル候補がコード `5` です（`terminal/strata_cli/launch/runner.py:1969-1981,1997-2003`）。
- setup が失敗した場合は setup の `[X]` 行を抽出してエラーにし、詳細ログの案内を付けます。setup の終了コードが非ゼロの場合、prepared files による代替経路を試してから失敗させます（`terminal/strata_cli/launch/runner.py:1782-1802`）。
- `--plan` はモデル名・指定フォルダー・準備計画を表示し、「Nothing was changed.」を出して終了します（`terminal/strata_cli/launch/cmd.py:897-925`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-87` — `strata launch` parser の登録。値は `PATH`、短縮別名なし。
- `terminal/strata_cli/launch/cmd.py:215-239` — preset と引数から設定を組み立て、`~` を展開し、`--model` との関係を決める。
- `terminal/strata_control/models.py:813-851,854-905,920-951` — パスの絶対化、存在確認、候補探索、GGUF shard と複数モデル群の判定。
- `terminal/strata_cli/launch/runner.py:1406-1412,1486-1512` — setup への `--gguf-dir` 転送、既存設定の再利用条件。
- `terminal/strata_cli/launch/runner.py:1956-2006,3296-3343` — 事前検査、モデル準備、失敗・起動経路。

調査対象の checkout は `git status --short --branch` で `## main...origin/main` と確認しました。作業ツリーに未コミット変更はありません。CLI help は実行せず、同一 revision のソース parser と処理を根拠にしました。
