# `--no-start`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` などの入口から呼び出されるセットアップ CLI） |
| オプション | `--no-start` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False` |

## 役割

セットアップや既存モデルの設定処理を行ったあと、モデルサーバーを起動せずに終了します。新規・追加モデルの選択、必要なファイルの取得、設定の保存などを省略するフラグではありません。通常経路では完了後に起動するサーバーを止めるための指定です（`terminal/setup.py:11526`, `terminal/setup.py:12521-12562`）。

## 使い方

```sh
./setup.sh --no-start
```

この例はセットアップ処理を実行し、完了後にサーバーを起動しません。処理対象のモデルや設定を明示する場合は、同じコマンドに `--family`、`--model` などを加えます。

## 値と既定値

`argparse` の `store_true` で定義されており、値は不要です。指定すると `a.no_start` が真になり、省略時は偽です。別名や独自の値 validation はありません（`terminal/setup.py:11526`）。

## 実行時の動作

- `--no-start` は処理モード選択で明示的なセットアップ指定として扱われます。インストール済みモデルがあっても通常の「そのまま起動」経路を外れ、セットアップ側の処理へ進みます（`terminal/setup.py:11681-11699`）。
- 通常のインストール経路では、実行設定を保存し、モデル用の起動スクリプトを作成して完了情報を表示したあと、`a.no_start` が真なら終了コード `0` を返します。偽なら同じ設定を `start()` に渡します（`terminal/setup.py:12521-12562`）。
- Hy4-Flash、Inkling-2-Mini、および own-path model のセットアップ経路でも、設定・起動スクリプト作成後に同様に起動を省略します（`terminal/setup.py:10021-10059`, `terminal/setup.py:10410-10421`, `terminal/setup.py:10949-10960`）。
- `--calibrate` と併用して既存設定を調整する経路では、調整は実行されますが、サーバー起動は省略されます。調整に失敗しても `--no-start` の場合は既定設定のまま終了する旨を警告し、コード上は起動を試みません（`terminal/setup.py:11734-11760`）。
- 通常のセットアップ経路では、`--no-start` を指定すると任意の調整確認を出さず、完了後のクイックベンチマーク確認にも進まずに終了します（`terminal/setup.py:12528-12562`）。

## 適用条件と副作用

`--no-start` 自体はファイル取得や設定変更を無効にしません。通常のセットアップ経路では、指定モデルに応じたセットアップの後で設定ファイルと起動スクリプトを書きます。したがって「インストールのみ」という help の説明は「サーバーを起動しない」意味であり、セットアップ副作用がない意味ではありません（`terminal/setup.py:12521-12527`, `terminal/setup.py:12555-12562`）。

`--setup` との併用に特別な制約はなく、どちらも明示的セットアップ経路に進めます。`--no-start` だけでも `explicit` 判定を満たします（`terminal/setup.py:11698`）。`--yes` は対話で推奨回答を受け入れる別フラグであり、`--no-start` の代替ではありません（`terminal/setup.py:11524-11526`）。

プラットフォームによって入口の処理が異なります。macOS では、Control モードや一部のモデルを除き、トップレベル `setup.py` は引数を `metal/setup_mac.py` に委譲します（`terminal/setup.py:11434-11437`）。そのため、この文書の処理詳細は `terminal/setup.py` の root parser と通常経路についてのものです。macOS の Metal セットアップ側の挙動は [mac 用 `--no-start` 文書](../mac/--no-start.md) を参照してください。

## 出力とエラー

通常のセットアップ経路では完了メッセージと作成した起動スクリプト名を表示してから、起動せず `0` を返します（`terminal/setup.py:12534-12556`）。このオプション専用のエラー処理はありません。モデル選択、取得、設定などの失敗は各処理の既存エラー経路に従い、`--no-start` はそれらを成功扱いに変更しません。`--output jsonl` を併用した場合は JSONL 出力モードも有効になりますが、`--no-start` による終了制御は同じです（`terminal/setup.py:11527-11529`, `terminal/setup.py:11606-11609`, `terminal/setup.py:12555-12571`）。

## 根拠

- parser 定義、値の型・既定値: `terminal/setup.py:11524-11529`
- セットアップと通常起動のモード選択: `terminal/setup.py:11676-11699`
- 通常の設定保存、起動スクリプト生成、調整・ベンチマーク・起動の分岐: `terminal/setup.py:12521-12562`
- キャリブレーション経路: `terminal/setup.py:11734-11760`
- own-path / Hy4-Flash / Inkling-2-Mini の終了分岐: `terminal/setup.py:10044-10059`, `terminal/setup.py:10410-10421`, `terminal/setup.py:10949-10960`
- macOS の委譲条件: `terminal/setup.py:11434-11437`; 委譲先 parser と終了分岐: `engine/metal/setup_mac.py:396-417`, `engine/metal/setup_mac.py:619`
