# `--draft-model`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--draft-model` |
| 別名 | なし |
| 値 | DFlash2 drafter pack (`PACK`) のファイルパス。省略時の値は空（既定 pack なし） |

## 役割

`--draft-model` は、`--draft dflash2` で使う DFlash2 block drafter の pack を指定します。通常の MTP draft 経路では参照されません。DFlash2 は Qwen3.8-Flash-Next 用の専用 drafter で、対象エンジンの native pack と speculative window が必要です。pack は起動時に読み込まれて GPU 側に展開されます（`engine/src/program/generate.cpp:1184-1186, 8266-8275`）。

## 使い方

```sh
strata --native /models/flash-next.native --draft dflash2 \
  --draft-model /models/flash-next-dflash2.pack --spec 6 \
  --mtp /models/flash-next-mtp
```

この例では `--mtp` ディレクトリの `draft_vocab.bin` を語彙部分集合として使います。通常の CUDA/HIP build で `--draft-fallback` を省略した場合、MTP layer 自体は読み込まず、DFlash2 だけで draft します（`engine/src/program/generate.cpp:1187-1190, 6494-6530`）。

## 値と既定値

- 値は次の引数をそのまま受け取る文字列です。parser は値の形式、拡張子、存在を検証せず、`--draft-model` の繰り返し指定は後の値で上書きします（`engine/src/program/generate.cpp:3842-3847, 4154`）。
- 値を省略すると parser は終了コード `2` で `--draft-model needs a value` を stderr に出します（`engine/src/program/generate.cpp:3844-3846`）。
- pack に既定値はありません。DFlash2 を選んだ場合、空のままでは起動時検査に失敗します。`--draft mtp`（または通常の MTP 経路）では、この値は使用されません（`engine/src/program/generate.cpp:8267-8274`）。
- CUDA/HIP の loader は `DF2P` magic と version 1、pack index と tensor shape を確認します。ファイルが開けない、形式・index・shape が不正、または GPU に収まらない場合は load に失敗します（`engine/src/core/dflash2.cpp:187-196, 225-236`）。Metal 実装も `DF2P` v1 を読み、pack index を処理します（`engine/metal/src/engine/dflash2.inc:131-140, 1046-1056`）。

## 実行時の動作

`--draft dflash2` が選ばれると、engine は pack を開いて index と重みを読み、DFlash2 の GPU/device 側領域へロードします。CUDA/HIP 実装では tensor を device memory に確保し、Q8_0/Q4_0 tensor の変換・転送を行って drafter の stream/buffer を準備します（`engine/src/core/dflash2.cpp:187-196, 236-268`）。Metal 実装では index を読み込んだ後、Metal decode window に pack を読み込ませます（`engine/metal/src/engine/dflash2.inc:1046-1065`）。

`--draft-model` 単独では DFlash2 を有効にしません。DFlash2 を選んだときは、pack に加えて `--spec` が 2 以上で、`--mtp DIR` または `--mtp-draft-vocab FILE` のいずれかが必要です。MTP directory は fallback 用の MTP layer を必ず意味するわけではなく、fallback を無効にした通常経路では `draft_vocab.bin` の場所として使われ、その後 MTP layer の読み込み対象から外されます（`engine/src/program/generate.cpp:6494-6507, 6527-6530`）。

| build / 選択 | この値の扱いと条件 |
| --- | --- |
| CUDA/HIP, `--draft dflash2` | `--draft-model` と native pack が必要です。MTP vocabulary は `--mtp DIR` または `--mtp-draft-vocab FILE` から選びます。既定の fallback は `none` で、DFlash2 が起動できなければ処理を終了します。`--draft-fallback mtp` を指定すると MTP layer も読み込み、DFlash2 の開始・bind・prepare が失敗した場合に MTP へ fallback します（`engine/src/program/generate.cpp:1184-1190, 8266-8326, 24512-24536`）。 |
| CUDA/HIP, `--draft auto` | serve 用の選択です。DFlash2 pack と MTP drafter の両方を用意し、要求ごとに drafter を選ぶ経路です。`--draft-fallback none` は組み合わせられません（`engine/src/program/generate.cpp:1367-1368, 6501-6503`）。 |
| SYCL, `--draft dflash2` | MTP layer は読み込まず、失敗時 fallback もありません。pack と MTP vocabulary、`--spec >= 2` が必要で、複数 GPU、`--batch`、`--pipeline-windows` は拒否されます（`engine/sycl/src/program/generate.cpp:785-788, 2118-2123, 4499-4517, 4557-4568`）。 |

