# `strata drafting plan --engines-unloading`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--engines-unloading` |
| 別名 | なし |
| 値 | 値を取らない真偽スイッチ。指定すると有効 |

## 役割

Strata の既存エンジンが新しいエンジンの開始前に解放する GPU メモリを、all-cards split engine の開始可否を見積もる際に空きメモリとして数えます。`strata drafting plan` が DFlash2 の drafter と split engine 用 MTP のどちらを計画に示すかに影響します。実際にエンジンを停止したり、メモリを解放したりするオプションではありません（`terminal/strata_cli/drafting_cmd.py:45-61, 123-125`）。

## 使い方

```sh
strata drafting plan --config ./run.json --engines-unloading
```

`--config` を省略した場合も指定できます。対象モデルの設定や GPU を明示しない場合は、コマンドが利用できる情報から計画を判断します（`terminal/strata_cli/drafting_cmd.py:25-38, 101-124`）。

## 値と既定値

値を取らない `argparse` の `store_true` オプションです。省略時は `False`、指定時は `True` になります。受理する値の範囲や別名はなく、値の validation もありません。parser はこの隠しオプションを `drafting plan` と `drafting fetch` の両方に登録しています（`terminal/strata_cli/drafting_cmd.py:22-38`）。

## 実行時の動作

`drafting plan` では、Hy4-Flash と Inkling-2-Mini の専用分岐を通らない場合に、設定から GPU の index を取り出し、`_split_expected` が all-cards split engine の開始可否を問い合わせます。これらのモデルは split 判定前に専用の plan 結果を返すため、このフラグは結果に影響しません（`terminal/strata_cli/drafting_cmd.py:156-208, 214-227`）。オプション指定時は GPU probe の各カードについて `free_mib` を `None` に置き換えます。split engine の `Card.room_mib` はこの値が `None` のとき空き容量ではなくカード全体の VRAM 容量を使うため、他プロセスが現在使っている分を差し引かずに見積もります（`terminal/strata_cli/drafting_cmd.py:45-59`; `terminal/strata_control/split_engine.py:96-103`）。

この見積もりが成立し、ドラフティングの選択が `auto` または `mtp` で、かつ `--no-split` が指定されていない場合、plan は選択を `mtp` にし、結果に `split: true` と split engine 用の説明を含めます。それ以外ではこのフラグによる切り替えはありません（`terminal/strata_cli/drafting_cmd.py:120-125, 214-227, 247-265`）。判定には run config の `split_engine` のほか環境変数 `STRATA_SPLIT_ENGINE` も関わります。環境変数に非空値があれば設定値より優先され、split engine が `off` なら見積もりは成立しません（`terminal/strata_control/split_engine.py:435-453, 477-513`）。

オプション自体が作用するのは計画判定です。split engine が使われると plan の対象モードや必要な drafter の判断が変わりますが、このオプションを付けた `plan` がエンジンをアンロードしたり、ダウンロードしたりする処理はありません。コマンドの plan 経路は結果を human または JSON で標準出力に出して終了します（`terminal/strata_cli/drafting_cmd.py:247-266`）。

## 適用条件と副作用

`_split_expected` は `strata_control.split_engine.expected` を呼びます。同関数は設定の split engine モード、drafting 選択、ユーザー引数、replicas、KV 型、OS、GPU、RAM、モデル情報なども判定し、いずれかの条件を満たさない場合は split engine 不使用とします（`terminal/strata_control/split_engine.py:477-511`）。したがって、このフラグだけで split engine の使用が保証されるわけではありません。`--no-split` は split engine を使わずに判定するため、`--engines-unloading` と併用しても計画モードは切り替わりません（`terminal/strata_cli/drafting_cmd.py:123-125`）。

GPU 情報の取得自体は通常の probe を通じて行われます。NVIDIA では `nvidia-smi`、AMD では OS に応じた情報源からカードを調べます（`terminal/strata_control/split_engine.py:295-298, 326-393`）。このフラグは probe のメモリ値を見積もり用に置き換えるだけで、デバイスの状態は変更しません。判定中に例外が起きた場合、`_split_expected` は `False` を返し、plan の処理は split engine を使わない側へ進みます（`terminal/strata_cli/drafting_cmd.py:60-61`; `terminal/strata_control/split_engine.py:512-513`）。

なお parser は同じオプションを `drafting fetch` にも登録し、その共通入力処理でも split 判定に渡します。ただし、この文書の対象は索引上の `drafting plan` であり、fetch のダウンロード動作は扱いません（`terminal/strata_cli/drafting_cmd.py:22-38, 101-125, 240-246`）。

## 出力とエラー

plan の通常出力は human 形式では計画文、`--output json` または `--output jsonl` では JSON です（`terminal/strata_cli/drafting_cmd.py:38, 247-266`）。`--engines-unloading` に固有の validation error や警告出力は定義されていません。split engine 判定内の例外はエラーとして表に出さず、判定結果を `False` にします（`terminal/strata_cli/drafting_cmd.py:60-61`; `terminal/strata_control/split_engine.py:512-513`）。

## 根拠

- parser と option 登録: `terminal/strata_cli/drafting_cmd.py:19-38`
- split engine 用 GPU メモリ見積もりと失敗時の扱い: `terminal/strata_cli/drafting_cmd.py:45-61`
- plan の入力と split 判定適用条件: `terminal/strata_cli/drafting_cmd.py:101-136, 156-227`
- plan 出力: `terminal/strata_cli/drafting_cmd.py:247-266`
- GPU 空きメモリを使う容量計算: `terminal/strata_control/split_engine.py:88-103`
- split engine 判定と例外時の戻り値: `terminal/strata_control/split_engine.py:435-453, 477-513`
