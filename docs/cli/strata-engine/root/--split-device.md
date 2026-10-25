# `--split-device`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--split-device` |
| 別名 | なし |
| 値 | 後段 stage の可視 GPU 番号をカンマ区切りで指定（例: `1,2`）。 |

## 役割

`--serve` の layer split で、先頭 stage が使う CUDA0 に続く各 stage の GPU を指定します。stage は `--layer-split` の各境界から作られます。後段 stage はそれぞれ自身の GPU 上に重み・session・expert cache・verify window などを持ち、最後の stage は head も持ちます。GPU 番号はプロセスから見えるデバイス番号です。

## 使い方

```sh
strata --serve --layer-split 24,36 --split-device 1,2
```

この例では stage 0 が CUDA0、境界 24 からの stage が CUDA1、境界 36 からの stage が CUDA2 を使います。実際に起動するにはモデル等の通常の engine 引数も指定してください。

## 値と既定値

- 値は空でない十進整数のカンマ区切りリストです。空要素や数字以外を含む値は拒否されます。負数や符号付き表記もこの形式には合いません。
- `--split-device` を省略すると、可視 GPU 番号 1 から順に後段 stage 用として割り当てます。明示的な `--layer-split K` が一つだけで、後段用 GPU が自動割当てされなかった場合は CUDA0 が選ばれ、同じ GPU 上の二段構成になります。
- 通常の複数 GPU 構成では、指定する番号は 1 以上かつ可視 GPU 数未満で、各番号は重複できません。明示値 `0` は境界が一つだけの構成でのみ許され、同一 GPU 上の stage として扱われます。`--layer-split auto` では `0` はこの例外に該当しません。
- `--split-device` の値は `--layer-split` がある場合に検証されます。`--layer-split` がなければ保存された値は split 構成に使われません。
- 同じオプションを複数回書いたときは parser の代入で後の値が残ります。重複指定自体を拒否する処理はありません。

## 実行時の動作

オプション parser は値を文字列として保存し、layer split の初期化時に `--layer-split` とともに整数リストへ変換します。layer split は `--serve` が必須です。明示的な境界リストでは境界数と GPU 数が一致し、境界は 2 以上で昇順でなければなりません。`--layer-split auto` では境界数が後段 GPU 数から決まります。

有効な構成では `split_devs` の各番号が後段 `GpuStage` の `dev` に設定されます。実行時にはそのデバイス上で stage の重みを読み込み、stream 等を作成します。GPU 間の stage hand-off 用に mapped pinned host memory も確保します。よって、このオプションは GPU 配置を指定するもので、メモリ不足や GPU 初期化失敗を回避する保証ではありません。

`--split-skip-if-fits` は `--layer-split auto` と併用したときだけ判定されます。プロファイルがない・読めない場合や remote expert cache 使用時は split を維持します。CUDA0 に profiled expert pair、session、drafter/head、reserve を含めて収まると判定した場合、split 設定をクリアして CUDA0 のみで実行します（`src/program/generate.cpp:4190-4235`）。

## 適用条件と副作用

- `--layer-split` と `--serve` が必要です。`--layer-split` がなければ `--split-device` 単独では stage を作りません。
- `STRATA_PRIMARY_DEVICE` が 0 以外のとき layer split は拒否されます。現行実装の layer split は先頭 stage を device 0 とする前提です。
- `--split-device 0` の同一 GPU 二段構成では、conversation parking（`--conversation-cache-mib`、`--conversation-cache-slots`、`--prompt-cache` がすべて有効な条件）は未対応で、該当時は起動エラーになります。
- GPU の stage 配置に伴い、後段 GPU ごとにメモリ確保、重みロード、CUDA stream/event 作成が発生します。mapped hand-off 領域の確保失敗も起動を失敗させます。

## 出力とエラー

- 値が欠落すると `--split-device needs a value` を stderr に出して終了コード 2 です（共通 `next()` 処理）。
- 不正な整数リスト、stage 数との不整合、範囲外・重複 GPU、または `--serve` なし等は `--layer-split ... needs --serve ...` の診断を stderr に出して終了コード 2 です。
- 同一 GPU split と conversation parking の組合せ、または非ゼロの `STRATA_PRIMARY_DEVICE` との組合せも stderr の診断後、終了コード 2 です。
- 後段 GPU の事前確認・CUDA リソース確保・stage 重みロードに失敗した場合は `strata generate:` のエラーを stderr に出し、該当する初期化経路で 1 を返します。
- 起動成功時は使用する CUDA 番号と layer split を stderr に記録します。`--split-skip-if-fits` で単一 GPU に切り替えた場合も、その判定を stderr に記録します。

## 根拠

- parser の値保存と `Options` の初期値: `src/program/generate.cpp:710-719`, `src/program/generate.cpp:2633-2635`
- 共通値取得処理（値欠落時の終了コード）: `src/program/generate.cpp:2416-2421`
- CSV 整数リスト、既定 GPU、stage 条件・validation、parking と `STRATA_PRIMARY_DEVICE` の拒否: `src/program/generate.cpp:2981-3037`
- 後段 stage への device 設定とリソース確保: `src/program/generate.cpp:4303-4365`
- split の説明、stage hand-off、同一 GPU 構成の実行動作: `src/program/generate.cpp:2970-2976`, `src/program/generate.cpp:8977-9029`
- `--split-skip-if-fits` の判定: `src/program/generate.cpp:4190-4235`
- 利用者向けの layer split 概要: `docs/MULTI_GPU.md:179-181`（ソース実装を優先して記述）。

## 調査範囲

指定 revision の source checkout の parser と使用箇所を調べました。同一 revision の既存 CLI `--help` や Release 配布バイナリは実行・確認していません。GPU を使った起動検証、build、テストも行っていないため、実機・backend ごとの runtime 成否は確認対象外です。
