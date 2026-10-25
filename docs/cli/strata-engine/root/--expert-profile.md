# `--expert-profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--expert-profile` |
| 別名 | なし |
| 値 | profile ファイルのパスを1つ取る |

## 役割

MoE expert の順位を記録した `profile.bin` を読み込み、GPU expert cache に起動時点で常駐させる expert を順位順に選びます。profile を渡すと「最初に使われた expert から cache に入れる」方式の代わりに、profile の順で cache を事前充填します。オプションの値は `Options::expert_profile` に保存され、profile 読込後は順位表として cache 配置などにも使われます（`src/program/generate.cpp:583-587, 988-989, 2749, 4414-4456, 6441-6487`）。

## 使い方

通常エンジンの例です。モデルと token 入力は実行するモデルに合わせて指定してください。

```sh
strata --native /path/to/model.gguf --tokens 1,2,3 \
  --expert-profile data/expert-profile.bin --expert-cache auto
```

`--expert-cache auto` は明示しなくても、profile 指定時に `--expert-cache` の既定値 `0` が自動容量扱い `-1` に切り替わります（`src/program/generate.cpp:4421-4424`）。

## 値と既定値

- 値はパス文字列です。parser ではファイル形式やパスの内容を検査せず、そのまま保持します。オプション値を省略すると `--expert-profile needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2416-2420, 2749`）。
- オプション未指定時の値は空文字列で、profile は読み込まれません（`src/program/generate.cpp:583-587, 4414-4417`）。空文字列を値として明示した場合も、空であるため読込はスキップされます。
- 同じオプションを複数回指定したときの重複拒否はありません。parser は指定ごとに同じ文字列変数へ代入するため、最後に処理された値が残ります（`src/program/generate.cpp:2416-2422, 2749`）。
- profile が指定され、`--expert-cache` が省略または `0` の場合は自動容量 `-1` になります。正数指定は cache の slot 数を制限します。profile の順位数を超えて cache slot を設定しても、通常の fill は順位表にある expert を超えて埋めません（`src/program/generate.cpp:4421-4424, 6450-6451, 6473-6487`）。native pack で明示 cache 数が profile の順位数を超える場合は、profile 件数が上限になった旨の警告が出ます（`src/program/generate.cpp:6255-6280`）。

## 実行時の動作

通常 parser は値を `Options::expert_profile` に格納します。model の expert レイアウトが分かった後、`read_expert_profile()` がファイルを読み、layer/expert の順位ペアを `profile` にします。読み込み成功時は stderr にパス、順位数、作成時 slot 数を表示します（`src/program/generate.cpp:2749, 4414-4420, 4455-4456`）。

Profile はバイナリ形式です。現在の reader は `STRP` magic、version 1、model の layer 数と expert 数の一致、順位数が header の slot 数以下であること、全順位ペアの読み込み完了、各 layer/expert index の範囲内を検査します。reader は `(layer, expert)` 順位ペア列を返し、header の slot 数も返します（`src/core/expert_cache.cpp:74-140`）。同じ順位に重複ペアがあることや、ファイル末尾の余剰データは reader の検査項目に含まれていません。

Profile があり、expert cache のデータソースが利用可能な場合、エンジンは profile 順に expert blob を cache に admit して転送します。cache が満杯なら通常はそこで終了し、profile はヒントではなく起動時の常駐順位として働きます。per-layer admission が有効な場合は、満杯の layer の pair を飛ばして他 layer の順位も処理します。fill 後、少なくとも1件埋まった場合は最初の slot を読み戻して検証します（`src/program/generate.cpp:6441-6451, 6464-6487, 6492-6502`）。

他の処理も順位を参照します。profile があると prefill buffer を expert cache から借りられる条件になり、split 自動配置や「split を省略して1 GPUに収まるか」の見積り、pin-by-need の候補選定などに順位が使われます（`src/program/generate.cpp:4190-4224, 4483-4495, 5837-5888`）。`STRATA_PEER_HOT` が有効な peer GPU 構成では、profile の先頭部分の順位が並べ替えられます（`src/program/generate.cpp:4430-4453`）。

## 適用条件と副作用

- `--layer-split` で複数 GPU に layer を分割すると profile が必須です。未指定なら診断を stderr に出し、終了コード `2` になります（`src/program/generate.cpp:3069-3073`）。
- `--expert-cache-remote` の CUDA0 helper cache は、profile、CUDA0 expert cache、および expert pool を必要とします。不足時はエラーを出して終了コード `2` になります（`src/program/generate.cpp:6666-6670`）。`--peer-device` も profile と expert cache が必要で、不足時は終了コード `1` です（`src/program/generate.cpp:6750-6756`）。
- `--cpu-oracle-q8-0` とは併用できず、診断を出して終了コード `2` になります（`src/program/generate.cpp:3407-3409`）。
- speculative verify の実行にも profile で埋めた VRAM expert tier が必要です。確認処理は residency table、cache base、blob サイズが揃わない場合に失敗します（`src/program/generate.cpp:16121-16125`, `src/core/verify.cpp:721-730`）。
- Profile 読込は model の GPU 実行準備中に行われるため、形式・内容のエラーは parser 時点ではなく読込時に判明します。開けない、header が短い、magic/version が不一致、別形状の model 用、順位リストが短い、index が範囲外の場合は理由を stderr に出し、終了コード `1` で処理を中断します（`src/program/generate.cpp:4415-4420`, `src/core/expert_cache.cpp:76-138`）。
- cache fill 中に blob を取得・転送できない場合も pair 番号と理由を stderr に出して終了コード `1` になります（`src/program/generate.cpp:6478-6483`）。GPU VRAM の確保量は `--expert-cache` や空き VRAM 等にも依存します。
- `--native` または `--model` で Qwen3.6-35B-A3B (`qwen35moe`) が検出されると、通常 parser より先に別の `src/qwen35` 実装へ委譲されます。この文書の parser と適用条件は通常 engine 経路を対象とします（`src/program/generate.cpp:2393-2407`）。

## 出力とエラー

成功時は読み込んだ profile の順位数などを stderr に表示し、cache fill 時には充填 slot 数、時間、読み戻し検証結果を表示します（`src/program/generate.cpp:4455-4456, 6498-6502`）。無効な profile や fill 失敗は上記のとおり stderr に診断を出して処理を中止します。profile 自体をこのオプションで書き換える処理はありません。

## 根拠

- Parser と既定値: `src/program/generate.cpp:583-587, 2416-2422, 2749`
- help 表示: `src/program/generate.cpp:988-989`
- profile 読込、cache 既定変更、順位利用: `src/program/generate.cpp:4414-4456, 6441-6502`
- Profile 形式と validation: `src/core/expert_cache.cpp:74-140`
- 組合せ制約と family 分岐: `src/program/generate.cpp:2393-2407, 3044-3073, 3407-3409, 6666-6670, 6750-6756, 16121-16125`; `src/core/verify.cpp:721-730`
- 今回は同一 revision のソースを根拠とし、既存 binary の `--help` は実行していません。Release artifact ごとの挙動は調査していません。
