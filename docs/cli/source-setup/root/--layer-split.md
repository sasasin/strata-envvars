# `--layer-split`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（setup.py のルートオプション） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | 必須の文字列。`auto` または、後続 GPU ごとの層開始番号を昇順のカンマ区切りで指定 |

## 役割

複数 GPU に一つのモデルを層単位で分けるとき、2 枚目以降の GPU が担当を始める層を指定します。これは各 GPU に割り当てる層数ではありません。通常の setup 経路では値をモデルの run config に記録し、起動時に server が engine の `--layer-split` 引数へ渡します。省略時は `auto` です。

## 使い方

```sh
# 2 GPU の通常 setup。後続 GPU は層 18 から担当し、設定だけ保存して起動しない。
./setup.sh --setup --family qwen --model IQ3_S --gpus 0,1 --layer-split 18 --no-start

# 3 GPU の通常 setup。2 枚目は層 16、3 枚目は層 32 から担当する。
./setup.sh --setup --family qwen --model IQ3_S --gpus 0,1,2 --layer-split 16,32 --no-start

# 複数 GPU を指定し、自動配置を明示する。
./setup.sh --setup --family qwen --model IQ3_S --gpus 0,1 --layer-split auto --no-start
```

## 値と既定値

- setup parser は値を取る文字列として登録しており、`choices`、数値変換、setup 時の値文法検査を行いません。値を省略すると `argparse` が引数不足として拒否します。 ( `terminal/setup.py:11496-11498` )
- 通常の multi-GPU setup では、値が未指定または空文字なら `auto` を config に保存します。`auto` は GPU の空き VRAM 等を使う配置選択を engine に委ねます。 ( `terminal/strata_control/setup_config.py:476-484` )
- 数値指定は GPU 数から 1 を引いた個数が必要です。各数値は `2` 以上で、前の数値より大きくなければなりません。たとえば 2 GPU で `18` なら最初の GPU が層 `0..17`、次の GPU が層 `18` から担当します。server は値を文字列または整数列として正規化し、この個数と昇順を検証します。 ( `terminal/serve/server_parts/engines.py:750-780` )
- `--layer-split` の重複指定時の setup parser の値は `argparse` が最後に解析した値です。setup 独自の重複指定処理はありません。 ( `terminal/setup.py:11496-11498`, `terminal/setup.py:11606` )

## 実行時の動作

通常の model setup では、複数 GPU が選ばれている場合に `a.layer_split` を config の `layer_split` に記録します。起動時に config の GPU が複数で、`--peer-device` による peer tier ではない場合、server は値を engine 引数へ追加します。GPU 指定なし、または単一 GPU の config では setup_config のこの代入条件に入らず、この値は split 設定として保存されません。 ( `terminal/strata_control/setup_config.py:476-484`, `terminal/serve/server_parts/engines.py:783-786`, `terminal/serve/server.py:3746-3748` )

通常の setup では `--replica-profile` または `STRATA_REPLICA_PROFILE` による自動 replica profile、および AMD の自動 profile は、`--layer-split` が未指定か `auto` のときだけ検討されます。replica 数を指定し、各 replica が複数 GPU を使う構成で明示的な数値 split を与えると、「各 group に同じ engine 値が適用されるため auto のままにする」旨の警告が出ます。 ( `terminal/strata_control/setup_config.py:487-508`, `terminal/strata_control/setup_config.py:517-530` )

HY4-Flash と Inkling-2 の setup は別の構成経路を通り、multi-GPU 条件を満たす場合にコードが `--layer-split auto` を生成します。Intel Arc の app setup でも複数カード選択時に config を `auto` にします。これらの経路では parser の `a.layer_split` を反映する処理を確認できませんでした。 ( `terminal/setup.py:10373-10385`, `terminal/setup.py:10764-10768`, `terminal/setup.py:10904-10925`, `terminal/setup.py:9421-9430` )

