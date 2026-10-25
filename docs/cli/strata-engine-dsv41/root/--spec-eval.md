# `--spec-eval`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--spec-eval` |
| 別名 | なし |
| 値 | IDS JSON ファイルのパス（必須） |

## 役割

IDS JSON に含まれる各 segment を独立した prompt としてモデルに feed し、その後 greedy decoding と DSpark speculative decoding を行い、segment ごとの token 数・round 数・採用 draft 数を評価ログに出します。`--spec-eval` は実行モードを選択するオプションで、実際の生成上限は [`--n`](--n.md)、speculative decoding の有効性は [`--dspark`](--dspark.md)、draft の confidence 下限は [`--dspark-conf`](--dspark-conf.md) に依存します。

## 使い方

```sh
strata-dsv41 --pack /models/example/maya-ds4 --spec-eval ./ids.json --n 32
```

`ids.json` は `tools/quant_quality.py` が使う形式を想定し、各 segment に `name` と整数列の `ids` を含めます。`--pack` は必須です。DSpark の起動時既定値は有効ですが、モデル内に drafter がなく `--dspark off|none` を指定するなどの場合、speculative draft は使われず通常の1 token step に fallback します（`src/dsv41/ds4_main.cpp:167-203,1224-1229`）。

## 値と既定値

- 値は必須です。値を省くと `--spec-eval needs a value` を stderr に出して終了コード 2 になります。値の形式・JSON 構造を parser 自体は検証せず、`--spec-eval` が複数回あれば最後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1208,1262`）。
- この option 自体に既定値はありません。未指定では spec-eval モードになりません。
- 指定された値は `read_score_ids()` で読み込みます。ファイルを開けない場合、または `name` と `ids` を含む segment を一つも読み取れない場合はエラーになります。読み取り処理は JSON ライブラリによる厳密な JSON 検証ではなく、文字列から `"name"`、`"ids"`、角括弧を検索して整数を抽出する実装です（`src/dsv41/ds4_main.cpp:71-83,967-1004`）。
- `--n` の既定値は 0 です。eval 関数は生成上限にかかわらず各 segment で最初の greedy token を sample し、`emitted < n` の間だけ round を続けます。そのため `--n` を省略、または 1 以下にすると round は行わず、各 segment の出力統計は token 数 1 になります（`src/dsv41/ds4_main.cpp:1191,1255-1257,1154-1173`）。

## 実行時の動作

1. 起動時に他の mode 指定と同様に model pack を読み込みます。`--serve` が指定されると serve が先に実行され、`--spec-eval` は選ばれません。serve 以外では `--profile-run` が先、続いて `--spec-eval`、`--score`、通常の処理の順です（`src/dsv41/ds4_main.cpp:1282-1301`）。
2. IDS JSON の segment ごとにモデル状態を reset し、prompt IDs を `--window` で指定された chunk に分けて feed します。`--window` 未指定時は、この mode では 16 が使われます。最後の chunk には終端 feed の flag を渡します（`src/dsv41/ds4_main.cpp:1191,1297-1300,1132-1153`）。
3. 各 segment で `m.sample(0.0f, 1.0f, 1, 0.0f, 1, ...)` により greedy の初回 token を取得します。その後の round も温度 0、top-p 1、top-k 1、seed 1 で進み、`--n` が round 上限を決めます。EOS token ID `1` が生成されるとその segment の decode を止めます（`src/dsv41/ds4_main.cpp:1154-1173`）。
4. round は起動時の `spec` と model の drafter block が有効で、残り枠が 2 以上の場合に draft を生成します。draft は `--dspark-conf` の confidence 下限を満たす間だけ検証へ進みます。該当 draft がなければ通常の1 step に fallback します（`src/dsv41/ds4_main.cpp:167-203,1160-1165,1224-1229`）。
5. 各 segment の処理後、stderr に segment 名、prompt 長、生成 token 数、round 数、平均 token/round、採用 draft 数、経過時間を表示します。stdout への通常生成 token 出力はこの関数にはありません（`src/dsv41/ds4_main.cpp:1174-1179`）。

## 適用条件と副作用

- `strata-dsv41` は CMake の `STRATA_BUILD_DSV41=ON` で生成される独立 executable で、この option の parser は `src/dsv41/ds4_main.cpp` にあります（`CMakeLists.txt:797-811`）。
- `--spec-eval` は model load 後のモード分岐です。`--pack` と何らかの mode 指定がなければ usage を stderr に出して終了コード 2、model load 失敗は stderr にエラーを出して終了コード 1 です（`src/dsv41/ds4_main.cpp:1282-1294`）。
- `DS4_ROUND_LOG` 環境変数が設定されている場合、そのパスを `wb` で開いて round ごとの TSV 行（segment 名、検証 draft 数、採用数、各 draft の confidence）を書きます。既存ファイルは切り詰められます。open の戻り値は検査されず、失敗時は round log が無効のまま評価を続けます。segment ごとに flush します（`src/dsv41/ds4_main.cpp:147-150,188-192,1139,1177`）。
- IDS file の open/segment 読み込み、prompt feed、draft/verify/step の失敗は stderr にエラーを出し終了コード 1 です（`src/dsv41/ds4_main.cpp:1132-1152,1160-1165`）。

## 根拠

- 索引と scope: `docs/cli/README.md:1387` — `strata-engine-dsv41` root の option として掲載。
- 独立 executable と build 条件: `CMakeLists.txt:797-811`。
- usage、parser、初期値、option 適用と mode 優先順: `src/dsv41/ds4_main.cpp:85-94,1187-1208,1262-1273,1282-1301`。
- IDS JSON の読み込みと整数抽出: `src/dsv41/ds4_main.cpp:71-83,967-1004`。
- segment 単位の reset/feed、初回 sample、round loop、統計出力: `src/dsv41/ds4_main.cpp:1130-1179`。
- DSpark round と confidence 判定/fallback: `src/dsv41/ds4_main.cpp:152-203`。
- `DS4_ROUND_LOG` のファイル出力: `src/dsv41/ds4_main.cpp:147-150,188-192,1139,1177`。
- 安全に実行できる同一 revision の既存 CLI バイナリは確認していないため `--help` は実行していません。parser と実処理をソースで照合しました。Release artifact の配布状況や GPU/backend ごとの実行結果は確認範囲外です。
