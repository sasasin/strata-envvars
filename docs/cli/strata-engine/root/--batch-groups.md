# `--batch-groups`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に変更表示はなかった。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` エンジン（root） |
| オプション | `--batch-groups G` |
| 別名 | なし |
| 値 | 正の整数、または `auto`。ただし parser は数値を `atoi` で変換し、正整数かどうかを厳密には検証しない |

## 役割

`--batch` の slot を複数 group に分け、layer split の GPU stage 間で別 group を重ねて処理する数を指定する。group 数が1以下ならこの pipelined group 経路には入らない。利用には `--batch`、`--serve`、複数 GPU にまたがる layer split が必要になる（`src/program/generate.cpp:780-791, 1034-1041, 6115-6121, 11364`）。

## 使い方

```sh
strata --model model.gguf --serve --batch 8 --layer-split 12,24 --batch-groups 2
```

ここでは8 slotを2 group（各4 slot）に分ける。グループ数を自動選択させる例:

```sh
strata --model model.gguf --serve --batch 8 --layer-split 12,24 --batch-groups auto
```

`--batch` の slot 数は実行時に VRAM などで減る場合があるため、最終的な group 数はその後の再評価と補正に従う（`src/program/generate.cpp:6101-6112, 6160-6175`）。

## 値と既定値

- 引数 parser は `auto` を特別扱いし、それ以外は `std::atoi` で整数化する。値がない場合は stderr に `--batch-groups needs a value` を出して終了コード2で終了する。`auto` 以外の文字列について数値形式・正数範囲を parser で拒否する処理はない（`src/program/generate.cpp:3005-3007, 3199-3204`; SYCL: `sycl/src/program/generate.cpp:1780-1782, 1935-1938`）。
- CUDA/HIP 系では、未指定時に `--batch` が2以上で layer split があると `auto` 相当となる。`auto` は slot 数を割り切り、stage 数（CUDA0を含む）を超えない最大の group 数を選ぶ。`--batch-groups 1` は明示的に直列 group を指定する（`include/strata/program/batch_groups.hpp:83-107`; `src/program/generate.cpp:6024-6045, 6131-6154`）。
- SYCL 系では未指定値は0、明示 `auto` は内部値-1。通常の `auto` は layer split がある場合に上記と同様に最大の割り切れる group 数を選ぶ。一方、未指定時に限り、Arc B-series 2枚の layer split で batch slot が8以上かつ偶数なら既定2 groupとなる。`STRATA_BATCH_GROUPS_AUTO` が設定され、`atoi` の結果が0ならこの特例を抑止する。明示 `--batch-groups 1` も特例を使わない（`sycl/src/program/generate.cpp:630-634, 1935-1938, 4184-4203`）。
- 不正文字列や0は厳密な validation error にはならず、`atoi` の結果が0となる場合は group 数0のまま保持される。負数も1以下として pipeline 条件を満たさない。これらを意図した使用方法としては記述されていない（`src/program/generate.cpp:3199-3204, 6155-6159, 11364`; SYCL: `sycl/src/program/generate.cpp:1935-1938, 4205-4209, 9473-9476`）。

## 実行時の動作

指定数が2以上なら、engine は layer split の stage 数と batch slot 数を照合する。layer split がない、または slot 数を group 数で割り切れない場合は stderr に warning を出し、1 group に補正する。slot session の確保後に slot 数が減って割り切れなくなった場合も1 groupに戻す（`src/program/generate.cpp:6155-6159, 6160-6175`; SYCL: `sycl/src/program/generate.cpp:4205-4209, 4210-4272`）。

pipeline 経路では各 group が `--batch / group数` slotを持ち、group を stage 間で順に進める。起動時の情報行には `batch_groups=<解決後の数>` が含まれ、実行完了時には group 数・group あたり slot 数・処理行数などを stderr に出す（`src/program/generate.cpp:11364, 12286, 13012-13017, 13470-13475`; SYCL: `sycl/src/program/generate.cpp:8911, 9473-9485, 9578-9581`）。

