# `STRATA_MTP_TOP2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の生成処理で、MTP draft が拒否された深さごとの件数と、その時点で検証側が選んだ token が draft head の runner-up と一致した件数を stderr に出すための診断フラグです。通常の MTP draft や検証 token の選択方法は変えません。ただし CUDA/HIP の複数 slot 向け一括 MTP draft 判定から除外するため、有効時はその経路の実行方式に影響します。`top2_env()` は CUDA/HIP と SYCL の MTP 実装にあります（`engine/src/core/mtp.cpp:699-702`、`engine/sycl/src/core/mtp.cpp:621-624`）。

## 値と判定

両実装とも `std::getenv` の結果の先頭 1 文字だけを `'1'` と比較します。文字列全体の parse、数値検証、空白除去、大文字小文字変換はしません。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP (`engine/src`) | 無効 | `1`、`10`、`1anything` など先頭 byte が ASCII `1` | 空文字、`0`、`true`、`TRUE`、` 1` など先頭 byte が `1` でない値 |
| SYCL (`engine/sycl/src`) | 無効 | `1`、`10`、`1anything` など先頭 byte が ASCII `1` | 空文字、`0`、`true`、`TRUE`、` 1` など先頭 byte が `1` でない値 |

どちらも `v && v[0] == '1'` が判定式です。未設定と空文字はいずれも無効です（`engine/src/core/mtp.cpp:699-702`、`engine/sycl/src/core/mtp.cpp:621-624`）。

## 有効になる条件

- 対象 backend の Strata 実行ファイルを使い、`--serve` のリクエスト生成処理まで到達すること。記録・集計箇所は CUDA/HIP 側 `engine/src/program/generate.cpp` と SYCL 側 `engine/sycl/src/program/generate.cpp` にあります。
- 深さ別の拒否数は、suffix draft ではなく、最初の window でもなく、MTP draft が拒否され (`a < T_mtp - 1`)、深さ index が 8 未満の window でだけ加算されます（`engine/src/program/generate.cpp:23052-23056`、`engine/sycl/src/program/generate.cpp:12794-12798`）。
- CUDA/HIP で一括 MTP drafting 判定から除外されるのは、`STRATA_BATCH_MTP_FUSED` が設定され、空でなく、先頭文字が `0` でないことに加え、`--batch-mtp` または `STRATA_BATCH_MTP` などで `batch_mtp` が有効、DFlash2 を使わず、layer split の stage がない場合です。その候補経路で `top2_env()` が true だと `can_draft_slots()` が false を返し、呼び出し側は slot ごとの `draft()` にフォールバックします。fused 経路を有効にするための別条件が満たされなければ、この相互作用はありません（`engine/src/program/generate.cpp:17292-17298`、`engine/src/core/mtp.cpp:2242-2251`、`engine/src/program/generate.cpp:17412-17449`）。SYCL 側ではこの `can_draft_slots()` 経路は確認できません。
- `STRATA_MTP_TOP2` が無効でも、通常の MTP drafting は継続し、top2 の集計ログを出しません。

## 実行時の詳細

値は `top2_env()` 内の関数ローカル `static` に初回呼び出し時に保存されます。呼び出しは CUDA/HIP の一括 draft 判定や各 window の集計条件、リクエスト終了時のログ判定から行われるため、必ずしもプロセス起動時に評価されるわけではありません。最初の呼び出し後にプロセス環境を変更しても、そのプロセス内では判定は更新されません（`engine/src/core/mtp.cpp:699-702`、`engine/sycl/src/core/mtp.cpp:621-624`）。

両 backend に `record_top2()` があり、draft head logits を host にコピーして runner-up token ID を `top2_` に保存する実装です（`engine/src/core/mtp.cpp:704-722`、`engine/sycl/src/core/mtp.cpp:626-647`）。しかし調査した現行 Strata ソースでは、このメソッドの呼び出し箇所が見つかりません。`top2_` が空のとき `top2(j)` は `-1` を返し、runner-up 値は現行経路から設定されません（`engine/include/strata/core/mtp.hpp:86-88`、`engine/sycl/include/strata/core/mtp.hpp:71-73`）。従って以下の runner-up hit 集計は現行ソースでは有効な hit 値を記録できません。

## ログと測定値

有効時、リクエスト終了時に stderr へ次の形式で出力します（`engine/src/program/generate.cpp:23934-23938`、`engine/sycl/src/program/generate.cpp:13267-13271`）。

```text
strata serve: mtp top2: rejected/runner-up by depth <拒否数>/<runner-up hit数> ... of <window数> windows
```

出力引数は深さ 0〜3 までで、内部配列の集計上限（深さ 8）より短い表示です。前述のとおり、現行ソースには `record_top2()` の呼び出しがないため runner-up hit 数は増えません。測定値は記載しません。

## 根拠

- `engine/src/core/mtp.cpp:699-722` — CUDA/HIP 側の環境変数判定、runner-up 計算実装。
- `engine/sycl/src/core/mtp.cpp:621-647` — SYCL 側の環境変数判定、runner-up 計算実装。
- `engine/include/strata/core/mtp.hpp:86-88`、`engine/sycl/include/strata/core/mtp.hpp:71-73` — `top2()` の未設定値。
- `engine/src/core/mtp.cpp:2242-2251`、`engine/src/program/generate.cpp:17412-17449` — CUDA/HIP 一括 MTP 判定と slot ごとの fallback。
- `engine/src/program/generate.cpp:17292-17298` — 一括経路の `STRATA_BATCH_MTP_FUSED`、`batch_mtp`、DFlash2、stage 条件。
- `engine/src/program/generate.cpp:23052-23056,23934-23938` — CUDA/HIP 側の集計条件と stderr 出力。
- `engine/sycl/src/program/generate.cpp:12794-12798,13267-13271` — SYCL 側の集計条件と stderr 出力。
