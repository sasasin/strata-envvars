# `STRATA_PF_BATCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリやドライバーが読む環境変数の動作は対象外。

## 役割

fused prompt-expert 経路で、一度の expert kernel launch に含める expert 数を指定します。router が選んだ行や出力の計算内容を選択する設定ではなく、expert ID 順に作る launch batch の幅を変えます。変数自体は fused 経路を有効化しません。

対象箇所は prefill の fused branch です。Q2_0 pack の fused 経路、または形式・device が対応する native pack の fused 経路で使われます。通常の MMQ/FP16 経路、decode、server 専用の設定としては参照されていません（`src/prefill/prefill.cpp:4192-4198,4221-4223,4252-4258,4273-4280`）。

## 値と判定

`std::atoi` で整数化し、結果が正の場合だけ指定値を使います。正の値は build の `kBatchRoom` まで切り詰めます。unset、空文字、整数化結果が 0 以下の場合は既定値の `kMaxBatch`（128）です（`src/prefill/prefill.cpp:4273-4279`）。

| 環境値 | 判定結果 |
|---|---|
| unset / 空文字 | 既定値 128 |
| `0`、負数、数字に変換できない文字列 | 既定値 128 |
| 正の整数 | `min(atoi(value), kBatchRoom)` |
| 数字の後ろに文字が続く値 | `atoi` が先頭の数値部分を変換した結果を使用（例: `12junk` は 12） |

全体文字列の検証や無効値警告はありません。空白や符号などの扱いは `atoi` によります。整数型の範囲を超える文字列について、Strata 側に検証・規定された処理はありません。

`kBatchRoom` は CUDA の通常 build で 512、HIP・gfx906・`STRATA_EXPERIMENTAL_SM60` build で 128 です（`include/strata/prefill/moe_fused.hpp:25-34`）。ただし 512 が実際の launch 幅になるのは後述の native wide 経路だけです。

## 有効になる条件

- prefill の該当 MoE layer が fused branch を選ぶ必要があります。Q2_0 側は `fused::enabled()`、native pack 側は `fused::native_supported()` と `fused_nat` の形式・layout・device 条件を通ります。複数 GPU の peer 経路、非 streamed chunk、MMQ/FP16 fallback など fused branch を通らない処理では、この値は launch 幅に影響しません（`src/prefill/prefill.cpp:4192-4198,4217-4223,4252-4258`）。
- Q2_0 fused は CUDA 用実装で、HIP は Q2_0 fused を使わず MMQ 等に進みます。native fused も build と device 上の対応形式が必要です（`CMakeLists.txt:2149-2153,2391-2416`; `src/prefill/prefill.cpp:110-129`; `src/prefill/moe_fused_iq.cu:1976-2015`）。
- 通常の fused native kernel と Q2_0 fused kernel は最大 128 experts/launch です。native で `fused_nat` が真かつ `native_wide()` が真なら wide kernel を選び、CUDA build では設定値を最大 512 まで使えます。native wide は `STRATA_PF_FUSED_NT=256`、`STRATA_PF_FUSED_F16=1`、または `STRATA_PF_FUSED_WS=1` によって該当 kernel が device 上で設定された場合に利用可能です。HIP など `kBatchRoom=128` の build では wide batch も 128 が上限です（`src/prefill/prefill.cpp:4278-4279`; `include/strata/prefill/moe_fused.hpp:25-34`; `src/prefill/moe_fused_iq.cu:1714-1725,2113-2141`）。
- native wide kernel が設定されていない場合、native 経路も一 launch あたり最大 128 に丸めます。設定値を 128 より大きくしただけでは wide kernel は有効になりません（`src/prefill/prefill.cpp:4278-4279`）。

## 実行時の詳細

値は fused branch 内の function-local `static const int pf_batch` の初期化時に一度読み取られます。したがって初回の fused batch 作成後にプロセス環境を変更しても再評価されません。CLI 引数や設定ファイルからの上書き処理はこの読み取り箇所にありません（`src/prefill/prefill.cpp:4273-4277`）。

fused 経路は expert ID を順に走査し、`per_launch` 件を一つの `Batch`（wide の場合は `WideBatch`）にまとめて launch します。実際の幅は wide 条件成立時には `pf_batch`、それ以外は `min(pf_batch, 128)` です。選択された expert の streamed blob を含む batch では、そのコピー完了を待ってから kernel を起動し、完了後に ring slot を返します（`src/prefill/prefill.cpp:4263-4279,4280-4329`）。ヘッダーの説明では、batch 幅を変えても同じ行を計算し、出力 bit は同じとされています（`src/prefill/prefill.cpp:4269-4272`; `src/prefill/moe_fused_iq.cu:552-555`）。

この変数専用のログ、警告、無効値エラーはありません。fused 経路に入った場合は共通ログとして stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を一度出します（`src/prefill/prefill.cpp:4252-4257`）。native kernel の形式未対応などは別条件の失敗経路で、`prefill fused experts (native): types ... are not covered here` を stderr に出して `exit(1)` しますが、batch 値の不正を示すものではありません（`src/prefill/moe_fused_iq.cu:2025-2032,2143-2150`）。

## 根拠

- 全参照検索では、実際の環境読み取りは `src/prefill/prefill.cpp:4274` の一箇所でした。その他の参照は実装コメントまたは文書です。
- `docs/DETAILS.md:1535-1544` は CUDA の sm_80 向け opt-in prompt switch 群として本変数を説明し、NT=256 と併用した測定として 4K/16K/52K prompt の +7.6%/+4.9%/+4.3% を掲載しています。同節は CMP 170HX での報告者測定で、Strata 側では測定していないと明記しています。この数値はその報告条件に限られ、ここで独自に再測定した結果ではありません。

