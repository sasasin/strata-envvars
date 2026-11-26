# `STRATA_DRAFT_TIMING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP draft の prompt K/V バッチ処理と、CUDA/HIP の MTP draft round について、処理時間を stderr に出す診断スイッチである。値の有無だけを見る prompt K/V 側と、値の先頭文字が `1` かを見る MTP round 側で判定が異なる。計算方式や draft 数をこの変数の値で選ぶ分岐はなく、測定用の同期・GPU event 計測を追加する。`Prefill::draft_kv` は CUDA/HIP と SYCL に実装され、Metal では同関数が対象外として decline する。MTP round の event 計測は `engine/src/core/mtp.cpp` の経路にある。根拠: `engine/src/prefill/prefill.cpp:2991-3000`、`engine/sycl/src/prefill/prefill.cpp:1857-1868`、`engine/src/core/mtp.cpp:1832-1863`。

`terminal/data/settings-register.json` にも名前と三つの読み取り座標が登録されているが、これは設定登録データであり、追加の実行時読み取り箇所ではない。根拠: `terminal/data/settings-register.json:7655-7678`。

## 値と判定

| 読み取り箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP・SYCL `Prefill::draft_kv` | 無効 | 空文字を含む、存在する値すべて（`1`, `0`, `true`, `0anything`） | なし。文字列内容を検査しない |
| `MtpDrafter::draft` の timing 計測 | 無効 | 先頭文字が `1` の値（`1`, `10`, `1anything`） | 空文字、`0`, `2`, `true`, ` 1` など、先頭が `1` でない値 |

prefill 側は `std::getenv(...) != nullptr` を関数内 `static const bool` に保存し、値を parse しない。MTP round 側は `DraftTiming` のグローバル初期化時に `getenv` し、`e != nullptr && e[0] == '1'` を保存する。どちらも数値変換・全体一致・範囲判定・大文字小文字変換はない。根拠: `engine/src/prefill/prefill.cpp:3079`、`engine/sycl/src/prefill/prefill.cpp:1937`、`engine/src/core/mtp.cpp:1841-1844`。

## 有効になる条件

- prompt K/V の時間行は、prompt 読み込み中に `Prefill::draft_kv` が実際にバッチ処理を実行して正常終了した場合に出る。単一 GPU では MTP 使用時にこの経路を試す。layer split では通常この経路を使わず、CUDA の生成経路では `STRATA_SPLIT_MTP_BATCH` が有効で、最後の stage に GGUF 形式の token embedding がある場合に試す。SYCL の server 経路では `use_mtp && !multi_gpu` の場合に試す。根拠: `engine/include/strata/program/draft_kv_plan.hpp:25-42`、`engine/src/program/generate.cpp:14763-14798`、`engine/sycl/src/program/generate.cpp:8622-8627`。
- バッチ処理は `STRATA_MTP_BATCH=0` で無効化される。draft K/V が非対応の mode（ring 以外の非 paged mode）、hybrid K/V、別 device、必要 tensor / gather 可能な embedding の欠落、64-row 分の scratch 不足などでも decline し、呼び出し元は通常 `MtpDrafter::prefill` に進む。このとき `STRATA_DRAFT_TIMING` による `strata draft kv:` 行は出ない。ring mode は `STRATA_MTP_BATCH_RING=0` で decline する。根拠: `engine/src/prefill/prefill.cpp:3001-3037,3045-3052`、`engine/sycl/src/prefill/prefill.cpp:1861-1874,1902-1913`、`engine/src/program/generate.cpp:14777-14798`。
- prompt K/V 計測の `static` 値は、その backend の `draft_kv` が条件を通過して読み取り箇所まで初めて到達したとき確定する。その後にプロセス環境を変更しても同関数内では反映されない。MTP round の値はグローバル `g_dt` の構築時に確定する。CLI 引数や設定ファイルがこの診断値を上書きする処理は見つからなかった。根拠: `engine/src/prefill/prefill.cpp:2991-3014,3078-3081`、`engine/sycl/src/prefill/prefill.cpp:1857-1874,1936-1942`、`engine/src/core/mtp.cpp:1841-1863`。
- MTP round の計測は `MtpDrafter::draft` のうち `min_p <= 0` かつ `chain_rule_` がない高速分岐を通らず、`max_steps > 0` の分岐に入った場合だけ event を記録する。したがって変数が有効でも通常の draft 条件によっては round timing 行が出ない。Metal の `draft` は別の早期経路を通り、ここでの event 計測を行わない。根拠: `engine/src/core/mtp.cpp:1865-1885,1936-1977,2043-2049`。

