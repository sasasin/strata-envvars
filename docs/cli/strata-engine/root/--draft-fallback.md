# `strata --draft-fallback`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（root parser。通常実行と `--serve` の両方） |
| オプション | `--draft-fallback` |
| 別名 | なし |
| 値 | `mtp` または `none` |

## 役割

`--draft dflash2` を選んだとき、DFlash2 が起動できない場合に MTP drafter を使える状態にするかを指定します。`mtp` は MTP layer もロードしてfallbackとして残し、`none` は MTP layer をロードせず DFlash2 だけで実行します。省略時も `none` と同じ扱いです。MTP layer を保持する設定は実行開始時に決まり、各生成ラウンドごとに切り替わる設定ではありません（`engine/src/program/generate.cpp:1182-1188,6466-6477`）。

## 使い方

```sh
# DFlash2 が起動できない場合に MTP へ切り替える。MTP ディレクトリには draft_vocab.bin が必要。
strata --pack TARGET.pack --native MODEL.gguf --mtp MTP_DIR --draft dflash2 --draft-model DFLASH2.pack --draft-fallback mtp --spec 4 --tokens 1,2

# MTP layer をロードせず、DFlash2 の起動失敗をエラーにする。語彙ファイルは別途指定できる。
strata --pack TARGET.pack --native MODEL.gguf --draft dflash2 --draft-model DFLASH2.pack --draft-fallback none --mtp-draft-vocab VOCAB.bin --spec 4 --tokens 1,2
```

## 値と既定値

- `mtp`: MTP layer をロードし、DFlash2 が利用できない場合は MTP で生成します。通常は `--mtp DIR` が必要です。`--mtp-draft-vocab FILE` は DFlash2 の draft vocabulary の場所を指定しますが、MTP layer 自体をロードする指定の代わりにはなりません（`engine/src/program/generate.cpp:6470-6471,8193-8203`）。
- `none`: DFlash2 専用にします。MTP layer のロードは省略されますが、DFlash2 用 draft vocabulary は必要です。`--mtp DIR` がある場合は既定の `<DIR>/draft_vocab.bin` の解決元として使われ、`--mtp-draft-vocab FILE` で個別指定もできます（`engine/src/program/generate.cpp:6470-6502`）。
- 省略時は内部値が空文字列のままで、`--draft dflash2` の通常経路では `mtp` 以外を `none` として扱います（`engine/src/program/generate.cpp:1188,6477`）。
- 値の大文字小文字や別表記は受理されません。値がない場合は `--draft-fallback needs a value`、`mtp` / `none` 以外は `strata generate: --draft-fallback takes mtp or none` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3839-3842,4150-4155`）。
- 有効値を複数回指定した場合、parser は後の値で同じフィールドを置き換えます。重複指定専用のエラー処理はありません（`engine/src/program/generate.cpp:3837-3842,4150-4155`）。

## 実行時の動作

このオプションは `--draft dflash2` と組み合わせた場合に作用します。`mtp` を選ぶと `o.mtp` を保持し、MTP layer をロードしたうえで DFlash2 を起動します。DFlash2 が初期化できなければ MTP に切り替えます（`engine/src/program/generate.cpp:8193-8203,8243-8255,24407-24426,13519-13527`）。したがってfallback用の MTP layer と draft vocabulary のメモリも必要です。

`none` または省略時は、MTP layer のロードを避けるために `o.mtp` をクリアし、`df2_solo` を立てます。MTP layer のロード箇所は `o.mtp` が空なら通りません（`engine/src/program/generate.cpp:6477-6502,8172-8194`）。そのため MTP layer の追加ロードを行いませんが、DFlash2 が使えない場合に MTP へ切り替わることもありません。

`--draft mtp` では `--draft-fallback` の値による分岐がなく、MTP drafterを選ぶ動作は変わりません。`--draft auto` は両 drafter を保持するモードで、`--draft-fallback none` を明示すると「`--draft-fallback none is for --draft dflash2`」を stderr に出し、終了コード 2 で終了します。`auto` と `mtp` の組み合わせでは `auto` 自体が両方を保持するため、fallback 指定による別の切替はありません（`engine/src/program/generate.cpp:4140-4144,6473-6475,6477`）。

## 適用条件と副作用

- DFlash2 の通常経路では `--draft-model PACK`、`--spec` 2以上、および draft vocabulary が必要です。`none` の場合、`--mtp DIR` または `--mtp-draft-vocab FILE` のどちらかが語彙の解決元として必要ですが、MTP layer をロードする必要はありません（`engine/src/program/generate.cpp:6477-6502`）。
- `mtp` を選び `--mtp` を省略すると、DFlash2 起動処理は「it needs --mtp (the fallback)」として停止します。通常実行では fallback MTP もロードされず、DFlash2 も使われない経路があります。fallback を意図する場合は MTP directory を指定してください（`engine/src/program/generate.cpp:8193-8203`）。
- DFlash2 のセットアップ失敗時は、`mtp` なら MTP が続行し、`none` なら通常の生成経路・serve 起動経路とも開始をエラーにします（通常実行: `engine/src/program/generate.cpp:8239-8255,24407-24430`、serve: `engine/src/program/generate.cpp:13519-13527`）。DFlash2 が正常に起動した場合は、`none` でも `mtp` でも主 drafter は DFlash2 です。
- 例外として、layer split のGPUメモリ事前判定で DFlash2 が収まらないと判断されたとき、`none` でも `df2_solo` と draft 指定を解除して drafter なしで続行する経路があります。この判定は layer split、離散GPU、`STRATA_SPILL_OFF` 未設定などの条件下です（`engine/src/program/generate.cpp:8148-8169`）。
- DFlash2 がロードされない場合も `none` を選べば常にエラーになるわけではありません。上記の事前判定経路のほか、DFlash2 実装が使えないビルド条件について、すべての分岐をこの調査範囲から確認できませんでした。

## 出力とエラー

引数値の誤りと `--draft auto --draft-fallback none` は終了コード 2 です。`none` で DFlash2 のロード・bind・prepare が失敗した場合、stderr に失敗理由を含むメッセージを出し、通常生成では終了コード 1、serve では開始を中止して終了コード 1 を返します。`mtp` で DFlash2 が起動しない場合は stderr に理由と MTP へ切り替える旨を出して続行します（`engine/src/program/generate.cpp:6473-6480,8240-8255,13519-13527,24412-24430`）。

## 根拠

- `engine/src/program/generate.cpp:1182-1188` — 値の役割、未指定時の意味、per-run 設定であること。
- `engine/src/program/generate.cpp:3837-3842,4150-4155` — 引数取得、受理値、欠落値と不正値の終了処理。
- `engine/src/program/generate.cpp:6470-6502` — `auto` との相互作用、語彙パス解決、MTP layer を外す処理。
- `engine/src/program/generate.cpp:8172-8203,8239-8255` — MTP のロードと通常生成時の DFlash2 起動・fallback。
- `engine/src/program/generate.cpp:8148-8169,24407-24430` — layer split のメモリ不足経路と通常生成時の失敗処理。
- `engine/src/program/generate.cpp:13505-13534` — serve の DFlash2 設定・fallback・起動中止処理。
