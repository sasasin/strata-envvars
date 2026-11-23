# `--replica-profile`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（source setup、トップレベル） |
| オプション | `--replica-profile` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると `True`。既定値は `False`。 |

## 役割

複数 GPU で新しいモデル設定を作るとき、対応する Qwen3.8-Flash-Next の量子化モデルなら、1つの layer-split engine の代わりに GPU ごとの独立 engine（replicas）を使う設定を opt-in で提案・保存する。適用時は RAM から起動可能な engine 数を選び、共有 expert arena、いくつかの実行環境変数、VRAM 予約量、条件に応じた `parallel` 数も設定する。フラグの宣言は `terminal/setup.py:11372-11376`、複数 GPU の設定構築と適用呼び出しは `terminal/strata_control/setup_config.py:476-500` にある。

## 使い方

`terminal/` ディレクトリで実行する例。モデルの選択など、他の setup 入力は通常どおり行う。

```sh
# GPU 0 と 1 で setup し、対応モデルなら replica profile を使う
python setup.py --gpus 0,1 --replica-profile
```

`--gpus` は複数カードを選ぶ引数で、`--replica-profile` は追加値を取りません（`terminal/setup.py:11271-11280`、`11372-11376`）。

## 値と既定値

- `argparse` の `store_true`、`default=False`。引数値の型変換や CLI 値の範囲 validation はない（`terminal/setup.py:11372-11376`）。
- このフラグを付けると設定生成時に `cfg["replica_profile"] = True` が設定される。フラグを付けないことだけで、既存 config 内の明示的な `false` を新たに書き込むわけではない（`terminal/strata_control/setup_config.py:487-495`）。
- `STRATA_REPLICA_PROFILE` 環境変数でも適用を要求できる。プロファイル関数は値を trim し小文字化して `1` / `on` / `yes` / `true` を有効値とする。それ以外の値は無効（`terminal/strata_control/setup_config.py:487-495`、`terminal/strata_control/replica_profile.py:40-49`）。

## 実行時の動作

`setup_config.config_for` は、選択 GPU が複数枚で、`--replicas` が未指定、`--layer-split` が未指定または `auto`、かつ CLI フラグまたは `STRATA_REPLICA_PROFILE` がある場合に profile を試す（`terminal/strata_control/setup_config.py:476-500`）。profile 側はさらに、設定内の replicas や `--peer-device` がなく、明示的 layer-split がなく、GPU が2枚以上で、モデル名または引数から Qwen3.8 と `iq3_s` / `iq3_xxs` / `q2_0` を識別でき、選択した各 GPU が24 GB以上であることを確認する（`terminal/strata_control/replica_profile.py:52-60`、`77-99`）。

条件を満たすと、RAM の見積りから engine 数 `k` を算出する。共有 arena が可能な platform では `RAM - 12 GB headroom - 量子化別 arena` を 8 GB 単位で数え、そうでない場合は各 engine の arena コピーも含めて算出し、2枚以上かつ選択カード数以下に制限する。選ばれた GPU それぞれを1 engine とする `replicas`、選択 GPU リスト、共有可能な場合の `replica_shared_arena: true` を config に加える（`terminal/strata_control/replica_profile.py:30-36`、`63-75`、`102-118`）。RAM 条件により一部の選択 GPU が使われないことがある（`terminal/strata_control/replica_profile.py:109-133`）。

profile は `STRATA_QSA_SLOTS`、`STRATA_BATCH_SELF_COMMIT`、`STRATA_SLOT_COPY_DIRECT`、`STRATA_CKPT_POOL`、`STRATA_CKPT_POOL_READY`、`STRATA_SLOT_CKPT_MOVE`、`STRATA_SLOT_COPY_BATCHSYNC` を config の `env` に既定値として設定する。プロセス環境に同名変数があれば追加せず、config 側に値があれば `setdefault` により保持する。また `--vram-reserve-mib` が args にない場合は `2500` を追加する（`terminal/strata_control/replica_profile.py:37-39`、`116-127`）。

`--parallel` が指定されず、config に `parallel` がなく、args に `--batch` / `--slots` がない場合、2 engines なら各 engine の `parallel` を8、それ以外は4にする。明示した `--parallel` または既存の parallel/slots 設定をこの既定値で置き換えない（`terminal/strata_control/setup_config.py:493-495`、`terminal/strata_control/replica_profile.py:134-136`）。`--replicas` または手動の layer split がある場合は profile 呼び出し条件から外れ、ユーザー指定を優先する（`terminal/strata_control/setup_config.py:487-488`）。

## 適用条件と副作用

- 対応モデル・GPU VRAM・RAM が条件に合わない場合は profile を適用せず、理由を setup の案内行として返す。2 engine 分の RAM がない場合も layer split のままとする（`terminal/strata_control/replica_profile.py:77-99`）。
- profile の適用中に例外が起きても setup 全体を失敗させず、`(the replica profile was not applied: ...)` を案内して続行する（`terminal/strata_control/setup_config.py:489-500`）。
- 成功時の設定は run config に保存される。setup は同じモデルの既存 config を更新し、変更がある場合は `.bak` を作ってから書き込む（`terminal/setup.py:12300-12306`、`7631-7663`）。
- これは setup 時の設定生成に作用するオプション。対象モデル以外や単一 GPU では profile の判定条件を満たさず適用されない。

## 出力とエラー

profile の判定理由または成功時の説明行は `setup_config.config_for` が `ok` / `say` を使って表示する。profile 内の例外は捕捉され案内文になります。parser 自体にこのオプション専用の validation error 経路はありません（`terminal/strata_control/setup_config.py:493-500`、`terminal/strata_control/replica_profile.py:104-136`）。

## 関連オプション

- [`--replicas`](--replicas.md)
- [`--parallel`](--parallel.md)
- [`--layer-split`](--layer-split.md)

## 根拠

- `terminal/setup.py:11372-11376` — parser 登録、フラグ形式、既定値。
- `terminal/setup.py:11271-11280` — GPU 選択引数の形式と layer-split の指定範囲。
- `terminal/strata_control/setup_config.py:476-500` — 複数 GPU 条件、profile 呼び出し、`--replicas` / layer-split との適用条件、例外時の継続。
- `terminal/strata_control/replica_profile.py:30-49` — 見積り定数、環境変数の有効値、opt-in 判定。
- `terminal/strata_control/replica_profile.py:52-99` — 対象モデル・GPU・RAM の条件と engine 数算出。
- `terminal/strata_control/replica_profile.py:102-136` — config 変更、env 設定、VRAM 予約、parallel の既定値。
- `terminal/setup.py:12300-12306`、`7631-7663` — 設定生成後の run config 保存と既存設定の backup。
