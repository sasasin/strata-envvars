# `setup.py --replicas`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから起動） |
| オプション | `--replicas` |
| 別名 | なし |
| 値 | 整数 `N`。明示的な範囲指定はない |

## 役割

選択した複数 GPU を `N` 個の同じ大きさのグループに分け、モデルごとの run config に replica 数を保存する。サーバー起動時には各グループで独立したエンジンを起動し、ひとつの HTTP サーバーがリクエストを各エンジンへ振り分ける。モデルの層を複数 GPU に分割する代わりに、複数の独立した実行系を使う設定であり、明示したときだけ有効になる（`terminal/setup.py:11589-11592`、`terminal/strata_control/setup_config.py:517-530`、`terminal/serve/server.py:8829-8842`）。

この文書は `source-setup` の root parser に対するもの。macOS で Control モードではなく、Hy4 / Inkling の指定もない場合、`setup.py` は root parser より前に `engine/metal/setup_mac.py` へ処理を委譲する。その Mac 経路には `--replicas` の宣言がないため、この説明の適用対象外（`terminal/setup.py:11434-11437`、`engine/metal/setup_mac.py` に `--replicas` の parser 定義なし）。

## 使い方

```sh
# 4 枚を 2 枚ずつ使う 2 replica の設定を作る
./setup.sh --gpus 0,1,2,3 --replicas 2

# インストールと設定保存まで行い、サーバーは起動しない
./setup.sh --gpus 0,1,2,3 --replicas 2 --no-start
```

`--gpus` は複数 GPU を選ぶ setup 側の引数である。単一 GPU を選ぶ `--gpu` では均等な複数グループを構成できない（`terminal/setup.py:11489-11498`、`terminal/strata_control/setup_config.py:517-526`）。

## 値と既定値

- `type=int` で整数に変換され、既定値は `None`（未指定）。値の選択肢や下限は parser では制限されていない（`terminal/setup.py:11589-11592`）。整数に変換できない値は `argparse` の引数エラーになる。
- setup の設定処理は `N >= 2` の場合だけ replica 設定を作る。`N` が `0`、`1`、または負数の場合は拒否や警告をせず、この処理では `replicas` を新たに設定しない（`terminal/strata_control/setup_config.py:517-530`）。
- `N >= 2` でも、選択 GPU がない、または GPU 数が `N` で割り切れない場合は警告を出して新しい `replicas` 値を設定しない。たとえば 4 GPU を `N=3` に分けることはできない。成功時は連続する選択 GPU を同数ずつグループ化する（`terminal/strata_control/setup_config.py:517-526`）。
- 不正な GPU 数でも setup 自体はこの条件で停止せず、後続処理へ進む。以前の run config がある場合、`replicas` は setup が管理する `SETUP_KEYS` に含まれず、今回の新 config に同じキーがなければ `carry_over` によって以前の値が保持される。このため、不成立の指定や `N < 2` は既存値を解除する指定にはならない（`terminal/setup.py:7544-7545,7557-7568`）。

## 実行時の動作

有効な指定では、setup は `cfg["replicas"] = N` を設定し、グループごとの GPU 数と割り当てを `[ok]` メッセージで示す。`--layer-split` に `auto` 以外の値があり、各 replica に複数 GPU を割り当てる場合は、その layer split が各グループに適用されることを警告し、`auto` を使うよう案内する。ホスト CPU 数が `8 * N` 未満の場合も、各 replica がモデルの RAM コピーと host thread を持つ点を警告する（`terminal/strata_control/setup_config.py:524-530`）。

設定はモデルごとの `strata-<model>.json` に保存され、既存ファイルと内容が異なる場合は書き換え前に `.bak` を作る。`--no-start` がなければ setup はその設定を使って直ちにサーバーを起動する（`terminal/setup.py:7715-7748,12521-12527,12555-12562`）。

サーバーは run config の `replicas` と `gpu` からグループを解決し、構成が無効なら `[strata] config ...` で終了する。グループができた場合、各グループに個別の `StrataEngine` を起動して `ReplicaEngine` の前段に置く。ルーターは生存中の engine から、会話 token のキャッシュ一致分と実行中リクエスト数に基づくコストが低い replica を選ぶ（`terminal/serve/replicas.py:529-543,568-586`、`terminal/serve/server.py:9460-9477,8829-8852`）。

setup の `--replica-profile` による自動設定は、明示した `--replicas` がない場合に限り候補になる。また `--layer-split` が未指定または `auto` の場合に限られる。したがって明示した `--replicas` はこの自動プロファイルの選択を抑止する（`terminal/strata_control/setup_config.py:487-500,517-524`）。

## 適用条件と副作用

- Replica 数は複数 GPU が選択され、GPU 数を均等に分割できる場合にのみ今回の setup 設定へ反映される。実際のエンジン起動時には各 replica がモデルの独立したコピーを持ち、メモリ使用量が増える（`terminal/strata_control/setup_config.py:517-530`、`terminal/serve/replicas.py:21-26`）。
- setup は replica ごとの `log` と `expert_profile_save` のパスに `.r<番号>` を付け、replica 設定に個別 `env` / `args` があれば共通設定に重ねる（`terminal/serve/replicas.py:252-267`）。
- `replica_shared_arena` または `STRATA_REPLICA_SHARED_ARENA` が別途有効なら、対応する Linux / Windows 環境では expert arena を共有する計画を試みる。これは `--replicas` 単独では有効にならず、Linux ではメモリや `/dev/shm` の空き、engine 引数などの条件により共有を使わず各 replica が個別コピーを持つ場合がある（`terminal/serve/replicas.py:161-224`）。
- サーバー起動時、replica engine が一部だけ起動失敗し共有 arena がある場合は、共有 arena 上で失敗した engine の再起動を試みる。それでも失敗する、または共有 arena なしで起動失敗した場合は、起動済み engine と arena を閉じ、`SystemExit` で失敗理由を出す（`terminal/serve/server.py:8866-8889`）。

## 出力とエラー

- GPU グループを作れないときは `warn()` が `[!]` の警告を出して処理を続ける。`--output jsonl` を併用している場合、同じ警告は `warning` イベントとして出力される（`terminal/strata_control/setup_config.py:519-523`、`terminal/setup.py:967-980,1044-1047`）。
- 起動時の run config が不正な場合、サーバーは `[strata] config ...` を理由に終了する。個別 engine の起動失敗は `replica <番号> did not start: ...` の失敗メッセージになる（`terminal/serve/server.py:9460-9464,8883-8889`）。
- `N` が整数でない場合の parser の usage/error 出力は Python `argparse` に委ねられる。この調査では同一 revision の CLI help 実行による表示確認は行っていない。

## 根拠

- `terminal/setup.py:11589-11592` — root parser の `--replicas` 宣言、型、説明。
- `terminal/setup.py:11434-11437` — macOS で Metal setup に委譲する分岐。
- `terminal/setup.py:12521-12527,12555-12562` — 設定組み立て・保存と、`--no-start` 以外での起動。
- `terminal/strata_control/setup_config.py:487-500,517-530` — 自動 replica profile との優先関係、GPU 分割条件、警告、config への値設定。
- `terminal/setup.py:7544-7545,7557-7568,7715-7748` — setup 管理キー、以前の設定の引継ぎ、既存 config のバックアップと保存。
- `terminal/serve/server.py:8829-8896,9460-9477` — replica ごとの engine 起動、失敗時の処理、起動経路。
- `terminal/serve/replicas.py:55-84,161-224,252-267,529-586` — GPU グループ、共有 arena 条件、replica ごとの設定、実際の振り分け処理。
