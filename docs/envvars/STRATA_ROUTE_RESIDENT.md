# `STRATA_ROUTE_RESIDENT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

512 expert・top-10 の router 結果について、指定した末尾順位にある非 resident expert を、logit が近い resident expert に置き換えます。resident expert を選ぶことで、後続の expert 実行時に非 resident expert の転送や CPU 計算が必要になる場合を減らす実験的な経路です。top-10 の ID と重みを変えるため、モデル出力も変わり得ます。既定では無効です。

主処理は `Verifier` の router 後、resident plan を作る前に実行されます。MTP draft router にも別の opt-in 変数 `STRATA_ROUTE_RESIDENT_MTP` を指定すると適用できます。

## 値と判定

`STRATA_ROUTE_RESIDENT` は `std::atof` で `float` に変換され、変換結果が `> 0.0f` のときだけ verifier の置換処理と統計カウンターが有効になります。未設定時は `0.0f`、空文字や数値として読めない文字列も `atof` の結果が 0 となるため無効です。数値の後ろに文字があっても数値部分は変換されます（例: `0.5junk` は 0.5）。負値、0、NaN は `> 0.0f` を満たさず無効です。正の値に上限はありません。設定文字列を保存するのではなく変換済み値を使います。

置換する順位範囲は関連変数 `STRATA_ROUTE_RESIDENT_RANKS` が指定します。未設定時は 0 始まりの rank `6` から `9`（top-10 の下位4件）です。設定時は `sscanf(v, "%d-%d", &lo, &hi)` を呼び、戻り値を検査せず、文字列全体の消費も確認しません。整数2個とハイフンが読めなければ、読み取りに成功した項目だけが更新され、残りは既定値のままです。後続の文字列は無視されます。rank の順序や範囲も検証されません。kernel は `r = lo` から `r <= hi && r < 10` まで走査するため、`hi >= 10` は rank 9 で止まりますが、負の `lo` は top-10 配列の範囲外を参照し得ます。負の rank を指定しないでください。

## 有効になる条件

- verifier では対象 layer の expert 数 `NE` が 512、top-k `K` が 10 で、`hits_.d_res` が null でないことが必要です。
- 条件を満たすと、通常 router または native router の結果を問わず、その後段で resident 置換 kernel を stream 上に起動します。`native_router_enabled()` 自体は追加条件ではありません。
- MTP draft ではさらに、MTP が使われ、layer stages が空（単一 GPU の経路）、resident table があり、`STRATA_ROUTE_RESIDENT` が設定済みであることが必要です。加えて `STRATA_ROUTE_RESIDENT_MTP` が設定され、その `atoi` 結果が 0 以外であり、margin が正である場合にだけ MTP に設定されます。したがって MTP 用の変数は厳密な `1` 判定ではなく、`atoi` で先頭から変換できる非ゼロ値なら有効です。空文字・非数値は無効です。
- kernel 自体は `src/kernels/cuda/native_router.cu` に実装されています。対象外の expert 数や top-k、resident table がない経路では変数が正でも呼び出されません。

## 実行時の詳細

Verifier 側の設定値は `route_resident_cfg()` の関数内 static 初期化で一度 parse されます。最初の `Verifier::init()` が統計ブロックを要求する際に評価されるため、その後プロセス内で環境を変更しても verifier 側には反映されません。MTP 条件は `generate.cpp` の生成セットアップ中に直接 `getenv` し、その時点で margin と順位を設定します。

kernel は token ごとに1 warpを使います。rank `lo..hi` を順に調べ、現在の expert が非 resident なら、現在選択済みの10件に含まれない resident expert のうち最大 logit のものを探します。候補があり、元の logit と候補 logit の差 `元 - 候補` が margin 以下なら、そのrankを候補に置き換えます。順位順に更新するため、先の置換結果は後続順位で選択済み expert として扱われます。同値の候補では小さい expert index を選びます。

置換が1件以上あった token では、新しい10件の logits に対する softmax を計算し、重みを再正規化します。置換がなければ router が出した重みを変更しません。置換処理後、verifier は更新済み ID/重みで resident plan 等を作ります。kernel 起動引数が不正、または launch error の場合、verifier は `verify route-resident: ...` をエラーに設定してその処理を失敗させます。

Verifier の統計用 GPU メモリは、margin が正のとき device ごとに確保されます。確保に失敗した場合は stderr に `route-resident: the counters could not be allocated on GPU %d; it runs without them` と出し、置換処理は統計なしで続きます。終了時、カウンターを読み出せた device について、`T>8 (prompt reads)` と `T<=8 (decode)` に分け、対象順位の非 resident 件数、置換数、全 top-10 の非 resident 件数の置換前後を stderr に出します。これらは処理数の統計であり、性能向上や品質を保証する測定値ではありません。MTP 側の置換呼び出しにはこのカウンターを渡しません。

## 文書との照合

`docs/DETAILS.md` はこの変数を opt-in の切り替えとして列挙し、`STRATA_ROUTE_RESIDENT_MTP` は単独の `STRATA_ROUTE_RESIDENT` より速くないと記載しています（1662-1663行）。同資料のこの箇所には測定条件や数値がなく、現ソースにも性能保証はありません。実装コメントはこの機能を実験的で出力を変えるものと明記しています。

## 根拠

- `src/core/verify.cpp:71-76,123-131`: margin と既定順位、および `atof` / `sscanf` による一度限りの parse。
- `src/core/verify.cpp:83-120,540-551`: device ごとの統計領域、確保失敗時の警告、終了時統計、Verifier 初期化からの取得。
- `src/core/verify.cpp:1464-1475`: router 後の条件判定、kernel 呼び出し、エラー処理。
- `src/kernels/cuda/native_router.cu:180-184,192-255`: 置換アルゴリズム、tie-break、softmax、カウンター、起動時チェック。
- `src/program/generate.cpp:7443-7454` と `src/core/mtp.cpp:915-932`: MTP 側の追加 opt-in 条件と適用箇所。
- `include/strata/core/mtp.hpp:50-55`: MTP 設定 API。
- `docs/DETAILS.md:1662-1663`: 文書上の opt-in 扱いと MTP 比較。
