# `STRATA_ADAPT_NOWAIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

適応層（adaptive tier）が入れ替える expert のコピーについて、次の decode window の開始時に完了を待つかを切り替えます。有効時は、前の入れ替えコピーが未完了でも完了イベントを非同期に確認し、window の実行へ進みます。コピーが完了した時点で保留中の入れ替えを反映します。適応層自体の有効化は別設定 `--adapt-every` と `--adapt-swaps` が担います。

値の判定は CUDA と SYCL の `adapt_nowait()` にあり、結果は関数内の `static const bool` に一度だけ保存されます。実行中に環境を変更しても反映されません。CUDA の SM 6.0 / SM 8.6 では、後述のアーキテクチャ既定値によって起動時に値が設定される場合があります。

## 値と判定

環境変数の文字列全体や数値としての妥当性は調べず、先頭文字が `'1'` かだけを判定します。

| 状態 | `adapt_nowait()` の値 |
|---|---|
| 未設定 | `false`（ただし CUDA の SM 6.0 / 8.6 では既定値注入の可能性あり） |
| 空文字 | `false` |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | `true` |
| それ以外（例: `0`, `true`, ` 1`） | `false` |

大文字小文字、空白の trim、後続文字の検査、数値変換はありません。CUDA SM 6.0 / SM 8.6 の既定値処理では、環境変数が何らかの値（空文字を含む）で既に存在する場合はユーザー設定として保持されるため、空文字や `0` で既定の `1` を抑止できます。

## 有効になる条件

- 通常の適応層の入れ替えがある経路で使われます。適応層が無効、または保留中の入れ替えがなければ、非同期確認の対象はありません。
- `STRATA_ADAPT_LAG` とは選択関係です。有効時は `adapt_lag()` の値にかかわらず、window 前の処理で `apply_pending(false)` を呼びます。無効時は保留が空でない場合に経過 window 数を数え、`adapt_lag()` に達した時点で `apply_pending(true)` を呼びます。`STRATA_ADAPT_LAG` の既定は 1、値は `max(1, atoi(value))` です。
- `STRATA_ADAPT_OVERLAP` は `STRATA_ADAPT_NOWAIT` が有効、または `STRATA_ADAPT_LAG != 1` の場合に併用できず、CUDA の serve 経路では `not with STRATA_ADAPT_LAG / STRATA_ADAPT_NOWAIT` の理由で overlap を止めます。
- CUDA では非同期入れ替えに伴う residency table の同期が別途条件付きで設定されます。通常の serial window と適応層が有効な場合、`adapt_nowait()` または `STRATA_ADAPT_LAG > 1` なら `drive.d.evict_sync` が `adapt_evict_sync()` に従って設定されます。これにより、コピー中の evicted expert をデバイス側が resident と誤認しないよう、verifier の起動前に変更済み table entry を反映します。関連する `STRATA_ADAPT_EVICT_SYNC` は未設定なら有効、設定時は `atoi(value) != 0` の場合に有効です。したがって `0`、空文字、数値変換結果が 0 になる文字列は同期を無効化します。
- CUDA の `--batch-groups` と layer split の組み合わせでは同期アップロードによる待ち合わせを避けるため、verifier に全 activation を publish させる経路があります。`--pipeline-windows` は verifier が常時 publish し、tier が window を fence する経路として扱われます。

## 実行時の詳細

通常の decode window の直前に `apply_pending(false)` が呼ばれます。`wait == false` の場合、保留したコピーの CUDA event が未完了なら関数は待たずに戻ります。完了済みなら pin した領域を解放し、resident RAM mode の commit、host residency table の更新、必要な device table の upload を行い、保留状態を消去します。したがって `NOWAIT` はコピーを取り消したり、完了前に新しい residency table を確定したりする設定ではありません。

この窓の前処理は CUDA の通常 decode と serve の逐次 decode にあり、SYCL にも同じ値判定と通常 decode 前の非同期確認があります。CUDA batch serve の slot-row 経路は各 window 前に `apply_pending(false)` を無条件で呼ぶため、この変数による分岐はありません。`--adapt-async` の job step や pipeline の同期・fence もそれぞれ別の処理です。

CUDA では、適応層が evicted expert を host 側で非 resident にした直後、コピー完了まで device table の更新を遅らせると stale な residency 情報が問題になります。通常の serial windows では pre-launch hook が dirty entry を verifier stream 上の patch kernel で反映します。`STRATA_ADAPT_CHECKRES` が設定されている場合は、table の照合経路も構成されます。必要な device table 更新が失敗した場合は `the residency table update failed: ...` を返し、呼び出し側が window を失敗として扱います。

## CUDA のアーキテクチャ既定値

CUDA 起動時、可視 GPU の compute capability がすべて同一なら `apply_nv_defaults()` が実行されます。SM 8.6（RTX 30 系 / RTX A2000-A6000）と SM 6.0（Tesla P100）では、この変数と `STRATA_ADAPT_LAG=2` を含む switch set が既定で設定されます。`STRATA_SM86_PERF=0` または `STRATA_SM60_PERF=0` で該当 set を無効にできます（判定は先頭文字が `0`）。既に `STRATA_ADAPT_NOWAIT` が設定されていれば値を上書きせず、設定した名前を stderr の `strata: sm_86 (Ampere): ... exact speed switches on by default ...` または `strata: sm_60 (Pascal): ...` ログに含めます。従って同じ環境変数でも、CUDA の通常の未設定時とこれらの構成での未設定時は異なります。SYCL/HIP のこの関数には、この CUDA 既定値適用はありません。

## 根拠

- 値の parse と static cache、`STRATA_ADAPT_LAG` の parse: `src/program/generate.cpp:1506-1519`, `sycl/src/program/generate.cpp:1304-1317`。
- `STRATA_ADAPT_EVICT_SYNC` の既定と parse: `src/program/generate.cpp:1541-1545`。
- CUDA 起動時の既定値適用条件: `src/program/generate.cpp:2800-2815`。
- SM 8.6 / SM 6.0 の既定値、既存値の保持と `setenv` / `_putenv_s`: `src/core/nv_defaults.cpp:12-15,18-49,52-68`。
- serve の overlap が NOWAIT / LAG と併用不可である判定: `src/program/generate.cpp:9952-9969`。
- pending swap 完了時の更新、および lagged / nowait residency update の説明・条件: `src/program/generate.cpp:10024-10052,10054-10088,10105-10110,16000-16015`。
- window 直前の分岐: CUDA serve `src/program/generate.cpp:14773-14794`、CUDA generate `src/program/generate.cpp:16310-16316`、SYCL serve `sycl/src/program/generate.cpp:11487-11492`、SYCL generate `sycl/src/program/generate.cpp:12710-12715`。CUDA batch の無条件 nonblocking poll: `src/program/generate.cpp:11396-11403`。
- Strata の設計説明と測定条件: `docs/DETAILS.md:2006-2008,2425-2441`。SM 8.6 / 6.0 の測定は IQ3_XXS、RTX 3060 / RTX A4000 / Tesla P100、fresh engine、8 interleaved pairs と記載されています。ここでは性能値を一般化せず、コード上の挙動を説明しています。
