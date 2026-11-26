# `--split-skip-if-fits`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`generate` 実行経路） |
| オプション | `--split-skip-if-fits` |
| 別名 | なし |
| 値 | 取らない真偽フラグ |

## 役割

`--layer-split auto` で複数 GPU への層分割が選ばれた場合に、先頭 GPU だけで全 expert profile の expert pair と全層分の session（KV）、drafter、reserve 等を確保できるか起動時に見積もります。収まる場合は split を取り消して単一 GPU で実行します。既定では無効です。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --serve \
  --layer-split auto --split-skip-if-fits
```

例では `--serve` を有効にし、auto split の開始前に単一 GPU で収まる場合の切替を許可します。

## 値と既定値

- 値や別名はありません。指定すると parser が `split_skip_if_fits` を `true` にします。初期値は `false` です。
- このフラグ自体に追加の値検証はありません。split の構文・条件検証は `--layer-split` 側で行われ、層分割には `--serve` が必要です。
- 同じフラグを複数回指定しても同じ真偽値を設定します。

## 実行時の動作

- 効果があるのは、複数 GPU の `--layer-split auto` が成立して `multi_gpu` が真のときだけです。単一 GPU で auto split が解除された場合や、明示的な層境界で split する場合には、この判定分岐に入りません。
- 後続 stage の重みを読み込む前に expert profile を読み、profile 内の pair サイズを積算します。native pack では slot stride（SYCL 側は blob サイズを 256 byte 単位に切り上げ）、それ以外では expert layout の最大 blob サイズを使います。先頭 GPU の空き VRAM から全層の session、`--vram-reserve-mib`、drafter/head、verify window の見積もりを引いた残りと比較します。
- pair が残り容量以内なら、split をスキップした旨と容量の内訳を標準エラーに出し、multi-GPU / auto の状態、stage 配置、`--layer-split` をクリアして単一 GPU 経路へ進みます。
- 収まらなければ容量と不足量を標準エラーに出して split を維持します。remote expert cache の使用、profile の未指定、profile の読み込み失敗でも理由を標準エラーに出して split を維持します。この判定だけで起動を失敗させる処理はありません。
- 相互作用として、`STRATA_SPLIT_OWN` が設定されていても、このフラグがあると split の prompt buffer を個別確保する自動判定を通らず、split は cache から借りる設定を保ちます。明示した `--no-prefill-borrow` は別途反映されます。

## 適用条件と副作用

- CUDA/HIP 実装と SYCL 実装に同じ parser・判定があります。どちらも先頭 device の実メモリ情報を用いるため、判定は起動時の空き VRAM に依存します。単一 GPU 化が選ばれた場合も、他の起動時メモリ確保が成功することまでは保証しません。
- 判定に使う profile が無い・読めない、または remote expert cache が有効なら、容量判定をせず split を維持します。明示 split や multi-GPU でない実行では実質的に無視されます。
- 成功時に split が解除されるため、以降の処理は通常の単一 GPU 経路になります。ファイルを書き換える副作用は確認できません。

## 出力とエラー

判定メッセージは `stderr` に出力されます。profile 読み込み不可・remote cache 使用時と、容量不足時は split 維持の旨を、容量が足りる場合は split を省略して先頭 GPU で動かす旨を表示します。フラグ固有の終了コード変更はありません。別途 `--layer-split` の不正な指定や通常の起動処理が失敗すれば、その経路のエラーになります。

## 根拠

- `engine/src/program/generate.cpp:1070-1079` — split option の説明とフラグ既定値。
- `engine/src/program/generate.cpp:4065-4068` — parser が値なしでフラグを有効にする箇所。
- `engine/src/program/generate.cpp:4840-4856` — auto split の検証・単一 GPU 時の解除と multi-GPU 判定。
- `engine/src/program/generate.cpp:4920-4924` — `STRATA_SPLIT_OWN` による buffer 判定との相互作用。
- `engine/src/program/generate.cpp:6446-6493` — profile 読み込み、サイズ・空き VRAM の比較、成功時の split 解除、split 維持の診断。
- `engine/sycl/src/program/generate.cpp:707-716,2058-2061,3522-3586` — SYCL 側にも同様の parser と判定があること。
- `terminal/serve/server.py:3746-3750` — server config の `split_skip_if_fits` が有効で、args にフラグが未指定なら engine args に追加。
