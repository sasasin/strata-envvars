# `STRATA_SYCL_BMG_EXPERT_WINDOW`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL generate の対象経路で、Battlemage の routed-expert prefill を隣接する最大 2 chunk 単位で処理する expert-window の利用可否を設定する。window 経路では同じ expert の圧縮 weight を隣接 chunk 間で共有する。window を使わない場合も、`STRATA_SYCL_BMG_ROUTED_EXPERTS` が有効なら通常の routed-expert grouping などは別に選択され得る。この変数自体は routed-expert 処理全体を無効にしない（`engine/sycl/src/prefill/prefill.cpp:4806-4810,4832-4840,5819-5835`）。

この値を読むのは `strata::bmg::window_mode()` で、起動時に `configure_bmg_window()` が設定を確認する。適用対象は `engine/sycl/src/program/generate.cpp` の SYCL generate 経路であり、モデル、キュー、build、実行形態が条件を満たす場合に限る（`engine/sycl/src/program/generate.cpp:4312`; `engine/sycl/src/prefill/prefill.cpp:5819-5835`）。

## 値と判定

共通 helper は `std::getenv()` で設定有無を判定し、設定があれば文字列全体を `std::strcmp(value, "1")` で比較する。未設定は `Auto`、完全一致する `1` だけ `Enabled`、設定されたそれ以外は `Disabled` になる。数値変換や trim、大文字小文字を無視する処理はない（`engine/sycl/src/bmg_prefill_options.hpp:8-14,21-24`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の Battlemage window 設定 | `Auto`。他の条件がそろえば window を許可する | `1`（文字列全体が完全一致） | 空文字、`0`、`true`、`01`、`1 `、` 1`、その他すべて。いずれも `Disabled` |

設定値が `Disabled` の場合、window device を false にして初期化を終える。未設定の `Auto` と `1` の `Enabled` はどちらも先の適用条件の検査へ進む。値は `window_mode()` 内の関数 static に初回呼び出し時キャッシュされ、同じプロセス内での環境変更は反映されない（`engine/sycl/src/bmg_prefill_options.hpp:21-24`; `engine/sycl/src/prefill/prefill.cpp:5819-5823`）。

## 有効になる条件

- `configure_bmg_window()` は SYCL generate の session 初期化後に一度呼ばれる。呼び出し条件の `single_unbatched` は、multi-GPU でなく、stage 分割が空で、`o.batch <= 0` の場合に限り true（`engine/sycl/src/program/generate.cpp:4312`）。
- `STRATA_SYCL_BMG_ROUTED_EXPERTS` が無効でないこと。こちらも同じ tri-state helper を使い、未設定は許可、文字列全体が `1` 以外の設定は無効として扱う。無効なら window は拒否される（`engine/sycl/src/bmg_prefill_options.hpp:10-18`; `engine/sycl/src/prefill/prefill.cpp:5821-5825`）。
- build に `STRATA_HAS_TLA_EXPERT_GU` が定義されていること。SYCL CMake は TLA expert kernels を有効にした場合にこの macro を定義し、対象構成は Level Zero と portable または Battlemage target に制限される（`engine/sycl/CMakeLists.txt:340-373`）。macro がない build では window を拒否する（`engine/sycl/src/prefill/prefill.cpp:5826-5832`）。
- 選択 queue が in-order の Level Zero queue で、GPU 世代判定が Battlemage であること（`engine/sycl/src/prefill/prefill.cpp:5828-5832`）。
- 実際の paired window には streamed expert source と native expert layout が必要。layout は 48 層すべてで `had_gu` / `had_d` が false、down type が 42、embedding 幅 2560、feed-forward 幅 640、gate/up type が 16 / 22 / 29 であることを要求する（`engine/sycl/src/prefill/prefill.cpp:1313-1321`）。
- paired window の chunk は 8192 token、expert 数は 512。TLA build があり、fused layout と MMQ plan がなく、XMX mode が 0、`STRATA_DBG_NAN` が未設定、ring bytes が有効で cvec が未ロードであることも必要（`engine/sycl/src/prefill/prefill.cpp:1306-1311,1323-1325`）。
- 実行時には prompt span が chunk より長く、expert cache が全層全 expert を保持せず、window workspace が確保されていることに加え、prefill-first / NaN 診断 / residual dump が無効で、active stage や tap がなく、通常の prefill stage 全体を処理する必要がある。これらを満たさない場合は paired window を走らせず通常の `run()` に進む（`engine/sycl/src/prefill/prefill.cpp:5842-5848,5945-5956`）。
- 値が `1` でも、上記条件が不足すると window は実行されない。未設定 Auto の場合も同じ適用条件を使う。条件不足理由を configure 時に警告するのは明示 `1` の場合だけ（`engine/sycl/src/prefill/prefill.cpp:5821-5835`）。

