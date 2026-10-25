# `--mmap-experts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root のエンジン引数） |
| オプション | `--mmap-experts` |
| 別名 | なし |
| 値 | `on`、`off`、`auto`。値は必須 |

## 役割

GPU に載らない CPU 側の expert weight を、モデルファイルからその場で読むか、空き RAM が許す範囲で RAM にコピーするかを指定します。`auto` は既定値で、GPU に載せた後に残る expert の量と利用可能 RAM を見て選びます。ここでいう対象は CPU 側に残った expert であり、GPU に配置された expert の扱いを切り替えるものではありません。

## 使い方

```sh
strata-dsv41 --pack /models/example/maya-ds4 --ids 1,2,3 --n 16 --mmap-experts on
```

`--serve` で起動する場合も同じ root 引数として指定します。

## 値と既定値

- 省略時は `auto`（内部値 `-1`）です。
- `on` は内部値 `1`、`off` は `0` になります。
- parser は `on` / `off` 以外の値をエラーにせず内部値 `-1` にするため、`auto` のほか、未知の文字列も `auto` 相当になります。厳密な値検査はありません。
- 値を省略すると `--mmap-experts needs a value` を stderr に出し、終了コード `2` で終了します。複数回指定した場合は parser が順に代入するため最後の値が残ります。

## 実行時の動作

通常の pack では、`on` は CPU 側の expert をモデルファイルから読み、`off` は空き RAM の範囲で利用頻度の高い expert を RAM にコピーします。`off` でもコピーできない expert はファイルから読みます。コピーに使える量は、利用可能 RAM から他用途向けの余白を引いた量と Windows の commit 余裕の小さい方が上限です。`auto` は、GPU に収まらない expert の容量と、VRAM の他 weight・prompt buffer を考慮した配置可能量、利用可能 RAM を比較し、ファイルから読むモードを選ぶか決めます。

GGUF pack は expert のファイルを読み元として使うため、内部の `file_experts` 判定は `--mmap-experts` の値にかかわらず有効になります。その後のコピー処理では `off` のときだけ既定の RAM コピーを試み、`on` と `auto` は既定でコピー予算を 0 とします。したがって GGUF の `auto` は標準ではファイルから読み、`DS4_COPY_GB` を設定した場合だけ指定量のコピーが加わります。

`DS4_COPY_GB` が設定されると、RAM コピー処理の予算をその GB 値で上書きします。ただし `on` はコピー処理を早期に抜けるため、この環境変数で RAM コピーに切り替わりません。`--ssd-cache` を有効にした場合は、その RAM tier を使うため OS page cache の先読み量を 0 にします。

## 適用条件と副作用

- このオプションは独立した `strata-dsv41` engine の parser に属します。CMake の `STRATA_BUILD_DSV41=ON` で生成される optional target で、通常の `strata` engine の `--mmap-experts` とは値の形式も挙動も異なります。
- ファイルから読む場合、GPU に置けない expert をモデルファイル経由で読み、OS の file cache が保持できるページは cache に残ります。`off` は空き RAM を expert コピーに使うため、その分プロセスの RAM 使用量が増えます。
- `off` で全ての対象 expert が RAM に収まらない場合は警告を出し、最頻出側からコピーし、残りはファイルから読みます。個々の layer の RAM 確保に失敗したときも、その layer のコピーを諦め、ファイル上に残します。
- 明示値のほかに option 固有の相互排他条件や失敗終了は確認できません。GPU 配置や prompt の chunk 既定値には `file_experts` 判定が使われるため、値や `auto` の判定結果がそれらにも影響します。

## 出力とエラー

ファイル読み込みが選ばれたときは stderr に、GPU に載らない expert の概算容量、RAM の空き、先読みする量、prompt chunk 数を出します。`off` で RAM が足りずコピー対象を残す場合は、足りない容量と、残りをファイルから読む旨を警告します。layer 単位の RAM 確保に失敗した場合は、その layer の expert をファイル上に残す旨を stderr に出して続行します。

未知のコマンドライン option は `unknown option ...` と usage を stderr に出し、終了コード `2` です。`--mmap-experts` の値自体は未知文字列でも `auto` 相当に変換されるため、この理由では失敗しません。

## 根拠

- CLI usage と値の説明: `src/dsv41/ds4_main.cpp:85-93`
- parser、値変換、option 不明時の出力と終了コード: `src/dsv41/ds4_main.cpp:1200-1207,1235-1238,1266-1272`
- 既定値と内部表現: `src/dsv41/ds4_model.hpp:34-36`
- auto 判定、GGUF 時の特別扱い、prompt chunk 既定値への反映: `src/dsv41/ds4_model.cu:1946-1969`
- file tier の容量・先読み量の出力: `src/dsv41/ds4_model.cu:2597-2618`
- RAM コピー予算、`DS4_COPY_GB`、不足時の警告、コピー失敗時の継続: `src/dsv41/ds4_model.cu:4144-4182,4217-4232`
- optional executable の build 条件: `CMakeLists.txt:797-811`

索引の `strata-engine-dsv41` 節では当該 option が予定リンクとして掲載されています。Release での配布実績は索引の注記どおり、この checkout だけでは判断していません。
