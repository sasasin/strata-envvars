# `STRATA_PRIVATE_MTP_DEMAND_LOG`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL のパイプライン decode 中、完了した MTP chain の状態を `STRATA_DEMAND_DETAIL` という JSON 形式の診断行として stderr に出すためのフラグです。トークン選択や chain の動作を有効にする変数ではありません。詳細ログには sequence、chain 種別、出力数、A window の情報、token 配列、probability 配列が含まれます（`sycl/src/program/generate.cpp:11860-11875`）。

## 値と判定

ログ側は `std::getenv(...) != nullptr` の有無だけを関数内 `static const bool` に保存します。値の文字列は parse しません。未設定なら無効、空文字を含め何らかの値が設定されていれば有効です（`sycl/src/program/generate.cpp:11866`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL のパイプライン decode が `chain_poll` に到達 | 詳細ログを出さない | 空文字、`0`、`false`、`0anything`、任意の文字列 | なし（未設定のみ無効） |

別に `private_demand::begin` もこの変数の設定有無を `State::metrics` に格納しますが、調査対象 HEAD ではその field を読む処理がなく、この格納は実際の分岐・ログに使われません。詳細ログを決めるのは上記の `demand_detail` です（`sycl/include/private_mtp_demand.hpp:27-30`; `sycl/src/program/generate.cpp:11866-11867`）。

## 有効になる条件

- 該当コードは SYCL executable の `generate.cpp` に含まれます（`sycl/CMakeLists.txt:305-307`）。
- パイプライン decode が使われる必要があります。コード上の `--pipeline-windows` は `--serve` の2 GPU layer split 用で、decode pipeline は値 `2`、または条件を満たす自動設定（両 GPU が Battlemage で MTP drafter が動作）で使われます（`sycl/src/program/generate.cpp:738-743`）。
- private demand state が有効である必要があります。別の `STRATA_PRIVATE_MTP_DEMAND` の値が先頭文字 `'1'` で始まり、`STRATA_PIPELINE_AGREE` が有効で、`force_miss == 0` のときだけ `begin(..., true)` になります。`STRATA_PIPELINE_AGREE` は未設定なら true、設定時は `atoi(value) != 0` です（`sycl/src/program/generate.cpp:11725-11736`）。この条件が満たされないと `get(&mtp)` は null を返し、詳細ログは出ません（`sycl/include/private_mtp_demand.hpp:23-25`; `sycl/src/program/generate.cpp:11862-11867`）。
- `chain_poll` が完了値 `1` を返した場合だけ詳細行を出します。未完了・エラーの poll には出ません（エラーは `die(err)` に進みます）（`sycl/src/program/generate.cpp:11860-11868`）。

## 実行時の詳細

`demand_detail` は最初にその関数内の該当行へ到達した時点で初期化され、以後プロセス内で cache されます。したがって、その初回到達後に環境を変更しても判定は変わりません。`State::metrics` 側の読み取りは `begin` のたびに行われますが、上記のとおり利用されません（`sycl/src/program/generate.cpp:11866`; `sycl/include/private_mtp_demand.hpp:27-30`）。

各完了 chain について `fprintf(stderr, ...)` で `STRATA_DEMAND_DETAIL {...}` を出力します。この変数自体は demand state を有効化せず、通常の decode を変えません。private demand state が有効なら、request の drain 後には別途 `STRATA_MTP_DEMAND ...` の集計行も出ますが、それはこの変数の判定ではなく state の有効性に基づきます（`sycl/src/program/generate.cpp:12148-12155`, `12220-12224`）。

## ログと測定値

詳細ログの接頭辞は `STRATA_DEMAND_DETAIL ` で、JSON 本体を stderr に出し、末尾に改行を付けます（`sycl/src/program/generate.cpp:11868-11875`）。`docs/DETAILS.md` にこの変数の測定値は見当たらず、本書では性能値を記載しません。

## 根拠

- `sycl/src/program/generate.cpp:11860-11875` — 完了 chain の判定、cache された設定確認、stderr 出力。
- `sycl/src/program/generate.cpp:11725-11736` — private demand state の別変数による有効条件。
- `sycl/include/private_mtp_demand.hpp:23-30` — thread-local state、owner/enabled 判定、`metrics` への設定。
- `sycl/src/program/generate.cpp:12148-12155`, `12220-12224` — drain 後の micro 判定と demand 集計ログ。
- `sycl/CMakeLists.txt:305-307`; `sycl/src/program/generate.cpp:738-743` — SYCL executable と `--pipeline-windows` の適用範囲。
