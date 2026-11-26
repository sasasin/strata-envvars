# `--embd-gguf`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root 引数） |
| オプション | `--embd-gguf` |
| 別名 | なし |
| 値 | token embedding を含む GGUF ファイルのパス |

## 役割

native（IQ）pack で使う token embedding を、`--native` が指す元モデルの shard からではなく、指定した GGUF から読み込みます。`--embd-gguf` がない場合は `--native` の model shards を embedding の入力にも使います。このオプションは埋め込みを別ファイルに分けた構成向けです。

## 使い方

```sh
# native pack と元モデルを指定し、分離して用意した embedding GGUF を使う
strata --pack /models/model.strata --native /models/model-00001-of-00002.gguf \
  --embd-gguf /models/token-embd-bf16.gguf --spec 2 --prefill 128
```

native pack では `--native SHARD1`、`--spec T`（T >= 2）、および `--prefill CHUNK` が必要です。これらの条件は pack の種類や token 入力にも関係します（`engine/src/program/generate.cpp:5782-5787`、`engine/sycl/src/program/generate.cpp:3047-3052`）。

## 値と既定値

- 値は parser が次の argv 要素から受け取るパス文字列です。数値範囲や拡張子の parser validation はありません。値が欠けると `--embd-gguf needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3847,3928`）。
- 同じオプションを複数回指定すると、parser は単一の文字列へ順に代入するため最後の値が残ります（`engine/src/program/generate.cpp:3928`）。空文字列を渡した場合も `.empty()` 判定により `--native` の shard 群を使います（`engine/src/program/generate.cpp:5790-5791`）。
- 省略時は `--native` の shard 群です。値を指定した場合は、その値だけを embedding ローダーへ渡します（`engine/src/program/generate.cpp:5790-5791`）。

## 実行時の動作

parser は値を `Options::embd_gguf` に保存します（`engine/src/program/generate.cpp:815-816,3928`）。native pack と判定された場合に限り、エンジンはこのパス（未指定なら `--native` の shard 群）から token embedding を読み込み、共有 embedding として設定します。読み込みに成功すると stderr に tensor 型、サイズ、配置、読み込み時間を出します（`engine/src/program/generate.cpp:5445,5781-5802`）。

ローダーは GGUF 内の `token_embd.weight` を探し、モデルの embedding 次元・語彙数と形状が一致すること、ビルド側に GPU dequantizer がある型であること、埋め込み次元が 256 の倍数であること、tensor payload が切り詰められていないことを検証します。`strata-embd` architecture のファイルではその単一 tensor を検査し、それ以外はエンジンが扱う architecture として確認します（CUDA/HIP: `engine/src/core/native_head.cpp:516-540`、SYCL: `engine/sycl/src/core/native_head.cpp:171-197`）。BF16 の checkpoint embedding を GGUF 化する補助スクリプトとして `terminal/tools/embd_bf16_pack.py:1-11` が案内されています。

読み込んだ table は token ID に対応する行を gather/dequantize して使われます（`engine/src/core/native_head.cpp:629-635`）。native pack の token embedding 入力となり、たとえば MTP の embedding 分岐でも共有 table があればそこから gather します（`engine/src/core/mtp.cpp:1201-1211`）。指定パスは session model fingerprint の入力にも登録されます（`engine/src/program/generate.cpp:13970-13980`）。

## 適用条件と副作用

- オプション自体は parser に受理されますが、embedding を読み込む処理は native pack の場合にだけ実行されます。通常の非-native pack ではこの値による embedding 差し替えは行われません（`engine/src/program/generate.cpp:5445,5781-5791`）。
- CUDA 実装では通常 mapped host memory に table を置きます。`STRATA_EMBED_VRAM=1` のときは、table サイズに加えて 512 MiB を超える空き VRAM があり、確保・転送に成功した場合だけ VRAM 配置を選びます。条件を満たさない場合は mapped host memory に戻ります。pin/alias できない場合にも VRAM へ fallback する経路があります（`engine/src/core/native_head.cpp:542-568,570-617`）。
- SYCL 実装には `STRATA_EMBED_VRAM` による明示的な配置分岐はなく、host allocation に失敗した場合に VRAM へ fallback します（`engine/sycl/src/core/native_head.cpp:197-242`）。
- GGUF の open・形式・tensor 検証に失敗すると、native pack の起動処理はエラーを stderr に出して終了コード 1 で終了します。native pack の前提条件を満たさない場合は説明を stderr に出して終了コード 2 です（`engine/src/program/generate.cpp:5782-5793`）。parser が知らない引数は `unknown argument` と usage を stderr に出し、終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274`）。

## 出力とエラー

成功時は `strata generate: native pack: ... token embedding ...` の診断を stderr に出します。CUDA/HIP では配置が `in VRAM` または `in mapped host memory` として出ます（`engine/src/program/generate.cpp:5796-5802`）。SYCL では `in mapped host memory` と表示されますが、host allocation 失敗後に VRAM fallback した場合はローダー側がその旨を別途 stderr に出します（`engine/sycl/src/program/generate.cpp:3061-3065`、`engine/sycl/src/core/native_head.cpp:235-242`）。

tensor がない、形状・型が不適合、payload が不足、GGUF を開けない、または必要な host/device memory を確保できない場合はローダーエラーを stderr に出し、native pack の読み込み経路から終了コード 1 で戻ります（CUDA/HIP: `engine/src/core/native_head.cpp:520-539,570-625` と `engine/src/program/generate.cpp:5790-5793`、SYCL: `engine/sycl/src/core/native_head.cpp:174-197,208-238,277-280` と `engine/sycl/src/program/generate.cpp:3055-3058`）。

## 根拠

- `engine/src/program/generate.cpp:815-816,1262-1265,3926-3929` — 値の保持、help 表示、parser 登録。
- `engine/src/program/generate.cpp:3844-3847,4268-4274` — 値欠落時と未知引数の処理。
- `engine/src/program/generate.cpp:5445,5781-5802` — native pack 条件、入力パス選択、ローダー呼び出し、成功時診断。
- `engine/src/core/native_head.cpp:516-540,542-625` — GGUF/tensor validation、CUDA/HIP memory placement と失敗経路。
- `engine/sycl/src/program/generate.cpp:499-500,851-853,1965-1968,2810,3046-3065`、`engine/sycl/src/core/native_head.cpp:171-197,208-280` — SYCL 側の parser、適用条件、読み込みと配置。
- `engine/src/core/mtp.cpp:1201-1211` — 読み込んだ embedding table の使用例。
- `engine/src/program/generate.cpp:13970-13980` — session fingerprint への入力登録。
- `terminal/tools/embd_bf16_pack.py:1-11` — 分離 embedding GGUF の生成例と用途の説明（補助資料）。
