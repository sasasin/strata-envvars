# `STRATA_NAN_INJECT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Verifier の非有限 logits 検出結果を、指定した window 番号でテスト用に合成する診断用フックです。実際の logits や sampler の出力値を書き換える処理ではなく、検出 mask に row 0 を立てて `nonfinite_row()` / `nonfinite_pos()` が異常を報告する状態にします。`note_nonfinite` が通常の検出結果を先に集め、既に非有限 row があれば注入では上書きしません。[`engine/src/core/verify.cpp:5821-5848`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

この状態を要求の終了に結びつける実装は `--serve` の要求処理です。該当 window の token は出力せず要求を `nonfinite` で終了し、次の要求開始時に live session、checkpoint、parked conversation 等を破棄して prompt を token 0 から読み直します。batch 経路では該当 slot を `BDONE ... nonfinite` で終了します。[`engine/src/program/generate.cpp:14547-14560`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)、[`engine/src/program/generate.cpp:17309-17321`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)、[`engine/src/program/generate.cpp:19242-19279`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)

## 値と判定

`std::getenv` で文字列を取得し、`std::strtoll(q, &end, 10)` で位置ごとに整数を読み取ります。文字列全体の厳密な検証はありません。`strtoll` が読めた数値のうち正数だけをリストに加え、直後の文字がカンマならカンマを越えて次を読みます。カンマ以外で数値変換が止まった場合はその位置から再度変換を試み、変換できなければそこで残りを無視します。そのためカンマは必須区切りではなく、例えば `1 2` も 1 と 2 を読みます。一方、数値の後ろの `x` や `.` は次の変換開始に使えないため、その位置で残りを無視します。通常の `n[,n...]` 形式では正の十進整数だけが有効です。`strtoll` が受け付ける先頭空白と符号は許され、負数・0 は読み取られても捨てられます。範囲外の `errno` は検査していません。[`engine/src/core/verify.cpp:5801-5817`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

| 条件 | 未設定 | 注入リストに入る値の例 | リストに入らない / 読み取りが止まる例 |
|---|---|---|---|
| `STRATA_NAN_INJECT` の初回読み取り | 空リスト（注入なし） | `1`、`1,3`、`+2`、` 2` | 空文字、`0`、`-1`、`true`、`,2` |

`1x` は `1` を読み取った後 `x` で停止し、`1,abc,3` は `1` の後で変換できず残りを読みません。`1,,3` も 2 個目の変換で停止するため `3` は読みません。大文字小文字の比較はありません。値が空リストになればカウンターも進まず、非有限結果は合成されません。[`engine/src/core/verify.cpp:5803-5815`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

注入を行うには別変数 `STRATA_NAN_GUARD` の guard が有効である必要があります。この変数は unset なら有効、設定時は `atoi(value) != 0` で判定されます。空文字・`0`・`false`・`true` は無効で、`1` や `2tail` は有効です。`STRATA_NAN_INJECT` を有効化する CLI 引数や、それを上書きする引数はこの実装にありません。[`engine/src/core/verify.cpp:5792-5799`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

## 有効になる条件

- `Verifier::note_nonfinite` が呼ばれ、`STRATA_NAN_GUARD` が有効であること。guard が無効なら関数は注入リストを参照する前に戻ります。[`engine/src/core/verify.cpp:5821-5830`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- head を持つ最終 stage の window であること。CUDA/HIP 側ではさらに `h_nf_ != nullptr` が必要です。Metal はこの buffer 条件を使わず、window の logits を host 側で scan します。[`engine/src/core/verify.cpp:5825-5837`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/src/core/verify.cpp:3745-3763`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- 注入リストに正の番号が 1 個以上あり、プロセス全体で数えた対象 window 番号がリストと一致すること。リストの番号は昇順でなくても構いません。[`engine/src/core/verify.cpp:5818-5819`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/src/core/verify.cpp:5838-5845`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)
- `--serve` では verifier の結果を検査する要求経路が注入状態を外部に示します。単発 CLI の各経路が同じ結果処理を行う根拠はこの変数の読み取り箇所からは確認できません。`docs/DETAILS.md:661-668` も one-shot command line と Intel (SYCL) port は check しないと記載しています。環境変数自体の読み取りは `engine/src/core/verify.cpp` のみです。

## 実行時の詳細

注入リストは関数内 `static const` であり、guard を通過して最初に `nan_inject_list()` に到達した時点の環境を一度読み取ります。未設定・空・無効な値をその時に読んだ場合も空リストとして保持され、以後の環境変更は反映されません。正の数を読んだ場合、注入対象 counter はプロセス共有の `std::atomic<long long>` で、リストが空でない各対象 window で 1 増えます。したがって起動時からの全 window 数ではなく、guard と stage 条件を通過し、非空リストを使う処理に到達した window の通し番号です。[`engine/src/core/verify.cpp:5803-5819`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/src/core/verify.cpp:5821-5845`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

番号が一致し、通常の非有限 mask がまだ空の場合、row 0 の bit を立てて `nf_row_` を 0 にします。position は `pos_b[0]`、または `last_pos0_ + 0` です。返すのは検出 metadata であり、この箇所で logits 配列は変更しません。既に実際の非有限 row があればその mask を維持し、注入専用ログも出しません。[`engine/src/core/verify.cpp:5832-5848`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/include/strata/core/verify.hpp:130-142`](../../../../Niko1221/Strata/engine/include/strata/core/verify.hpp)

`STRATA_NAN_GUARD` 自体も関数内 `static` で初回呼び出し時に評価されます。注入リストの読み取りは guard を通過した後なので、guard が最初に無効と判定された場合、注入リストはまだ読み取られません。[`engine/src/core/verify.cpp:5792-5799`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)、[`engine/src/core/verify.cpp:5821-5838`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

## ログと測定値

番号が一致して synthetic flag が立つ場合、stderr に次の行を出します（`k` はプロセス内の対象 window 番号）。実際の非有限 logits が同じ window に既にあれば、この注入ログは出ません。[`engine/src/core/verify.cpp:5838-5844`](../../../../Niko1221/Strata/engine/src/core/verify.cpp)

```text
strata verify: STRATA_NAN_INJECT: window <k> reported as non-finite
```

`--serve` が flag を検出した場合は stderr に `strata serve: non-finite logits (#879) in a <prompt|first decode|decode> window at position <position> (row <row>): its tokens are not emitted, the request ends (DONE nonfinite) and the next request reads its prompt from token 0` を出します。batch 処理では `strata batch: non-finite logits (#879) ...` を stderr、`BDONE <slot> <generated> nonfinite ...` を stdout に出します。[`engine/src/program/generate.cpp:14550-14560`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)、[`engine/src/program/generate.cpp:17309-17321`](../../../../Niko1221/Strata/engine/src/program/generate.cpp)

Strata の資料にこの変数による性能測定値はありません。

## 根拠

- 実読み取り、リスト変換、cache、カウンター、注入条件: `engine/src/core/verify.cpp:5801-5848`
- guard の既定値と cache: `engine/src/core/verify.cpp:5792-5799`
- CUDA/HIP と Metal の非有限検査条件: `engine/src/core/verify.cpp:3745-3763`, `engine/src/core/verify.cpp:5825-5837`
- verifier の非有限 row/position の公開: `engine/include/strata/core/verify.hpp:130-144`
- serve の要求終了と cache flush: `engine/src/program/generate.cpp:14547-14560`, `engine/src/program/generate.cpp:19242-19279`
- batch slot の終了: `engine/src/program/generate.cpp:17309-17321`
- 補足資料との照合: `docs/DETAILS.md:661-668`
