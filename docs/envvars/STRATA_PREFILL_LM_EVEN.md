# `STRATA_PREFILL_LM_EVEN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

layer-major prefill の super-chunk を GPU ごとの空きメモリに合わせて決めた後、プロンプト全体をほぼ同じ大きさの super-chunk に分割できる場合に、各ステージのバッファをその大きさに取り直すかを制御します。既定では取り直します。`0` で始まる値を設定すると、各ステージで確保できた最大サイズを維持し、最後の小さい super-chunk を許します。

これは layer-major prefill 自体の ON/OFF ではありません。layer-major の選択は `STRATA_PREFILL_LAYER_MAJOR`、backend、stage 数、その他の適用条件で決まり、この変数は `lm_prepare_chain()` が共通サイズを準備できた後の分割サイズ調整だけに使われます（`src/prefill/prefill.cpp:6117-6164,7238-7271`）。

## 値と判定

| 環境値 | 判定 | 動作 |
|---|---|---|
| 未設定 | 有効 | 均等サイズへの取り直しを許可 |
| 空文字 | 有効 | `getenv()` は非 null、先頭文字は `\0` なので `0` ではない |
| 先頭文字が `0` | 無効 | 現在の各ステージの確保サイズ `cap` をそのまま使う |
| それ以外 | 有効 | 均等サイズへの取り直しを許可 |

文字列全体の parse、数値変換、大文字小文字判定はありません。したがって `0`, `0anything`, ` 0`（空白が先頭）は無効、`false`, `00`, `1`, `anything`, 空文字は有効です。判定結果は `lm_even_env()` の `static const bool` に保存され、プロセス内の初回評価後に環境を変更しても再評価されません（`src/prefill/prefill.cpp:5905-5908`）。

## 有効になる条件

この変数が参照されるのは、`lm_prepare_chain()` がすべての Prefill stage で共通のサイズ `cap` を得た場合だけです。`n` は読み込む prompt の合計 token 数、`T` は先頭 stage の chunk 幅、`k = ceil(n / cap)`、`even = ceil(ceil(n / k) / T) * T` です。`k < 2` または `even >= cap` なら環境値を評価せず `cap` を返します。均等化が可能な場合、既定（または先頭が `0` でない値）では各 stage の buffer を `even` で再準備し、先頭が `0` なら再準備せず `cap` を返します（`src/prefill/prefill.cpp:6146-6164`）。

通常の `Prefill::run()` では layer-major が選ばれた prompt のみがこの処理に到達します。レイヤー分割は CUDA で既定選択される条件の一つですが、単一 GPU でも `STRATA_PREFILL_LAYER_MAJOR` で opt-in すれば対象になりえます。HIP build は layer-major を使うのに別変数 `STRATA_LM_HIP=1` が必要です。layer-major 自体は `STRATA_PREFILL_LAYER_MAJOR` が明示設定されればその値で解決され、未設定時は backend、stage 数、`STRATA_DEFAULTS=026` によって決まります（`include/strata/core/sm120_series.hpp:112-120`, `src/prefill/prefill.cpp:7233-7243`）。

Metal build の `Prefill::run()` は layer-major 判定より先に Metal engine の prompt 処理へ戻るため、この環境変数は参照されません（`src/prefill/prefill.cpp:7222-7231`）。

layer-major の準備は、未初期化、peer GPU/helper、画像 prompt、DFlash2 prompt taps、KVA、chunk 境界で yield する batch read、`--prefill-pipe` による chunk 指定、対応しない nibble expert、routing/row debug dump、必要な expert/MMQ/FP16 buffer がない状態、対応外 expert format、fused expert layout などで拒否されます。さらに prompt が短すぎる、空き VRAM / pinned RAM が足りない、stage 間で共通サイズが作れない場合も layer-major は成立しません（`src/prefill/prefill.cpp:5955-6026,6040-6061,6117-6168`）。これらの場合、この変数の値で layer-major が有効になることはありません。

別経路の `Prefill::run_multi()`（複数 prompt の co-read）も `lm_prepare_chain()` を呼ぶため、共通 super-chunk の均等化が可能ならこの変数の対象です。`run_multi()` は短い合計 prompt でも layer-major を試みます（`src/prefill/prefill.cpp:6188-6206`）。呼び出し元は co-read が「declined」なら通常の prompt read に戻します（`src/program/generate.cpp:15218-15224`）。

## 実行時の詳細

`lm_prepare_chain()` は最大4回、各 stage に `lm_prepare(n, why, cap)` を呼び、全 stage の super-chunk サイズが一致するまで調整します。均等化が有効なときは全 stage の既存 buffer を解放して `even` 上限で再確保します。再確保がどれかの stage で失敗すると chain 全体を解放して失敗を返し、環境値が有効でも layer-major の実行には進みません（`src/prefill/prefill.cpp:6129-6168`）。通常の `run()` はこの場合 chunk-major の `run_impl()` に進みます。理由が変わった場合 `stderr` に `strata prefill: layer-major off for this prompt: ...` を出します（`src/prefill/prefill.cpp:7254-7271`）。

均等化後に layer-major が実行されると、stderr の `strata prefill: layer-major ...` 行に super-chunk の個数と最大 token 数が出ます（`src/prefill/prefill.cpp:7159-7167`）。この環境変数専用のログや、値が不正という警告はありません。`run_multi()` では準備失敗時に `prefill: multi-prompt read declined: ...` を返し、呼び出し側は `strata batch: co-read of ... declined (...)` を stderr に出して通常 read に fallback します（`src/prefill/prefill.cpp:6193-6198`, `src/program/generate.cpp:15218-15224`）。

CLI がこの環境変数の値を直接上書きする処理はありません。`--prefill-pipe` による chunk plan は layer-major の準備を拒否する条件であり、`STRATA_PREFILL_LM_TOKENS` は `lm_prepare()` が基礎となる目標サイズを決める別設定です。その値や stage ごとの空きメモリにより `cap` が変わり、結果として均等化が不要になったり、適用可能になったりします（`src/prefill/prefill.cpp:6024-6032,6146-6164`）。

## 根拠

- 環境値の読み取り、先頭文字判定、static cache: `src/prefill/prefill.cpp:5905-5908`
- layer-major の前提条件と基礎 super-chunk サイズ・fit: `src/prefill/prefill.cpp:5955-6061`
- chain stage の sizing と均等化式・再確保: `src/prefill/prefill.cpp:6117-6168`
- 通常 prompt の選択、fallback と理由ログ: `src/prefill/prefill.cpp:7222-7271`
- multi-prompt co-read 経路: `src/prefill/prefill.cpp:6188-6206`, `src/program/generate.cpp:15178-15224`
- layer-major backend/default resolver: `include/strata/core/sm120_series.hpp:112-120`, `src/prefill/prefill.cpp:7233-7243`
