# `setup.py` `--no-remote-expert-opt`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（Linux では `./setup.sh`、Windows では `START-HERE.bat` などから起動） |
| オプション | `--no-remote-expert-opt` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると真になる（`store_true`）。 |

## 役割

複数 GPU 用の設定を作る際、setup が条件に応じてエンジン引数へ推薦追加する `--remote-expert-opt` を追加しないようにします。helper cache が設定されている場合だけ追加される推薦を抑止するもので、`--remote-expert-opt` というエンジン引数を直接設定するオプションではありません。実際の反映先は生成するモデルの run config の `args` です。

## 使い方

Linux の Strata checkout のルートから、複数 GPU の設定を作り、セットアップ後すぐにはモデルを起動しない例です（セットアップ自体は実行され、設定や必要なモデルファイルを作成・取得します）。

```sh
./setup.sh --setup --family qwen --gpus 0,1 --no-remote-expert-opt --no-start
```

## 値と既定値

- 値や引数は不要です。指定しなければ `False`、指定すれば `True` になります（`terminal/setup.py:11499-11500`）。
- `--no-remote-expert-opt=true` のような値付き指定や、直後に `true` / `false` を置く形式はこの parser のフラグ構文ではありません。parser は `main()` 内で `parse_args()` を呼びます（`terminal/setup.py:11444`, `terminal/setup.py:11606`）。
- 複数回指定しても真のままです。数値などの追加 validation はありません。

## 実行時の動作

通常のモデル設定生成では、選択 GPU が複数枚なら `config_for()` が `recommend_remote_expert_opt(cfg, off=a.no_remote_expert_opt)` を呼びます（`terminal/strata_control/setup_config.py:479-485`）。関数は GPU が2枚未満なら何もしません。複数枚の場合、`off=True` なら `args` に `--remote-expert-opt` があれば1項目を取り除いて戻り、なければそのまま戻ります。したがって、このフラグを指定したときは後続の pipeline 判定や helper cache の有無の判定を行わず、推薦追加もしません（`terminal/setup.py:2527-2540`）。

このフラグを指定しない通常の推薦経路では、正の値の `--pipeline-windows` があれば追加を見送り、helper cache 用の `--expert-cache-device1`〜`--expert-cache-device3` が `args` にある場合に限って `--remote-expert-opt` を追記し、`ok` メッセージを出します。helper cache がない場合は追加しません（`terminal/setup.py:2541-2561`）。このため、オプトアウトによる専用の成功メッセージはありません。

生成された config は `write_setup_config()` から書き込まれます。既存 config の手動追加 engine 引数は `carry_user_args()` で生成引数へ重ねられるため、以前の config の `user_args` などに `--remote-expert-opt` を明示している場合は、今回の推薦抑止後に引数として戻る可能性があります（`terminal/setup.py:7632-7660`, `terminal/setup.py:7715-7747`, 呼び出し `terminal/setup.py:12521-12526`）。

## 適用条件と副作用

- 索引上のスコープは `source-setup` の root（`setup.py` / wrapper 群）です（`docs/cli/README.md:1659-1701`）。Linux wrapper は受け取った引数を `setup.py` に渡します（`setup.sh:81`）。
- このフラグが `off` として渡されるのは、モデルの run config を組み立てる `setup_config.config_for()` の複数 GPU 分岐です。インストール済みモデルの起動処理では、既存設定に対する GPU 選択時に `recommend_remote_expert_opt(cfg)` が `off` なしで呼ばれます。また、起動時の GPU 自動提案経路も `off` なしです（`terminal/setup.py:8640-8652`, `terminal/setup.py:2607-2617`）。したがって、既存モデルの通常起動・GPU 選択に対する一律の抑止指定とは確認できません。
- `recommend_remote_expert_opt()` は設定辞書の `args` を変更します。エンジン起動や GPU 動作をこのフラグ自体が直接変更するのではなく、後続の config 保存に影響します（`terminal/setup.py:2534-2561`, `terminal/setup.py:12521-12527`）。
- 設定生成時に複数 GPU が選択されていなければ、関数は早期 return するため、このオプションによる追加の変更はありません（`terminal/setup.py:2534-2535`）。

## 出力とエラー

- オプトアウト分岐は `--remote-expert-opt` の削除後に return し、専用の `ok` / `warn` を出しません（`terminal/setup.py:2537-2540`）。
- 値を付ける形式は parser のフラグ定義に適合しません。Strata 独自の validation や専用エラー文は確認できず、引数解析は `argparse` の `parse_args()` に委ねられています（`terminal/setup.py:11444`, `terminal/setup.py:11499-11500`, `terminal/setup.py:11606`）。

## 根拠

- `terminal/setup.py:11499-11500` — parser 登録、`store_true`、help 文。
- `terminal/setup.py:11606` — parser による引数解析。
- `terminal/strata_control/setup_config.py:479-485` — 複数 GPU 設定から `off` を渡す箇所。
- `terminal/setup.py:2523-2561` — GPU 数、`off`、設定値、pipeline、helper cache による推薦条件と出力。
- `terminal/setup.py:2607-2617`, `terminal/setup.py:8640-8652` — `off` を渡さない既存モデル側の推薦呼び出し。
- `terminal/setup.py:7632-7660`, `terminal/setup.py:7715-7747`, `terminal/setup.py:12521-12527` — 手動 engine 引数の引き継ぎと生成 config の保存。
- `setup.sh:81` — Linux wrapper から `setup.py` への引数転送。