CUDA/HIP 系の暗黙 `auto` は、`--adapt-async 1` のため、または一部の2枚 NVIDIA 構成で `STRATA_BATCH_GROUPS_NV_SERIAL` / `STRATA_DEFAULTS=026` が直列動作を指定するため、1 groupになることがある。`--batch-mtp` は通常の暗黙 pipeline 既定を1 groupにはせず、group pipeline が選ばれる場合は batch MTP draft が無効になることがあり、stderr warning で理由を案内する。明示した数値または `auto` はこれらの暗黙既定より優先される（`include/strata/program/batch_groups.hpp:48-70, 73-80, 92-115`; `src/program/generate.cpp:6037-6045, 6055-6071, 13012-13028`）。

## 適用条件と副作用

- batch decode は `--serve`、2 slot以上、各 layer stage がそれぞれ別 GPU にあることを要求する。満たさないと `--batch` 自体が warning 付きで無効化され、group pipeline も実行されない（`src/program/generate.cpp:6115-6129`; SYCL: `sycl/src/program/generate.cpp:4171-4182`）。
- group pipeline は GPU stage 間に複数 batch group の処理を重ねる。これは実行経路と VRAM 配分に影響する。batch slot ごとに session が確保され、その VRAM は expert cache が使える容量を減らす（`src/program/generate.cpp:6160-6175`; SYCL: `sycl/src/program/generate.cpp:4210-4275`）。
- `--batch-mtp` は通常の group pipeline と同時には slot draft を行わず、draft 用 VRAM を保持したまま使われない場合がある。直列 batch windows で batch MTP を使う場合は `--batch-groups 1` が案内されている（`src/program/generate.cpp:6055-6071, 13026-13028`）。
- group pipeline と `--adapt-async 1` は併用時の解決動作が異なる。pipeline の adaptive tier は通常は動かず、`STRATA_PIPE_ADAPT_EVERY` が正の間隔なら group windows の完了を待って適応処理を実行する（`include/strata/program/batch_groups.hpp:13-15, 43-45`; `src/program/generate.cpp:9064-9069, 13223-13243`）。
- 本文は source checkout の CUDA/HIP 系 `src/program/generate.cpp` と SYCL 系 `sycl/src/program/generate.cpp` を調査した。各 backend の実機動作や性能差は実行・測定していない。

## 出力とエラー

数値が `auto` 以外でも parser による書式エラーは確認できない。指定 group 数が layer split を要求する条件を満たさない場合は `strata generate: WARNING: --batch-groups ... needs a layer split and to divide --batch ...; one group` を stderr に出して1に戻す（`src/program/generate.cpp:6155-6159`; SYCL: `sycl/src/program/generate.cpp:4205-4209`）。

`--batch` の条件を満たさない場合は別の warning により batch 自体が無効になる。slot session が各 GPU に2つ以上確保できない場合も batch が無効になる（`src/program/generate.cpp:6115-6121, 6160-6175`; SYCL: `sycl/src/program/generate.cpp:4171-4182, 4263-4275`）。

## 根拠

- CLI help と option parser、内部初期値: `src/program/generate.cpp:780-791, 1034-1041, 3199-3205`; SYCL: `sycl/src/program/generate.cpp:630-635, 840-844, 1935-1939`。
- group 数の自動解決と暗黙既定: `include/strata/program/batch_groups.hpp:83-115`; `src/program/generate.cpp:6024-6045, 6131-6159`。
- SYCL Arc B-series の既定と環境変数: `sycl/src/program/generate.cpp:4184-4209`。
- batch 適用条件、slot 調整、pipeline 実行と出力: `src/program/generate.cpp:6115-6129, 6160-6175, 11364, 12286, 13012-13028, 13470-13475`; SYCL: `sycl/src/program/generate.cpp:4171-4275, 8911, 9473-9485, 9578-9581`。
- 適応処理との相互作用: `src/program/generate.cpp:9064-9069, 13223-13243`; `include/strata/program/batch_groups.hpp:13-15, 43-45`。
