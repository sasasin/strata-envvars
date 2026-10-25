# `--draft`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--draft` |
| 別名 | なし |
| 値 | `mtp` または `dflash2` |

## 役割

`--spec` による speculative decoding で、次の候補トークンを作る drafter を選びます。`mtp` はモデルの MTP 層、`dflash2` は Qwen3.8-Flash-Next 用 DFlash2 block drafter です。未指定時も MTP が使われます。DFlash2 は MTP を fallback として残します。 (`src/program/generate.cpp:792-796`, `src/program/generate.cpp:949-950`)

## 使い方

```sh
strata generate --pack /path/to/native-pack --tokens '1,2,3' \
  --mtp /path/to/mtp --spec 4 --draft dflash2 --draft-model /path/to/dflash2-pack
```

`--draft dflash2` を使うには、MTP と speculative window を指定し、`--draft-model` に `tools/dflash2_pack.py` で作成した pack を渡します。実際の利用には対応する Flash-Next モデルと CUDA または HIP build が必要です。 (`src/program/generate.cpp:949-950`, `src/program/generate.cpp:5474-5479`)

## 値と既定値

- 値は大文字小文字を区別する `mtp` または `dflash2` です。それ以外は `strata generate: --draft takes mtp or dflash2` を stderr に出して終了コード 2 で終了します。 (`src/program/generate.cpp:2692-2697`)
- 値を省略すると parser は「値が必要」と stderr に出して終了コード 2 で終了します。 (`src/program/generate.cpp:2418-2420`)
- 既定値は空文字ですが、DFlash2 が有効にならない限り MTP の drafter が使われます。help 表示も `default mtp` としています。`--draft mtp` はこの既定動作を明示します。 (`src/program/generate.cpp:794`, `src/program/generate.cpp:949`)
- 同じオプションを複数指定した場合、parser はその都度値を代入するため最後の値が残ります。 (`src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2692-2697`)

## 実行時の動作

`--draft dflash2` の選択を実際に有効化するのは、MTP drafter の初期化箇所です。そのため `--mtp` が空なら DFlash2 は有効にならず、MTP fallback が必要という理由を stderr に出します。また、native pack がない場合、複数 GPU・`--batch`・`--serve` を使う場合、または `--draft-model` が空の場合も無効化理由を stderr に出し MTP に戻ります。 (`src/program/generate.cpp:5474-5479`, `src/program/generate.cpp:5515-5517`)

条件を満たす場合、engine は `--draft-model` の pack を読み込みます。pack が開けない、DF2P v1 形式でない、または pack の形状が Flash-Next drafter と合わない場合など、読み込み失敗は理由を stderr に出して MTP に戻ります。読み込んだ pack は GPU VRAM に配置されます。 (`src/core/dflash2.cpp:122-131`, `src/core/dflash2.cpp:167-177`, `src/program/generate.cpp:5480-5482`, `src/program/generate.cpp:5510-5516`)

DFlash2 が選ばれても、verifier に taps がない場合や bind / prepare が失敗した場合は stderr に理由を出し、MTP に切り替わります。有効化されると stderr に DFlash2 の pack パスと graph capture 時間を表示します。 (`src/program/generate.cpp:16148-16165`)

MTP / DFlash2 のどちらも speculative loop の候補生成にだけ使われます。DFlash2 の候補は verifier の tap を使って生成されます。`--draft-conf` を正の値にすると、selector の候補確率の積が指定値を下回る位置で DFlash2 の verify window を切り詰めます。 (`src/program/generate.cpp:16494-16503`, `src/program/generate.cpp:16544-16549`)

## 適用条件と副作用

- DFlash2 実装は CMake の CUDA または HIP GPU build で定義されます。CMake のコメントでは Metal / SYCL build はこの実装なしとされています。その build では parser が `dflash2` の値自体を受理しても、DFlash2 有効化コードは compile 条件から外れ、MTP が使われます。 (`CMakeLists.txt:336-340`, `src/program/generate.cpp:5474-5475`)
- DFlash2 の model pack 読み込みや bind は VRAM を使います。読み込み失敗時の診断には約 1.2 GiB の必要量と VRAM を空けるための案内が表示されます。 (`src/program/generate.cpp:5510-5513`, `src/program/generate.cpp:16153-16163`)
- DFlash2 の window 幅は既定では GPU によって上限が加わります。Strix Halo / iGPU は 5、CUDA compute capability major 12 は 6、それ以外は上限なし（指定された `--spec` のまま）です。`--draft-cap` を正数で指定すると自動値に代えてその値を使い、`--spec` が上限を超える場合は `o.spec` を上限に補正して stderr に通知します。 (`include/strata/core/draft_cap.hpp:8-15`, `src/program/generate.cpp:5498-5502`)
- CUDA の総 VRAM が 13 GiB 未満で `--draft-cap` 未指定の場合、MTP の方が速い測定が多かった旨を stderr に警告しますが、選択を強制変更しません。これはソース内の測定メモであり、性能推奨をこの文書で一般化するものではありません。 (`include/strata/core/draft_cap.hpp:18-19`, `src/program/generate.cpp:5504-5507`)

## 出力とエラー

値不正・値欠落は終了コード 2 です。DFlash2 の適用条件を満たさない、pack の読み込みに失敗する、verifier taps がない、bind / prepare に失敗するといった初期化段階の失敗は stderr に理由を出し、処理全体をただちに失敗させず MTP に fallback します。 (`src/program/generate.cpp:2418-2420`, `src/program/generate.cpp:2692-2697`, `src/program/generate.cpp:5510-5517`, `src/program/generate.cpp:16148-16165`)

## 根拠

- parser、許容値、既定値の help: `src/program/generate.cpp:792-796`, `src/program/generate.cpp:949-952`, `src/program/generate.cpp:2418-2420`, `src/program/generate.cpp:2692-2701`
- DFlash2 の適用条件、window cap、fallback: `src/program/generate.cpp:5474-5518`, `src/program/generate.cpp:16148-16165`
- pack 形式・shape と VRAM load: `src/core/dflash2.cpp:122-177`
- DFlash2 build 条件: `CMakeLists.txt:336-340`
- GPU ごとの既定 cap: `include/strata/core/draft_cap.hpp:8-19`
- draft 候補生成と `--draft-conf` による window 選択: `src/program/generate.cpp:16494-16512`, `src/program/generate.cpp:16538-16550`

調査範囲は指定 commit のソースです。対応 GPU での実行、配布済み Release artifact、性能比較は確認していません。
