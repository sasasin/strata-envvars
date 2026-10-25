# `STRATA_ADAPT_EVICT_SYNC`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

適応 tier が expert の入れ替えコピーを待たずに次の検証 window を始める経路で、GPU 側の residency table に eviction を反映してから window を実行します。これにより、すでに VRAM から追い出された expert を GPU table が resident と誤認し、CPU 側の expert pool が古い activation を使って計算する状態を防ぎます。

この変数は `src/program/generate.cpp` の `adapt_evict_sync()` で一度だけ評価され、その結果が `ExpertDispatch::evict_sync` の設定に使われます。値の既定値は有効ですが、適応 tier がコピーを待つ通常経路ではこの機能は有効になりません。

## 値と判定

`std::atoi()` の結果が 0 かどうかで判定します。文字列全体の厳密な検証はなく、`atoi` が数値として読める先頭部分を変換します。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定値） |
| `0`、空文字、整数に変換できない文字列（例: `false`） | 無効（変換結果 0） |
| 0 以外の整数（負数を含む） | 有効 |
| 数字の後ろに文字が続く値（例: `1abc`、`0abc`） | 数字部分を変換し、その結果が 0 以外なら有効 |

先頭の空白や符号を含む入力の扱いも `atoi` の変換規則に従います。評価結果は関数内の `static const bool` に保存されるため、最初の評価後にプロセス環境を変更しても反映されません。

根拠: `src/program/generate.cpp:1507-1511`。

## 有効になる条件

環境変数の判定が有効でも、次の条件を満たす経路でのみ eviction 同期が動作します。

- 適応 tier が有効で、`--adapt-every` と `--adapt-swaps` から routing usage table が作られている。
- tier がコピー完了を待たない設定である。`STRATA_ADAPT_NOWAIT` の先頭文字が `1`、または `STRATA_ADAPT_LAG` の実効値が 1 より大きい。
- GPU の device residency table が存在する。
- `serve` の場合、window が serial である（`--pipeline-windows` ではなく、layer split を使った複数 batch group 経路でもない）。

`STRATA_ADAPT_NOWAIT` は先頭文字が `1` の場合だけ有効です。`STRATA_ADAPT_LAG` は `atoi` で変換され、未設定時は 1、設定時は最低 1 に clamp されます。したがって `STRATA_ADAPT_LAG=0` や数値に変換できない文字列だけでは tier-lag 条件を満たしません。

layer split を使った複数 batch group 経路では `evict_sync` 自体を立てず、変数が有効なら verifier に常に activation を publish させます。`serve` の `--pipeline-windows` 経路はこの同期フックの対象外です。単一 generate 経路には `serve` の `serial_windows` 判定はなく、device table、usage table、lag 条件で判定します。

関連箇所: `src/program/generate.cpp:1472-1485,9606-9614,15321-15336`。

## 実行時の詳細

適応 swap で evict した expert の index を dirty list に記録します。tier が待たないと、host 側の table では evicted expert を non-resident にした後も GPU table の更新は次の verifier launch まで遅れるため、その launch 前 hook が dirty entry を GPU に反映します。小さい更新は mapped host memory 上の `(index, value)` pair を使う `res_patch` kernel で変更箇所だけを更新し、pair 用 buffer が得られない場合や変更数が上限 16,384 を超える場合は residency table 全体を upload します。コピー完了後に新しく resident になった expert の entry も dirty list に加え、以降の window 前に反映します。

更新 API が CUDA error を返した場合、window は続行せず `the residency table update failed: ...` のエラーで失敗します。`serve` では機能が有効なとき起動時に `strata serve: the adaptive tier's evictions reach the device's table before the next window (STRATA_ADAPT_EVICT_SYNC=0: when its copies land)` を stderr に出します。通常の待機経路では同期機能を設定しないため、このログも出ません。単一 generate 経路にはこの機能を示す専用ログはありません。

根拠: `src/program/generate.cpp:1536-1566,9581-9592,9621-9650,9685-9692,9821-9824,15347-15364,15406-15415`、`src/kernels/cuda/verify_kernels.cu:601-603,700-704`、`src/core/verify.cpp:2662-2665,3542-3549`。

## 文書との照合

`docs/DETAILS.md:1885-1887` は `STRATA_ADAPT_NOWAIT=1` または `STRATA_ADAPT_LAG` が 1 より大きい場合に、eviction を次 window 前に device table へ反映する修正と説明しています。また `STRATA_ADAPT_EVICT_SYNC=0` でその修正を無効化でき、既定の「tier がコピーを待つ」経路は変更しないとしています。今回確認した実装と一致します。同資料はこの変数による性能値を示していません。
