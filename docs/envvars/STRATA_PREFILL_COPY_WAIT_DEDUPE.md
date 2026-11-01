# `STRATA_PREFILL_COPY_WAIT_DEDUPE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

この opt-in は、prompt prefill の expert copy stream が staging slot を再利用するとき、前の entry と同じ release event を待てばよい場合に、連続する entry の二度目以降の `cudaStreamWaitEvent` を省略します。対象は `Prefill::run_impl()` の `stream_all` 経路で threaded issuer が動く場合です。省略対象は slot の再利用待ちだけで、expert のコピー、copy 済み event、compute stream 側のコピー完了待ちは引き続き行われます。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果が 0 以外なら有効です。文字列全体を検証する parser ではないため、数値として先頭から変換できる部分が 0 以外なら有効になり、変換できない文字列や空文字は 0 になります。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | `atoi("") == 0` のため無効 |
| `0`、`00`、`0text`、数値に変換できない文字列 | 無効（変換結果 0） |
| `1`、`-1`、`2` など、`atoi` の結果が非 0 の文字列 | 有効 |

値に範囲制限、clamp、CLI 引数や設定ファイルとの優先順位はありません。この変数の判定は関数内 `static const bool` に保存されるため、宣言に初めて到達した時点で一度だけ読み取られ、以後プロセス内で環境を変更しても再評価されません（`src/prefill/prefill.cpp:3486-3489`）。

## 有効になる条件

値が有効でも、次の条件を満たさなければ release wait は省略されません。

- CUDA/HIP GPU prefill の通常の `run_impl()` 経路を通ること。Metal の `Prefill::run()` は `prompt_run()` を呼び出して戻るため、この経路の判定には到達しません（`src/prefill/prefill.cpp:7222-7232,7271`）。
- `stream_all` が真であること。これは `m.ring > STAGE`、prompt chunk の token 数 `T >= stream_all_min()`、expert source が存在することを要求します。`STAGE` は 8 です（`src/prefill/prefill.cpp:176,3328-3332`）。
- `STRATA_PREFILL_ISSUER` が inline 発行を選んでいないこと。`issuer_on` は同変数が未設定なら真、設定時は `atoi` が非 0 の場合だけ真です。threaded issuer は `stream_all && issuer_on` のときだけ動きます（`src/prefill/prefill.cpp:3459-3462,3473`）。
- 対象 slot が既使用（`m.stage_live[sl]`）であり、helper の `copy_wait_dedupe_ok()` が真を返すこと。判定条件は ring slot 数が MMQ group サイズより大きい（`m.ring > 16`）、現在の entry index が ring を超えている（`idx > m.ring`）、現在と直前の release event index が同じ（`rel == prev_rel`）のすべてです。直前 entry が未使用 slot なら `prev_rel` を `-1` に戻すため、その直後も省略できません（`include/strata/prefill/copy_events.hpp:35-42`, `src/prefill/prefill.cpp:1304,3529-3545`）。

省略条件を満たさない再利用では通常どおり `cudaStreamWaitEvent(m.copy, m.used[rel], 0)` をキューに入れます。`STRATA_PREFILL_COPY_EVENT_EVERY` は copy-done event の記録頻度と compute 側の待ち先を制御する別設定で、この release wait の dedupe 可否には使われません（`src/prefill/prefill.cpp:3482-3490,3535-3556`）。

## 実行時の詳細

threaded issuer は entry を順番に発行し、entry index を ring slot 数で割った余りを staging slot として使います。slot が再利用済みの場合、dedupe 条件が成立すれば待ちを省いて `iss_dedup` を増やし、成立しなければ `m.used[rel]` を待って `iss_waits` を増やします。その後どちらの場合も expert blob の H-to-D copy を enqueue し、`m.copied` event を記録するか sparse event の記録規則に従います（`src/prefill/prefill.cpp:3525-3560`）。

判定が有効で threaded issuer が動くと、最初の該当 prefill 経路で stderr に `strata: prompt copies: a copied event every ... (STRATA_PREFILL_COPY_EVENT_EVERY), one wait per release event (STRATA_PREFILL_COPY_WAIT_DEDUPE)` を一度出します。この文言は設定が有効なことを示し、実際に一回以上 wait を省略したことまでは示しません（`src/prefill/prefill.cpp:3490-3498`）。`STRATA_PREFILL_TIMING` が設定されている場合は、issuer join 後に stderr に総 slot waits と同じ release event として省略した数を出します（`src/prefill/prefill.cpp:5624-5632`, timer の有効条件は `src/prefill/prefill.cpp:2731-2748`）。

この設定固有の無効値警告や終了経路はありません。copy stream の同期に失敗した場合、`run_impl()` は `prefill: expert copy stream: <CUDA/HIP runtime error>` を `err` に設定して false を返します（`src/prefill/prefill.cpp:5762-5769`）。`Prefill::run()` は body または pipeline drain の失敗を false として返します（`src/prefill/prefill.cpp:7271-7280`）。これらは copy stream 全般のエラー経路であり、この環境変数が原因だとはコードだけから特定できません。

## 根拠

- 候補名の読み取りは `src/prefill/prefill.cpp:3486-3489` の一箇所です。`rg` で候補名の全参照を調べ、他の参照は同ファイルの説明・ログと `include/strata/prefill/copy_events.hpp` のコメントでした。
- threaded issuer と親条件: `src/prefill/prefill.cpp:3328-3332,3459-3473`。
- wait の分岐および省略条件: `src/prefill/prefill.cpp:3529-3545`, `include/strata/prefill/copy_events.hpp:35-42`。
- 設定・実動作ログと計数ログ: `src/prefill/prefill.cpp:3490-3498,5624-5632`。
- `docs/DETAILS.md` と既存の設計資料には、この変数の追加仕様や性能値の記載を確認できませんでした。性能向上や生成結果への影響は本調査では測定していません。
