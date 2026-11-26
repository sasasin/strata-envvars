# `STRATA_BATCH_ATTN_ROWS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA attention を含む verifier のバッチ窓で、各行ごとに実行していた block score・top-k・decode attention を、窓内の複数行をまとめるカーネル呼び出しに切り替える。各行は引き続き自身の indexer と K/V pool を使う。通常の単独窓では `batch_rec_` が false のため、この設定だけでは経路は切り替わらない。CUDA/HIP 共通実装と SYCL 実装に読み取りがある（`engine/src/core/verify.cpp:2194-2199`, `engine/sycl/src/core/verify.cpp:1485-1494`）。

## 値と判定

両実装とも `std::getenv` の結果を `std::atoi` に渡し、結果が 0 以外なら有効とする。文字列全体の数値妥当性検査はなく、`atoi` が先頭から変換できた整数部分で判定する。未設定と空文字は 0。例では `1`, `-1`, `2` が有効、`0`, `0anything`, `true`, `false`, 空文字は無効。先頭空白や符号の後に数値がある場合は `atoi` の変換結果に従い、数値の後ろの文字列は無視される。大文字小文字の概念はない（`engine/src/core/verify.cpp:375-377,391`; `engine/sycl/src/core/verify.cpp:1488-1491`）。

| 実装・起動条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP verifier。Linux CUDA の `--batch` slot 数が 2 以上なら、未設定時に起動処理が `1` を補う | 通常は OFF。Linux CUDA で slot 数 2 以上の場合は起動時の既定値により ON | `atoi(value) != 0`（例: `1`, `-1`, `2`） | `atoi(value) == 0`（例: `0`, `0anything`, `true`, `false`, 空文字） |
| HIP の gfx11 parallel defaults 条件が成立する起動 | 条件成立時は起動処理が `1` を補う。それ以外は OFF | 同上 | 同上 |
| SYCL verifier | OFF | 同上 | 同上 |

HIP では起動時の既定値設定が環境変数の「設定有無」を先に調べるため、明示した空文字も既定値で上書きされず OFF になる。既定値が適用されない経路でも判定自体は同じである（`engine/src/core/arch_defaults.cpp:218-223,302-309,346-350`; `engine/src/program/generate.cpp:4287-4320`; `engine/sycl/src/program/generate.cpp:2223-2228`）。

## 有効になる条件

- verifier がバッチ窓を記録していること（CUDA/HIP は `capture_batch` 中に `batch_rec_` を true にして `record_window` を呼ぶ: `engine/src/core/verify.cpp:4677-4691`）。
- 対象層が QSA 層であること。QSA の窓内行数が最大 8 以下であること。超える場合は行ごとの経路を使う（`engine/src/core/verify.cpp:2198-2199`; `engine/sycl/src/core/verify.cpp:1492-1494`; 最大値は `engine/include/strata/kernels/qsa_decode_attn.hpp:36` と `engine/sycl/include/strata/kernels/qsa_decode_attn.hpp:36`）。
- 窓内の対象 QSA 状態に KV streaming (`kv_mode == 1`) がないこと。1 つでも該当するとこのまとめ処理を使わず、行ごとの選択・resolve・attention 経路に戻る（CUDA/HIP: `engine/src/core/verify.cpp:2191-2199,2232-2264,2450-2470`; SYCL: `engine/sycl/src/core/verify.cpp:1492-1513`）。CUDA/HIP では QSA stream opt 経路 (`stream_opt_ok`) が選ばれた場合も `!stream_opt_ok` 条件により、この変数による分岐は適用されない（同 `verify.cpp:2192-2199`）。
- 既定値の自動投入は別条件に限られる。Linux CUDA は `o.batch >= 2` で parallel stack を投入する（ユーザーが設定済みなら値を保持。`engine/src/core/arch_defaults.cpp:226-260`; 呼び出しは `engine/src/program/generate.cpp:4410-4414`）。HIP は RDNA3 discrete (`gfx1100/1101/1102`) または Windows `gfx1151` の parallel defaults が対象で、batch slots が 2 以上、かつ `STRATA_GFX11_DEFAULTS=0` や `STRATA_GFX1151_DEFAULTS=0` など該当 defaults 無効条件がない場合に候補となる。各スイッチはユーザーが設定済みなら `=0` を含め保持される（`engine/include/strata/core/gfx11_extra.hpp:27-30,116-132`; `engine/src/core/arch_defaults.cpp:240-245,312-357,423-440`; HIP 呼び出し `engine/src/program/generate.cpp:4287-4320`）。この自動投入に該当しない HIP 構成と SYCL は、ここでの既定値投入は確認できず、未設定なら OFF。

## 実行時の詳細

CUDA/HIP では `batch_attn_rows_on()` 内の関数ローカル `static const bool` に初回評価結果を保存する。通常は最初に verifier の batch log または batch window の経路から評価され、以後の環境変更は反映されない。SYCL も `record_window` 内の関数ローカル `static const bool` で同様に初回評価時の値を保持する。HIP/CUDA のアーキテクチャ既定値は、生成処理で環境を設定した後に verifier が初回評価する順序になっている（`engine/src/core/verify.cpp:373-377,391`; `engine/sycl/src/core/verify.cpp:1488-1491`; `engine/src/program/generate.cpp:4287-4320,4410-4414`）。

有効な場合、QSA 各層・各窓について行ごとの indexer keys と pool 群を配列化し、全行の block scores、top-k、decode attention をそれぞれまとめて発行する。CUDA/HIP は `qsa_block_scores_rows` と `qsa_decode_attn_batch_rows` を使い、SYCL も対応する rows API を呼ぶ（`engine/src/core/verify.cpp:2218-2230,2450-2468`; `engine/sycl/src/core/verify.cpp:1494-1511`）。生成 token や選択結果が同一になることは、この分岐だけからは断定しない。

## ログと測定値

CUDA/HIP では batch verifier の初期化時に、`STRATA_BATCH_ATTN_ROWS` または `STRATA_BATCH_GDN_GROUPS` のどちらかが有効な場合、stderr に次の形式を出す。KV streaming があれば末尾の説明も付く。対象変数が OFF で他方も OFF の場合、この行は出ない（`engine/src/core/verify.cpp:4661-4673`）。

```text
strata verify: batch rows in one launch: attention on (STRATA_BATCH_ATTN_ROWS), GDN off (STRATA_BATCH_GDN_GROUPS)
```

SYCL 側ではこの変数の値を示すログは見つからなかった。`docs/BATCHING.md:704-723` は従来「両方 off by default」と記すが、現行コードでは上記の Linux CUDA と条件付き HIP parallel defaults が未設定値を `1` に設定するため、同資料の既定値説明はすべての現行経路には当てはまらない。資料記載の測定値は本調査で再測定していない。

## 根拠

- 読み取りと数値判定: `engine/src/core/verify.cpp:373-377,391`; `engine/sycl/src/core/verify.cpp:1488-1491`
- バッチ窓の開始とログ: `engine/src/core/verify.cpp:4661-4673,4677-4691`
- CUDA/HIP の適用分岐: `engine/src/core/verify.cpp:2191-2199,2218-2230,2450-2468`
- SYCL の適用分岐: `engine/sycl/src/core/verify.cpp:1492-1513`
- 自動既定値: `engine/src/core/arch_defaults.cpp:226-260,302-357,423-440`; `engine/include/strata/core/gfx11_extra.hpp:27-30,116-132`; 呼び出し `engine/src/program/generate.cpp:4287-4320,4410-4414`
