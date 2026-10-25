# `--draft-model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` エンジン（`generate` 引数 parser） |
| オプション | `--draft-model` |
| 別名 | なし |
| 値 | DFlash2 の `DF2P v1` pack ファイルのパス |

## 役割

`--draft dflash2` を選ぶときに使う DFlash2 block drafter の pack ファイルを指定します。DFlash2 は対象モデルの中間状態から次の候補 token を作り、検証には通常の verifier を使います。MTP drafter は fallback としてロードされたままです。`--draft-model` 単独では drafter を切り替えません。

## 使い方

`pack`、native model、MTP model、token 入力など通常のエンジン引数も必要です。例:

```sh
strata generate --pack pack/full --native models/target.gguf --mtp models/mtp \
  --tokens "1,2,3" --draft dflash2 --draft-model models/dflash2.df2p
```

これは構文例です。`models/dflash2.df2p` は `tools/dflash2_pack.py` で作られた pack を指す想定で、ここでは pack の入手・作成や実行結果を検証していません。

## 値と既定値

- 値は次の argv 要素をそのまま文字列として受け取ります。値の形式やファイル存在は parser 段階では検査しません。値を省略すると `needs a value` を stderr に出し、終了コード 2 で終了します。
- 既定値は空文字列です。`--draft dflash2` を選び、パスが空なら DFlash2 を有効化せず MTP に戻ります。`--draft` 自体を省略した場合も MTP 経路です。
- 複数回指定した場合は引数ループで後の値が `draft_model` に代入されます。
- `--draft` の値は `mtp` または `dflash2` のみです。別値は parser がエラーを出して終了コード 2 で終了します。

## 実行時の動作

DFlash2 は CUDA または HIP でコンパイルしたエンジンに含まれます。`--draft dflash2`、MTP が有効（`--mtp` と `--spec` が必要）、native pack 使用、単一 GPU、非 batch、非 serve の CLI 実行、空でない `--draft-model` が揃ったときに、指定パスを GPU 0 向けに読み込みます。MTP は DFlash2 と並行して fallback としてロードされます。

ロード処理はファイルをバイナリで開き、`DF2P` magic と version 1、pack index、Flash-Next drafter に合う shape を確認し、tensor データを GPU に確保・転送します。DFlash2 の verifier tap が利用できない場合、head/vocabulary の bind に失敗した場合、または graph 準備に失敗した場合も DFlash2 を止めて MTP に戻ります。成功時は stderr に DFlash2 が有効になった旨を出力し、生成終了時に round あたりの時間と VRAM 使用量を stdout に出します。

## 適用条件と副作用

- CMake では CUDA または HIP 有効時に `STRATA_HAVE_DFLASH2` を定義します。Metal / SYCL build には DFlash2 実装がなく、このオプションで DFlash2 は有効になりません。
- `--draft-model` が空、MTP がない、native pack でない、複数 GPU・batch・serve のいずれか、の条件では stderr に理由を出して MTP を使います。これらは拒否終了ではありません。
- 読み込み時にパスのファイルを開き、pack の tensor を GPU VRAM に確保・転送します。shape 不一致、切り詰められた index/data、開けないファイル、VRAM 不足等のロード失敗は stderr に理由を出して MTP へ fallback します。DFlash2 として必要な VRAM はエラー案内で約 1.2 GiB と説明されますが、実使用量は pack と実行環境によります。
- pack が読み込まれた後、カード判定により `--spec` の最大窓幅が縮められることがあります。`--draft-cap N` が正ならその値を cap とし、そうでなければカード別 cap を使います。cap を適用したときは stderr に通知します。
- DFlash2 自体は Flash-Next 向けです。別 family や backend、Release 配布物での利用可能性はこの調査では実機確認していません。

## 出力とエラー

pack を開けない場合は `dflash2: cannot open <path>`、DF2P magic/version や shape が合わない場合は各理由が stderr に出ます。これらの DFlash2 初期化失敗は通常 MTP に fallback するため、CLI 全体の即時エラーとは限りません。GPU での生成や失敗経路は実行しておらず、記載はソース読解に基づきます。

## 根拠

- parser、値の格納、`--draft` の受理値と usage: `src/program/generate.cpp:949-950`, `src/program/generate.cpp:2418-2420`, `src/program/generate.cpp:2692-2701`。
- MTP 条件と DFlash2 の適用条件、pack load、カード別窓幅 cap、fallback 診断: `src/program/generate.cpp:5455-5479`, `src/program/generate.cpp:5480-5517`。
- verifier tap、bind、graph prepare の失敗時 fallback と成功メッセージ: `src/program/generate.cpp:16148-16165`。
- DFlash2 round での draft 呼び出し、confidence による窓選択、実行統計: `src/program/generate.cpp:16494-16503`, `src/program/generate.cpp:16544-16549`, `src/program/generate.cpp:16832-16838`。
- pack の open、magic/version、shape 検査、VRAM 確保・データ転送: `src/core/dflash2.cpp:122-172`, `src/core/dflash2.cpp:179-193`。
- DFlash2 の pack 形式・drafter 概要: `include/strata/core/dflash2.hpp:1-8`, `include/strata/core/dflash2.hpp:33-47`。
- 対応 build backend: `CMakeLists.txt:336-340`。