config 保存では、同一モデルの既存 config が変更される場合に `.bak` を作成してから書き込みます。`--no-start` を付けなければ通常 setup の最後にモデル起動へ進みます。 ( `terminal/setup.py:12521-12527`, `terminal/setup.py:7715-7747`, `terminal/setup.py:12555-12562` )

## 適用条件と副作用

- 実際の split は `strata serve` 経由の engine 起動でのみ有効です。engine は `--layer-split` に `--serve` が伴うことを要求します。 ( `engine/src/program/generate.cpp:4065`, `engine/src/program/generate.cpp:4783-4805`, `engine/src/program/generate.cpp:4848-4854` )
- `auto` で可視 GPU が 1 枚しかない場合、engine は「no split」と出力して split 指定を解除し、その GPU 単独で続行します。自動配置に有効な split がない場合はエラーで終了します。 ( `engine/src/program/generate.cpp:4836-4839`, `engine/src/program/generate.cpp:7501-7505` )
- setup parser は任意文字列を受理しますが、通常の multi-GPU 起動では server が engine 起動前に値を検査します。値の形式、GPU 数に対する個数、昇順・下限が不正なら `[strata] config ...` のエラーとして起動を止めます。 ( `terminal/serve/server_parts/engines.py:755-780`, `terminal/serve/server.py:9436-9441` )
- 数値がモデルの最終層を越える場合は server の形式検査後、engine が stderr にエラーを出して終了コード `2` で返します。engine は層分割開始後、各 GPU に割り当てる区間に応じて dense weights をロードします。 ( `engine/src/program/generate.cpp:7593-7598`, `engine/src/program/generate.cpp:7599-7609`, `engine/src/program/generate.cpp:7651-7668` )

## 出力とエラー

- multi-GPU setup は選択した GPU と split 値を `layer split across GPUs [...] (...)` と表示します。 ( `terminal/strata_control/setup_config.py:479-485` )
- server は起動前に正規化済み split 値を表示します。config 値が不正なら `[strata] config` を付けたエラーで終了し、engine の長時間ロードへ進みません。 ( `terminal/serve/server.py:9436-9441` )
- engine の指定がその GPU 数と一致しない、数値が 2 未満または昇順でない、`--serve` がない等の場合、stderr に `--layer-split ... needs --serve` の usage 形式を出し、終了コード `2` で終了します。指定層がモデルの最終層より後なら別の stderr エラーを出して終了コード `2` です。 ( `engine/src/program/generate.cpp:4841-4854`, `engine/src/program/generate.cpp:7593-7598` )

## 根拠

- `terminal/setup.py:11496-11498` — setup parser の宣言と help 文。
- `terminal/strata_control/setup_config.py:476-508` — GPU split の config 設定と自動 profile 条件。
- `terminal/strata_control/setup_config.py:517-530` — replica と明示 split の警告。
- `terminal/serve/server_parts/engines.py:750-786` — config 値の正規化・検証と split 適用判定。
- `terminal/serve/server.py:3746-3748`, `terminal/serve/server.py:9436-9441` — engine 引数への転送と起動前 validation。
- `engine/src/program/generate.cpp:4065`, `engine/src/program/generate.cpp:4783-4854`, `engine/src/program/generate.cpp:7501-7515`, `engine/src/program/generate.cpp:7593-7609`, `engine/src/program/generate.cpp:7651-7668` — engine parser、検証、自動配置、層境界と weight load の処理。
- `terminal/setup.py:10373-10385`, `terminal/setup.py:10764-10768`, `terminal/setup.py:10904-10925`, `terminal/setup.py:9421-9430` — 特殊な HY4-Flash / Inkling-2 / Intel setup の自動 split 設定。
- `terminal/setup.py:7715-7747`, `terminal/setup.py:12521-12527`, `terminal/setup.py:12555-12562` — config 保存、副 backup、setup 後の起動分岐。
