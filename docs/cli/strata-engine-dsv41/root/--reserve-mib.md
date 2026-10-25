# `--reserve-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 専用エンジン） |
| オプション | `--reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数として扱われる値。parser は `std::atoll` で変換する |

## 役割

各 GPU で他のプログラム向けに空けておく VRAM 量を、エンジンのモデル配置・expert 容量計算から差し引きます。既定値は各 GPU あたり 600 MiB です。ソース上の用途は容量見積もりであり、このオプション自身が VRAM を確保したり、指定量の空き容量を実行中に保証したりするものではありません。

## 使い方

```sh
strata-dsv41 --pack /models/example/maya-ds4 --reserve-mib 1200 --ids 1,2
```

`--pack` と推論用の `--ids` を付けた実行例です。実行ファイルは `STRATA_BUILD_DSV41=ON` で生成される独立 CLI で、CMake 上は GPU backend が有効な構成で作られます（`CMakeLists.txt:797-811`）。

## 値と既定値

- 値は `--reserve-mib N` の形で指定し、MiB 数として `std::atoll` に渡されます（`src/dsv41/ds4_main.cpp:1212-1214`）。
- 省略時は `600`（MiB）です（`src/dsv41/ds4_model.hpp:25-30`）。
- parser は `atoll` の変換結果をそのまま設定し、数値形式、非負条件、上限を検査していません。したがって不正な数値文字列は `atoll` の変換規則で値になり、数値として読めない文字列は通常 0 になります。負数も拒否されません（`src/dsv41/ds4_main.cpp:1212-1214`）。
- 同じオプションを複数回指定すると、引数を順に読む parser が同じ設定値を上書きするため最後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1214`）。
- 値を省略すると `%s needs a value` を stderr に出して終了コード 2 で終了します（`src/dsv41/ds4_main.cpp:1202-1207`）。

## 実行時の動作

モデル load 中に CUDA の `cudaMemGetInfo` で得た各 GPU の空きバイト数から、`reserve_mib * 2^20` を差し引き、負の余剰は 0 として GPU ごとの容量を見積もります。この見積もりは CPU 側 expert 配置の自動判定や DSpark 自動ロード判定、モデル層の GPU 分割に使われます（`src/dsv41/ds4_model.cu:1890`, `1962-1966`, `2002-2009`, `2072-2080`）。

expert の VRAM 容量についても、現在の空き VRAM から同じ reserve を差し引き、`--vram-experts` の係数を適用して候補容量を計算します。モデル内の複数経路でこの余力を用います（`src/dsv41/ds4_model.cu:2600-2608`, `2800-2814`, `3812-3821`）。GPU を選ぶ `--gpus` により対象デバイスが決まり、reserve は選択された各 GPU に個別適用されます。`--vram-experts` は expert 用余力に掛ける係数として相互作用します（`src/dsv41/ds4_model.hpp:27-30`, `src/dsv41/ds4_main.cpp:1210-1214`, `src/dsv41/ds4_model.cu:1876-1890`, `1962-1966`）。

予約差引後に prompt buffer が収まらない場合、エンジンは chunk サイズを段階的に小さくし、最終的に prompt を window 単位で実行する経路へ切り替えることがあります。その際は stderr に buffer 不足と遅くなる可能性を示すメッセージが出ます（`src/dsv41/ds4_model.cu:2578-2595`）。

オプション値は `--pack-info`、`--help`、`--version` の早期終了経路ではモデル load に到達しないため使われません（`src/dsv41/ds4_main.cpp:1251-1253`, `1266-1268`, `1275-1285`）。

## 適用条件と副作用

- モデルを load する DSV41 engine の実行で使われます。`--serve` も通常の引数検査の後に `Model::load` を呼ぶため、同じ容量計算の対象です（`src/dsv41/ds4_main.cpp:1282-1296`）。
- GPU ごとの空き容量を見積もりに使い、モデル分割、expert 用の VRAM 枠、CPU lane 用 expert 読み込みの自動判断、DSpark の自動判断、prompt buffer の経路に影響します。GPU やモデルの実際の空き容量が後から変わっても、指定 MiB を物理的に維持する保証はありません。
- 負数は parser で拒否されず、容量計算では `size_t` に変換される箇所があります。そのため意図した「負の予約量」として扱われるわけではなく、巨大な差引値となり利用可能量をほぼ 0 と見積もる可能性があります（`src/dsv41/ds4_model.cu:1963-1965`, `2072-2079`）。負数の挙動は有効な設定として推奨できません。
- 数値文字列以外の処理、整数範囲外の変換、各 GPU/backend での詳細な実測影響は、この調査では実行確認していません。実行バイナリや Release 配布物の help も照合していません。

## 出力とエラー

`--reserve-mib` 固有の validation error や警告は parser にありません。オプション値を使った後のモデル load が失敗すると、main は `maya-ds4: <エラー内容>` を stderr に出し、終了コード 1 を返します（`src/dsv41/ds4_main.cpp:1289-1294`）。予約量によって prompt buffer の確保に失敗した場合は、chunk の縮小または window 実行への切替メッセージが stderr に出ます（`src/dsv41/ds4_model.cu:2581-2591`）。

## 根拠

- 索引上のスコープとリンク: `docs/cli/README.md:1353-1382`。
- parser と引数不足・未知 option の処理: `src/dsv41/ds4_main.cpp:1200-1214`, `1266-1273`。
- 既定値: `src/dsv41/ds4_model.hpp:25-30`。
- GPU 空き容量の取得と reserve を用いる容量計算: `src/dsv41/ds4_model.cu:1870-1890`, `1946-1966`, `1997-2009`, `2057-2080`, `2597-2612`, `2799-2814`, `3812-3821`。
- 独立 executable の build 条件: `CMakeLists.txt:797-811`。
