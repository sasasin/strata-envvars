# `ROCR_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata がこの変数を読むのは、Python server の HIP backend 起動時に行う AMD GPU 自動選択を抑止するためです。値をデバイス番号として解釈したり、この変数の値から `HIP_VISIBLE_DEVICES` を設定したりはしません。非空の値があると Strata の自動選択 probe を行わず、構築済みの環境変数を engine に渡します（`serve/server.py:3622-3628,3747-3790`）。

## 値と判定

| server に渡される値 | 判定 |
|---|---|
| 未設定 | 偽。ほかの条件を満たせば自動選択の対象になる |
| 空文字 `""` | 偽。ほかの条件を満たせば自動選択の対象になる |
| 空でない任意の文字列 | 真。自動選択 probe を抑止する。値の構文・数値・デバイス名の検査はしない |

判定は `env.get("ROCR_VISIBLE_DEVICES")` の Python truthiness です。したがって `"0"`、空白だけの値、その他の非空文字列はすべて同じく probe を抑止します。これは Strata がその値を検証・適用するという意味ではありません（`serve/server.py:3626-3628`）。

## 有効になる条件

この判定が実行されるのは `child_env()` が HIP backend の環境を組み立てる経路です。自動選択 probe は backend が `hip` で、設定に GPU 指定がなく、全 GPU が Off ではなく、`hip_ordinal` が空で、`HIP_VISIBLE_DEVICES` と `ROCR_VISIBLE_DEVICES` の両方が空の場合に限って試みられます。したがって、非空の `ROCR_VISIBLE_DEVICES` はその自動選択を抑止します。`HIP_VISIBLE_DEVICES` の非空値、GPU 指定、`hip_ordinal` もそれぞれ probe を抑止します（`serve/server.py:3622-3628`）。

`child_env()` はまず親プロセス環境をコピーし、その後 config の `env` 項目で同名キーを上書きします。そのため親環境の値だけでなく config の `env.ROCR_VISIBLE_DEVICES` も判定対象です。config 側で空文字に上書きすれば、この判定上は値なしとして扱われます（`serve/server.py:3747-3760,3782-3790`）。

## 実行時の詳細

判定は `child_env()` の呼び出しごとに、コピーおよび config の環境変数上書き後に行われます。モジュール初期化時の固定値や static cache はありません。server はこの環境辞書を engine 起動に渡し、同じ辞書を自動選択用の `strata-device --list-devices` probe にも渡します（`serve/server.py:3629-3637,3747-3790,8710,8777,9193`）。

自動選択が試される条件でも、隣接する `strata-device` が存在しない、起動に失敗する、timeout する、または非ゼロ終了する場合は probe 結果を使わず `None` を返します。probe が成功し、検出デバイスに実行可能なカードがない場合は `SystemExit` で問題文を出します。自動選択でカードが選ばれた場合は `[strata] automatic GPU choice: ...` を出し、選んだ番号を `HIP_VISIBLE_DEVICES` に設定します。これらは probe の処理経路の結果であり、`ROCR_VISIBLE_DEVICES` 固有の警告やエラーではありません（`serve/server.py:3629-3650,3782-3790`）。

`ROCR_VISIBLE_DEVICES` について Strata 自身が出すログ、独自の終了経路、値ごとの fallback はありません。ROCm runtime や driver がこの値をどう扱うかは本調査の対象外です。

Strata の `docs/AMD_HIP.md:241` は必要に応じて `ROCR_VISIBLE_DEVICES` または `HIP_VISIBLE_DEVICES` で AMD device を選ぶよう案内し、`docs/OLDER_GPUS.md:40` は特定の RX 5700 XT 構成で同変数を必要とする旨を記しています。これらは利用案内であり、上記の server 実装は値を選択・検証しません。実際の device filtering の意味は Strata のコードからは確認できません。

## 根拠

- `serve/server.py:3622-3628` — HIP 自動選択 probe の条件と `ROCR_VISIBLE_DEVICES` の truthiness 判定。
- `serve/server.py:3629-3650` — probe の起動、失敗時の return、選択ログおよび no-runnable-card 時の終了。
- `serve/server.py:3747-3790` — 親環境のコピー、config `env` による上書き、HIP 経路での判定、選択結果の `HIP_VISIBLE_DEVICES` 設定。
- `serve/server.py:8710,8777,9193` — 組み立てた環境を server の engine 起動経路へ渡す箇所。
- `docs/AMD_HIP.md:241`, `docs/OLDER_GPUS.md:40` — 同変数に関する利用案内。runtime/driver 側の意味を示す実装根拠としては使っていない。
