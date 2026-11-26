# `STRATA_PREFILL_LM_FORCE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

layer-major prefill がすでに選択されているとき、その経路を使う最小プロンプト長の判定を緩めます。通常は入力長 `n` が `2 * m.T` 未満だと `lm_prepare` が `"a short prompt"` で layer-major を断りますが、この変数が有効なら最小値を 1 token にします。layer-major 自体を ON にするスイッチではありません。通常の CUDA prompt 処理では、主スイッチ `STRATA_PREFILL_LAYER_MAJOR` が有効で `Prefill::run` の条件を通った後に効きます（`engine/src/prefill/prefill.cpp:8088-8090, 8235-8238, 9657-9662`）。

## 値と判定

`std::getenv` の結果について、未設定でなく、かつ先頭文字が文字 `'1'` の場合だけ true です。文字列全体の parse や数値妥当性検査はありません。空文字は false、空白を挟んだ `" 1"` も false、`"1"`・`"10"`・`"1anything"` は true、`"0"`・`"true"`・`"2"` は false です。大文字小文字の概念はなく、先頭の1文字だけを比較します（`engine/src/prefill/prefill.cpp:8088-8090`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `lm_prepare` に到達する実行経路 | false | 先頭文字が `1` (`1`, `10`, `1x`) | 空文字、`0`, `2`, `true`, ` 1` |

## 有効になる条件

- `Prefill::run` が layer-major 分岐へ入る必要があります。現行の `prefill_layer_major_default` は false で、通常は `STRATA_PREFILL_LAYER_MAJOR` の明示的な有効値が必要です。single-card small-cache の自動選択は条件に合うと同変数を設定します。`STRATA_PREFILL_LM_FORCE=1` 単独では layer-major を開始しません（`engine/include/strata/core/sm120_series.hpp:180-192, 211-219`; `engine/src/program/generate.cpp:12562-12590`; `engine/src/prefill/prefill.cpp:9657-9662`）。
- Metal の `Prefill::run` は Metal prompt 経路を実行して return するため、この変数を参照する layer-major 分岐には入りません（`engine/src/prefill/prefill.cpp:9633-9650`）。
- HIP build は、追加で `STRATA_LM_HIP` の先頭文字が `1` である必要があります。満たさない場合 `lm_prepare` は `"layer-major prefill has only been run on NVIDIA CUDA"` で decline します（`engine/src/prefill/prefill.cpp:8166-8179`）。
- CUDA/HIP の layer-major 経路でも、モデル未初期化、prompt hand-off / peer GPU、対象条件を満たさない layer split と PLE、画像 prompt、制約に合わない DFlash2 prompt taps、`STRATA_KVA`、chunk 境界で yield する batch read、`--prefill-pipe` の chunk plan、build 時の expert nibble が有効な場合、routing/row debug dump (`STRATA_DBG_FEAT`, `STRATA_DBG_ROUTE_OVERRIDE`, `STRATA_PREFILL_DUMP_R_ALL`)、必要な expert plan / buffer がない場合、WMMA 専用・APR/Hadamard・NVFP4 の未対応 layer、fused expert layout などでは `lm_prepare` が decline し、通常の chunk-major 経路に戻ります（`engine/src/prefill/prefill.cpp:8166-8234`）。
- 強制しても、GPU メモリに super-chunk が収まらない場合や layer split の各 stage が共通サイズを見つけられない場合は実行されません（`engine/src/prefill/prefill.cpp:8245-8285, 8342-8393`）。

## 実行時の詳細

値は `lm_force_env()` 内の関数ローカル `static const bool` 初期化子で一度だけ読み取られ、最初に `lm_prepare` が最小長判定まで到達したときの環境値がそのプロセス内で cache されます。その後に環境を変更しても反映されません。server request ごとの再読み取りや、子プロセスへの転送はこの変数の実装にはありません（`engine/src/prefill/prefill.cpp:8088-8090, 8235-8238`）。

最小長の優先順位は、内部 `lm_force_` またはこの環境変数が true なら `1`、そうでなく `STRATA_PREFILL_LM_TOKENS` の `atoll` 結果が正なら `m.T`、それ以外は `2 * m.T` です。`STRATA_PREFILL_LM_TOKENS` は最小長だけでなく super-chunk の目標サイズにも使われます。force は目標サイズ、入力長に基づく上限、GPU メモリ fit、stage 間の制約を解除しません。`lm_force_` は複数 prompt 用 `run_multi` が内部で立てる別の状態で、この環境変数とは独立です（`engine/src/prefill/prefill.cpp:8098-8100, 8235-8244, 8413-8424`）。

## ログと測定値

この変数専用の有効ログ、警告、終了経路はありません。layer-major が他の条件で decline した場合、非既定の明示選択では `strata prefill: layer-major off for this prompt: <理由>` が stderr に出ます。短い prompt の decline は `"a short prompt"` として理由ログの対象となり、unset 時の既定選択ではその行を抑制します。16 回続けて長い prompt が decline した場合は `strata prefill: layer-major still off, ...` の行も出ます。成功時には layer-major 処理を行い、prompt 単位の force 専用ログは出しません（`engine/src/prefill/prefill.cpp:9673-9703`）。

## 根拠

- 環境値の読み取りと先頭文字判定: `engine/src/prefill/prefill.cpp:8088-8090`
- 最小 prompt 長と `STRATA_PREFILL_LM_TOKENS` の判定: `engine/src/prefill/prefill.cpp:8235-8244`
- layer-major の選択、HIP 条件、fallback/log: `engine/src/prefill/prefill.cpp:8166-8234, 9652-9705`
- unset 時の主スイッチ既定と小さい cache の自動選択: `engine/include/strata/core/sm120_series.hpp:180-219`; `engine/src/program/generate.cpp:12562-12612`
- Metal 経路の早期 return: `engine/src/prefill/prefill.cpp:9633-9650`