CUDA/HIP では `--draft-cap` によって `--spec` の上限が変わる場合があります。DFlash2 load が失敗した場合、既定の `none` では stderr に理由を出し終了コード `1`、`mtp` fallback では MTP が draft を続けます（`engine/src/program/generate.cpp:8298-8303, 8310-8326`）。Metal build の target は DFlash2 support を定義しており、共通 parser/起動処理から Metal 固有の loader に接続します（`engine/metal/CMakeLists.txt:154-177`, `engine/metal/src/engine/dflash2.inc:1046-1065`）。build ごとの feature 構成は異なるため、ここに挙げた以外の配布 build での可否は確認していません。

## 適用条件と副作用

- CUDA/HIP 共通 parser は `--draft` の値として `mtp`、`dflash2`、`auto` を受け付けます。DFlash2 の起動経路では native pack が必要で、CUDA/HIP は `STRATA_HAVE_DFLASH2` build 条件下で load します（`engine/src/program/generate.cpp:4143-4149, 8266-8274`; build 定義は `engine/cmake/strata_gpu_engine.cmake:6-13`）。
- DFlash2 を使うと GPU/device memory を pack や drafter 用に確保し、ファイルから pack を読みます。解析した範囲では pack 自体を書き換える処理はありません（`engine/src/core/dflash2.cpp:187-196, 236-268`）。
- CUDA/HIP の DFlash2 で `--pipeline-windows` を有効にすると、対応する次 window の draft 経路がないため DFlash2 は停止し、既定 `none` では起動失敗、MTP fallback が有効なら MTP に切り替わります（`engine/src/program/generate.cpp:8268-8273, 8319-8326`）。
- SYCL では `--draft-fallback` は `none` 以外を拒否します（終了コード `2`）。また DFlash2 は一 GPU・一 request のみで、batch、pipeline、layer split を拒否します（`engine/sycl/src/program/generate.cpp:2119-2123, 4557-4560`）。

## 出力とエラー

- 値がない場合は stderr に `--draft-model needs a value` を出し、終了コード `2` です（`engine/src/program/generate.cpp:3844-3846`）。
- DFlash2 選択時に `--draft-model`、`--spec >= 2`、または MTP vocabulary のいずれかが不足すると、要件を stderr に出し、終了コード `2` です（`engine/src/program/generate.cpp:6505-6508`; SYCL: `engine/sycl/src/program/generate.cpp:4504-4508`）。
- pack の open、format、shape、GPU memory 等で load できない場合、CUDA/HIP は `--draft-fallback none` なら理由を stderr に出して終了コード `1`、`mtp` なら理由と fallback を stderr に出して MTP で続行します（`engine/src/program/generate.cpp:8310-8326`）。SYCL は fallback を行わず終了コード `1` です（`engine/sycl/src/program/generate.cpp:4562-4565`）。

## 根拠

- `engine/src/program/generate.cpp:1184-1190` — DFlash2 と `--draft-model` の役割、fallback の既定値。
- `engine/src/program/generate.cpp:3842-3847, 4143-4159` — 値の取得、missing value、`--draft` / fallback parser。
- `engine/src/program/generate.cpp:6494-6530` — vocabulary と fallback 条件、MTP directory の扱い。
- `engine/src/program/generate.cpp:8266-8326, 24512-24536` — native pack 条件、load、failure/fallback、出力経路。
- `engine/src/core/dflash2.cpp:187-268` — CUDA/HIP pack 読込・形式検証・device allocation。
- `engine/metal/src/engine/dflash2.inc:131-140, 1046-1065` — Metal の index 読込と bind。
- `engine/sycl/src/program/generate.cpp:785-788, 2118-2123, 4499-4517, 4557-4568` — SYCL parser と適用条件・失敗経路。
- `engine/cmake/strata_gpu_engine.cmake:6-13`, `engine/metal/CMakeLists.txt:154-177` — CUDA/HIP と Metal の feature build 定義。