## 実行時の詳細

設定は configure 時に確認され、`SessionState::bmg_window_device` に保存される。`generate.cpp` の `read_part` はこの flag が true で、現在の処理が piped でなければ `Prefill::run_expert_window()` を呼び、そうでなければ通常の `run()` を呼ぶ（`engine/sycl/src/program/generate.cpp:4312,11446-11456`）。値そのものは helper 内 static cache であり、リクエストごとに読み直さない。

実行可能な span は 8192 token 単位で走査され、次の chunk に少なくとも 4096 token 残り、checkpoint または保存する tail の境界にかからない場合に 2 chunk を組にする。それ以外は 1 chunk ずつ進む。組にした場合は各層で両 chunk の routed rows をまとめ、expert ごとに weight を一度ロードして projection に使う。window 中の処理が失敗すると `run_expert_window()` は false を返し、そこから通常実行へ切り替える fallback ではなく呼び出し元へ失敗を返す（`engine/sycl/src/prefill/prefill.cpp:5877-5924`; `engine/sycl/src/prefill/bmg_expert_window_walk.tpp:33-72,145-220`）。

window が選ばれないときは `run_expert_window()` が通常の `run()` を実行する。明示 ON または `STRATA_TRACE` 設定時には、fallback の理由をその `Prefill::Impl` 内で一度だけ stderr に出す（`engine/sycl/src/prefill/prefill.cpp:786,5945-5956`）。configure に serve 専用の分岐はなく、server mode でも同じ実行条件が適用される。window flag は CLI 引数で直接上書きされず、CLI の batch / split 状態は適用条件として使われる。

## ログと測定値

明示 `STRATA_SYCL_BMG_EXPERT_WINDOW=1` で configure 条件が満たされない場合、stderr に次の形式で出る。reason は順に routed experts 無効、split/batched execution、TLA kernels 未 build、選択 queue が in-order Level Zero Battlemage でないことを示す（`engine/sycl/src/prefill/prefill.cpp:5821-5835`）。

```text
strata: expert window disabled: <reason>
```

paired window が実際に始まると、プロセス内最初の一度だけ stderr に次を出す。`STRATA_TRACE` は値の内容ではなく `getenv()` の設定有無で判定され、空文字でも設定すれば chunk 長を示す trace が出る（`engine/sycl/src/prefill/prefill.cpp:5877-5878,5891-5898`）。

```text
strata: Battlemage prefill uses two adjacent chunks per expert window
strata trace: expert window pos=<位置> chunks=[<長さ>[,<長さ>]]
```

実行時条件で paired window が選べず、明示 ON または `STRATA_TRACE` が設定されていれば、stderr に次の形式で理由を一度だけ出す。具体的な reason 文字列は chunk plan、streaming、expert geometry/formats/workspace、prompt span、active stage / diagnostic / workspace の状態で決まる（`engine/sycl/src/prefill/prefill.cpp:5945-5954`）。

```text
strata: expert window skipped: <reason>
```

参照した Strata 資料には機種・設定・測定条件つきの性能値はなく、ここでは測定値を記載しない。

## 根拠

- `engine/sycl/src/bmg_prefill_options.hpp:8-24` — 値の tri-state 判定、関連 routed-experts 設定、static cache。
- `engine/sycl/src/program/generate.cpp:4312,11446-11456` — configure 呼び出しと prefill 実行時の window 選択。
- `engine/sycl/src/prefill/prefill.cpp:1303-1325,5819-5956` — build / device / model / runtime 条件、pair 処理、ログ、通常実行への fallback。
- `engine/sycl/src/prefill/bmg_expert_window_walk.tpp:5-16,33-72,145-229` — paired window 内の expert weight・projection 処理。
- `engine/sycl/CMakeLists.txt:340-373` — TLA expert kernels の build 条件と `STRATA_HAS_TLA_EXPERT_GU` 定義。
