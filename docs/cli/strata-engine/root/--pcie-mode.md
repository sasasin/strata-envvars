# `--pcie-mode`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数 parser） |
| オプション | `--pcie-mode` |
| 別名 | なし |
| 値 | 値を取る文字列。parser は文字列をそのまま保存し、値の列挙検証はしない |

## 役割

PCIe 経由で verifier に渡す expert blob の読み込み方式を選びます。`Options` の初期値は `auto` で、通常の verifier 経路では `auto` を GPU copy kernel 経路として設定します（`src/program/generate.cpp:687,9231-9236,16170-16175`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --pcie-mode kernel
```

エンジンの usage は `--tokens` を必須として示しています（`src/program/generate.cpp:806-812,3174-3178`）。

## 値と既定値

ソースコメントと設定処理から確認できる値は次のとおりです（`src/program/generate.cpp:687,9216-9236`）。

| 値 | verifier に渡す mode | 動作 |
| --- | ---: | --- |
| `auto`（既定値） | 2 | copy kernel で staging buffer に読み込む |
| `kernel` | 2 | `auto` と同じ copy kernel 経路 |
| `direct` | 1 | expert source の device alias を直接参照する |
| `dma` | 0 | host-to-device DMA で staging buffer にコピーする |

parser は `next("--pcie-mode")` で値を保存するだけで、許可値チェックや範囲補正をしません（`src/program/generate.cpp:2418-2420,2633-2637`）。実行時の写像は `dma` なら 0、`direct` なら 1、それ以外はすべて 2 です。したがって未記載の値も拒否されず、`kernel` と同じ mode 2 に進みます。値を省略した場合は通常の parser では `--pcie-mode needs a value` を stderr に出して status 2 で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

PCIe lane に割り当てられた expert ごとに、mode 0 は staging 上のポインタを plan に記録し、fetch callback にコピー対象数を渡します。mode 1 と 2 は source の device alias を plan に記録し、fetch callback にはコピー対象数 0 を渡します（`src/core/expert_source.cpp:4938-4961`）。

- `dma`（mode 0）では `Verifier::fetch_dma` が各 blob を `cudaMemcpyAsync` で staging に転送し、後続処理を host function で解放します。DMA batch 機能を使う経路で upload に失敗するとエラーを stderr に出し、GPU wait を解放して `abort()` します（`src/core/verify.cpp:3272-3301`）。
- `kernel` / `auto`（mode 2）では verifier が PCIe lane の待機後に copy kernel で staging へ移し、plan のポインタを staging 側へ付け替えます（`src/core/verify.cpp:2129-2138`）。
- `direct`（mode 1）は verifier の mode 2 専用コピー分岐に入らず、device alias を参照する plan を使います（`src/core/expert_source.cpp:4940-4944`, `src/core/verify.cpp:2133-2138`）。

この option は PCIe lane の割当率を設定しません。`--pcie-frac` 等で PCIe share が 0 なら lane は使われず、share が正でも expert miss がない場合や source がその layer の PCIe read に対応しない場合は PCIe 対象になりません（`src/program/generate.cpp:682-687`, `src/core/expert_source.cpp:4877-4884`）。share の詳細は [`--pcie-frac`](--pcie-frac.md) を参照してください。

## 適用条件と副作用

`STRATA_PIPED_CONCURRENT` による prompt read の並行化判定では、値が文字列 `dma` のときだけ `pcie_dma` 条件が立ち、並行化を止める理由として `--pcie-mode dma` を返します。`auto`、`kernel`、`direct`、および未知値はこの条件では DMA 扱いになりません（`src/program/generate.cpp:13554-13568`, `include/strata/program/batch_read.hpp:43-53`）。

Qwen3.6-35B-A3B の GGUF は main parser より前に family 専用 `strata::qwen35::run` へ転送されます（`src/program/generate.cpp:2393-2407`）。その parser に `--pcie-mode` の個別処理はありません。`--serve` が先に指定されていない通常経路では未知 option として usage を出して status 2 で終了し、`--serve` 後なら未対応 option として stderr に無視した旨を出し、続く値らしい引数も消費します（`src/qwen35/q36_engine.cu:3742-3748,3782-3795`）。このため通常 engine parser に対する本書の値の説明は同 family 専用経路には適用されません。

## 出力とエラー

通常 engine parser は未知の引数を `unknown argument: ...` と usage 付きで stderr に出して status 2 を返しますが、`--pcie-mode` の値自体は列挙検証対象ではないため、未知値だけを理由とするエラーはありません（`src/program/generate.cpp:2787-2793`）。DMA batch upload failure の出力・停止動作は上記のとおりです（`src/core/verify.cpp:3281-3295`）。

## 根拠

- option の初期値と想定表記: `src/program/generate.cpp:682-687`
- parser と必須値処理: `src/program/generate.cpp:2418-2420,2633-2637`
- 通常・split verifier への mode 設定: `src/program/generate.cpp:9212-9236,16170-16175`
- PCIe 対象選定・source pointer・fetch 呼び出し: `src/core/expert_source.cpp:4877-4884,4938-4961`
- kernel staging 経路: `src/core/verify.cpp:2129-2138`
- DMA 転送・batch upload 失敗経路: `src/core/verify.cpp:3272-3301`
- piped concurrent read の抑止条件: `src/program/generate.cpp:13554-13568`, `include/strata/program/batch_read.hpp:43-53`
- family 専用 parser への振り分け: `src/program/generate.cpp:2393-2407`
- family 専用 parser での未対応 option 処理: `src/qwen35/q36_engine.cu:3742-3748,3782-3795`

調査制約: CLI バイナリの `--help` は実行していません。ソース内の `usage()` に `--pcie-mode` の説明はなく、parser と使用箇所を根拠にしています。Release artifact、GPU/backend 別の実動作、未知値を与えた実行結果は確認していません。
