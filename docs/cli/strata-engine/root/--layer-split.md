# `--layer-split`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | `auto`、または後段 GPU ごとの先頭 layer 番号 `K[,K2...]` |

## 役割

`--serve` で常駐するエンジンの層を GPU 間で分割します。値 `K` は後段 GPU が担当する最初の layer 番号であり、その GPU に割り当てる layer 数ではありません。複数境界を指定すると、CUDA0 が layer 0 から最初の境界の直前までを実行し、各後段 GPU が境界から次の境界の直前までを担当します（`src/program/generate.cpp:710-715, 2969-2972, 5138-5158`）。

## 使い方

```sh
strata --pack /path/to/pack --serve --expert-profile /path/to/profile.bin --layer-split auto
```

固定境界と後段 GPU を指定する例:

```sh
strata --pack /path/to/pack --serve --expert-profile /path/to/profile.bin --layer-split 24,36 --split-device 1,2
```

`--serve` 時は要求ごとに prompt を受け取るため、`--tokens` は省略できます。エンジンの usage は `strata generate --pack DIR --tokens ... [options]` としてこの parser の入口と serve 時の利用を示しています（`src/program/generate.cpp:806-812, 2633-2637, 3168-3178`）。

## 値と既定値

- 省略時は空文字列のままで、layer split を設定しません（`src/program/generate.cpp:710-712`）。
- `auto` は自動配置です。`--serve` が必要で、split に使う GPU と各 stage の expert profile を使って境界を選びます。profile は起動時に `--expert-profile` で指定しなければなりません（`src/program/generate.cpp:2998-3002, 3069-3073, 4462-4482`）。
- 固定値はカンマ区切りの十進整数です。各 `K` は 2 以上、前の値より大きく、モデルの最終 layer 番号より小さい必要があります。各境界は対応する後段 GPU 一台につき一つです（`src/program/generate.cpp:2985-2997, 3015-3020, 5132-5136`）。例の `24,36` は、3 段なら CUDA0 が `0-23`、次の GPU が `24-35`、最後が `36` から末尾までを担当します。
- `--split-device` を省略すると、見えている後続 GPU を順に使います。`--split-device` を明示した場合は、境界ごとに対応する GPU 番号をカンマ区切りで指定します。指定 GPU は重複不可で、通常は 1 以上の可視デバイス番号です。固定境界が一つだけの場合は `--split-device 0` で同一 GPU 内に二段を置けます（`src/program/generate.cpp:3000-3004, 3015-3020`）。
- 同じオプションを複数回指定すると parser は各値を同じフィールドへ代入するため、最後の指定が残ります（`src/program/generate.cpp:2416-2421, 2633-2634`）。値を省略すると `--layer-split needs a value` を stderr に出して終了コード 2 です。

## 実行時の動作

複数 GPU にまたがる場合、CUDA0 と後段 GPU に stage を作り、決定した境界で担当 layer 範囲を割り当てます。後段 stage は自身の GPU 上に重み・session・（最終 stage では）head を用意し、各 GPU で担当 layer の expert cache を使います。起動時には使用 GPU と split 値、各 stage の layer 範囲・cache 概況を stderr に表示します（`src/program/generate.cpp:3143-3146, 4303-4365, 5140-5158, 6598-6608`）。

`auto` の探索は候補配置の decode 窓コストや GPU の空き VRAM、expert profile 等に基づきます。配置できる候補がない場合は診断を出し、より緩い条件で再探索します。それでも配置できなければ終了コード 2 です。自動配置に `--split-skip-if-fits` を併用すると、CUDA0 だけで profile の expert 群・session・drafter・reserve を収容できる場合は split を解除して単一 GPU で続行します（`src/program/generate.cpp:4210-4234, 4462-4482, 5074-5086`）。

`--trim-stage-weights` または `STRATA_STAGE_TRIM` を有効にすると、明示 split では各 GPU が担当範囲の dense weights だけをロードします。`auto` と併用した場合、split 探索後に後段 GPU の該当 weights をロードします。これは既定では有効ではありません（`src/program/generate.cpp:3802-3819, 4306-4333, 5162-5173`）。

## 適用条件と副作用

- split を指定すると `--serve` が必須です。複数 GPU の split では `--expert-profile` も必須です。`auto` で可視 GPU が一台しかない場合は「no split」と stderr に出し、split 指定を解除して続行します（`src/program/generate.cpp:2998-3012, 3069-3073`）。
- `STRATA_PRIMARY_DEVICE` が 0 以外のときは layer split を拒否し、終了コード 2 です（`src/program/generate.cpp:3030-3037`）。
- `--peer-device` とは併用できず、エラーを stderr に出して終了コード 2 です。複数 GPU split は `--gpu-only-full` および `--gpu-stages` とも併用できません（`src/program/generate.cpp:3369-3375, 3386-3392`）。
- `--split-device 0` の同一 GPU 二段で conversation parking が有効な条件（`--conversation-cache-mib > 0`、slots と prompt cache も正数）では拒否され、parking を無効にする案内を出して終了コード 2 です（`src/program/generate.cpp:3003-3008`）。
- `--expert-cache-remote` を複数 GPU split と併用する場合、stage を実行しない追加 GPU が必要です。空き GPU がなければ終了コード 2 です（`src/program/generate.cpp:3128-3141`）。
- split 中の server `SAVE` / `RESTORE` session-file 操作は対応しておらず、その要求に対して stderr と `SERR` 応答を出して拒否します（`src/program/generate.cpp:12064-12077, 12093-12099`）。
- split 値の書式、`--serve`、GPU 数・番号、境界順序の不整合は説明を stderr に出して終了コード 2 です。手動境界がモデル末尾以降の場合も終了コード 2 です（`src/program/generate.cpp:3015-3027, 5132-5136`）。

## 根拠

- parser の値受け取りと option 宣言: `src/program/generate.cpp:710-715, 2416-2421, 2633-2635`
- 値解析、GPU の割当、validation、`auto` の一台時 fallback: `src/program/generate.cpp:2981-3028`
- profile 要件、環境変数との適用制限、GPU stage 作成: `src/program/generate.cpp:3030-3037, 3069-3073, 4303-4365`
- 自動配置と失敗経路: `src/program/generate.cpp:4462-4482, 5074-5086, 5132-5136`
- 関連 option との相互作用、session file の拒否: `src/program/generate.cpp:3003-3008, 3128-3141, 3369-3392, 12064-12099`
- 索引上の scope と配置: `docs/cli/README.md:1128-1135, 1195-1196`

この文書は通常の `strata-engine/root` parser を対象にしています。同じ名前の DSV41 専用 parser、Terminal CLI、setup.py の option は別 scope です。性能値や GPU/backend ごとの実測適性はこの調査では測定していません。