## 実行時の詳細

バッチ prompt K/V の計測が有効だと、CUDA は測定開始前に prefill stream を同期し、その後 drafter stream が idle になるまでの時間、バッチ処理時間、全体時間を測る。SYCL も同じ目的で prefill queue を待ってから計時する。成功すると両者とも処理した cell 数・開始位置・first-needed 位置・batch 幅と時間を一行で stderr に出す。同期の追加は測定対象を区切るためのもので、draft K/V の計算結果を選択する条件には使われない。根拠: `engine/src/prefill/prefill.cpp:3079-3084,3161-3169`、`engine/sycl/src/prefill/prefill.cpp:1937-1942,2037-2057`。

MTP round の計測は CUDA event を作成し、round graph と各 step graph の GPU 時間、graph 間の GPU gap、および host 側の staging・launch・PLE prefetch・待機時間を累積する。event 作成に失敗すると `on` を false にして計測を止め、ここでは警告を出さない。成功時も 300 round ごとのみ stderr に平均を出す。static な環境判定は実行中に再読込されない。根拠: `engine/src/core/mtp.cpp:1845-1859,1973-2044`。

## ログと測定値

prompt K/V の成功時ログ（CUDA/HIP・SYCL 共通）:

```text
strata draft kv: %lld cells from %lld (first needed %lld), batch %lld: drafter idle %.1f ms, the batches %.1f ms, all %.1f ms
```

MTP round の計測行（対象経路で 300 round ごと）:

```text
strata mtp draft timing: %lld rounds, %.2f steps/round: wall %.3f ms = round graph %.3f + steps %.3f GPU (%.3f per step) + host gaps between graphs %.3f + tail %.3f (per round)
strata mtp draft timing (host, per round): staging %.3f, graph launch calls %.3f, PLE prefetch %.3f, wait for draft 0 %.3f, waits for the steps %.3f
```

これらは実行時の測定ログであり、`STRATA_DRAFT_TIMING` に結び付いた性能測定値は Strata の `docs/DETAILS.md` に見つからなかった。MTP event 計測の初期化失敗時は無効化され、専用の警告は出ない。バッチ処理本体の後段同期が失敗した場合は、CUDA では `prefill: the draft layer's K/V: ` に CUDA エラー文字列を連結して失敗を返し、SYCL では同じ接頭辞に `dpct::get_error_string_dummy(0)` を連結して失敗を返す。根拠: `engine/src/prefill/prefill.cpp:3161-3169`、`engine/sycl/src/prefill/prefill.cpp:2037-2057`、`engine/src/core/mtp.cpp:1845-1859`。

## 根拠

- `engine/src/prefill/prefill.cpp:2991-3014,3079-3084,3161-3169` — CUDA/HIP のバッチ経路、適用条件、判定と診断行。
- `engine/sycl/src/prefill/prefill.cpp:1857-1874,1936-1942,2037-2057` — SYCL の同経路。
- `engine/include/strata/program/draft_kv_plan.hpp:25-42` — 単一 GPU / layer split でバッチ経路を試す条件。
- `engine/src/program/generate.cpp:14763-14798,24142-24149`、`engine/sycl/src/program/generate.cpp:8622-8627,13365-13370` — server / generate からの呼び出しと fallback。
- `engine/src/core/mtp.cpp:1832-1863,1865-1885,1936-1977,2043-2055` — MTP round 側の値判定、適用分岐、計測と出力。
