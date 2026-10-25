# `STRATA_MTP_TOP2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP の draft token が verifier に拒否されたとき、draft head の logits で2番目に大きい token が verifier の出力と一致した回数を深さごとに数え、`strata serve` の stderr に診断行を出すためのフラグです。実装コメントも「2本目の枝が何を拾えたか」を測る診断としています。

ただし、この HEAD では runner-up token を計算する `MtpDrafter::record_top2()` に呼び出し箇所がありません。従って実行中に `top2_` が設定されず、`top2()` は常に `-1` を返します。環境変数を有効にしても `runner-up` hit 数は常に 0 となり、意図された測定結果は得られません。通常の draft / verify の token 選択や生成結果は変えません。

## 値と判定

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 先頭文字が `1` | 有効 |
| 空文字、先頭文字が `1` 以外 | 無効 |

文字列全体や数値としての妥当性は parse しません。`1`, `10`, `1anything` は有効で、`true`, `01`, 空文字は無効です。判定結果は `top2_env()` 内の `static const bool` に保存され、プロセス内で初めて呼ばれた後に環境を書き換えても再評価されません。

根拠: `src/core/mtp.cpp:465-467`、`sycl/src/core/mtp.cpp:558-560`。

## 有効になる条件

`strata serve` の各リクエストで、decode window に MTP draft の拒否があり、suffix draft 由来ではなく、初回 window でもなく、拒否深度が `T_mtp - 1` 未満かつ 8 未満の場合に `rejected` カウンターを増やします。リクエスト末尾には、変数が有効なら `strata serve: mtp top2: rejected/runner-up by depth ... of ... windows` を stderr に出します。カウンターはリクエストごとにゼロ初期化されます。条件を満たす拒否がないリクエストでも診断行自体は出ます。

MTP を使わないリクエストでは拒否カウンターは増えません。環境変数の有効化だけでは MTP を有効にせず、MTP の有無は `--mtp` の設定から決まります。通常の `generate` 経路には、この変数による集計・診断行はありません。

根拠: `src/program/generate.cpp:6871`（`--mtp` による serve の有効化）、`src/program/generate.cpp:11921-11930,12377-12381`（拒否集計と診断行）。SYCL 実装も同じ判定と集計を持ち、`sycl/src/program/generate.cpp:11185-11192,11587-11591` にあります。

## 実行時の詳細

`top2_env()` は通常の MTP 有効条件を設定する関数ではなく、診断カウンターと末尾ログの条件に使われます。CUDA/HIP 側と SYCL 側に、head logits を host にコピーし、最大値と2番目の値の token ID を `top2_[j]` に保存する `record_top2()` が実装されています。draft vocab subset を使う場合は subset 内の2番目の index を token ID に戻します。コピー失敗時、範囲外 index、runner-up がない場合には `-1` を保存する設計です。

しかし HEAD のソース全体で `record_top2()` の呼び出しは見つからず、`top2_` を書くコードはこの関数内だけです。初期状態では `top2_` は空で、`top2(j)` は範囲外なら `-1` を返します。そのため現状の診断行では rejection 数は条件に応じて増える一方、runner-up hit 数は常に 0 です。runner-up 算出のための host コピーや走査も現状の実行経路では起きません。

根拠: `src/core/mtp.cpp:472-488`（未呼び出しの runner-up 計算）、`include/strata/core/mtp.hpp:68-70,212-213`（公開 accessor と初期 vector）、`src/program/generate.cpp:11927-11930`（hit 判定）。SYCL 側は `sycl/src/core/mtp.cpp:565-584`、`sycl/include/strata/core/mtp.hpp:71-73,218-219`。

## 根拠

- 変数の直接読み取りとキャッシュ: `src/core/mtp.cpp:465-467`、`sycl/src/core/mtp.cpp:558-560`。
- 診断の意図と host 側 runner-up 算出: `src/core/mtp.cpp:470-488`、`sycl/src/core/mtp.cpp:563-584`。
- 値を参照する集計・ログ: `src/program/generate.cpp:11927-11930,12377-12381`、`sycl/src/program/generate.cpp:11189-11192,11587-11591`。
- `docs/DETAILS.md` を含む Strata の docs には、この変数の動作や測定結果の説明は見つかりませんでした。
