# `STRATA_DBG_CPU_GATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、prefill の CPU share 自動判定が行うレイヤー計測の診断行を `stderr` に出す。CPU share を有効化したり、CPU に割り当てる expert 数を決めたりはしない。出力される gate の値は計測後の `m.cpu_gate` であり、その値は後続レイヤーの CPU share 試行スケジュールに使われる。読み取りと出力は `engine/src/prefill/prefill.cpp` のレイヤー処理内にある（`5982-5986` 行）。

## 値と判定

値の内容は parse しない。`std::getenv(...) != nullptr` という設定有無だけを関数内 `static const bool` に保存し、設定されていれば出力を許可する（`engine/src/prefill/prefill.cpp:5982-5984`）。

| 条件 | unset | 設定されている値の例 | 無効になる値の例 |
|---|---|---|---|
| 共通 | 出力しない | 空文字、`0`、`1`、`true`、`false`、`0anything`、先頭・末尾に空白がある値はいずれも出力を許可 | なし（値文字列による無効判定はない） |

大文字小文字、数値形式、末尾文字を検証しない。値が `1` である必要はなく、空文字も「設定あり」と判定される。CPU share の実行設定 `STRATA_PREFILL_CPU_SHARE` はこの変数の値判定には使われず、後述のとおり診断箇所へ到達する条件を左右する（`engine/src/prefill/prefill.cpp:691-703, 5982-5984`）。

## 有効になる条件

- CUDA/HIP の prefill 実装で、CPU share 自動計測が有効なレイヤーに到達すること。この診断箇所は `cpu_maybe && cpu_share_env() < 0.0` の経路で計測を始めた場合に限られる。`STRATA_PREFILL_CPU_SHARE` の `auto`、または unset かつ既定 share が arm された状態が自動計測値 `-1` になる。明示的な数値 share（`0` を含む）では自動 gate 計測をしない（`engine/src/prefill/prefill.cpp:691-703, 3812-3868, 5895-5905`）。
- レイヤーが `cpu_maybe` を満たすこと: CPU pool を保持し、全 expert stream 経路ではなく、expert source と native layout / format があり、CPU share が停止済みでなく、peer GPU 使用中なら `STRATA_PF_PEER_CPU` による peer 併用が許可されていること（`engine/src/prefill/prefill.cpp:5876-5877, 705-714`）。
- そのレイヤーの計測が cold start でなく、stream 対象 expert があり、計測イベントの取得に成功して pending wall 計測が設定されること。次レイヤーの処理で `cudaEventElapsedTime` が成功した後に診断行が出る（`engine/src/prefill/prefill.cpp:5969-5986, 7610-7616`）。
- gate の自動計測を使うのは未指定時に既定 share が適用される構成、または `STRATA_PREFILL_CPU_SHARE=auto` などの自動 share 設定である。既定 share の arm は backend・GPU・prefill 経路に条件づけられている（CUDA 側は `arm_cpu_share`、HIP 側は対象 gfx 世代を判定。layer split には別条件がある）。この変数自体にサーバーモードや CLI 引数の優先規則はない（`engine/src/prefill/prefill.cpp:3812-3896`）。

## 実行時の詳細

関数内 static 値は、処理が `cudaEventElapsedTime` 成功後の診断分岐へ初めて到達した時点で一度評価され、以後そのプロセス内ではキャッシュされる。プロセス起動時に必ず読むわけではない。初回評価より後に環境値を変更しても、この static 判定には反映されない（`engine/src/prefill/prefill.cpp:5971-5984`）。

自動 share は eligible layer の wall time を計測し、同じ chunk 内で共有あり / なしの隣接 arm を比べた比率の中央値から `m.cpu_gate` を更新する。最初の 3 比率が集まるまでは arm を交互に試し、その後は gate 側を使いつつ 29 eligible layer ごとに反対側を probe する。診断行は直前に計測した layer の番号・共有の有無・non-resident expert 数・経過ミリ秒・expert あたり時間と、更新後の gate（`share` / `do not share`）を表示する（`engine/src/prefill/prefill.cpp:5895-5905, 5969-5989`）。

CPU share の有無は別の設定と適用条件で決まり、実際に CPU が担当する候補も routed row 数、resident / peer 状態、安定した expert blob の取得可否などで絞られる。この診断変数はその計算や CPU/GPU への割り当てを変更しない（`engine/src/prefill/prefill.cpp:6023-6057`）。明示 share や gate 計測の対象外経路では `pend_wall` が作られず、この診断行も発生しない。CLI とサーバーのどちらから呼ばれたかではなく、この prefill 実装の自動計測経路に到達したかで決まる。

## ログと測定値

有効な値がキャッシュされ、pending wall 計測の経過時間取得が成功すると、次の書式で標準エラーへ出力する（文字列は実装どおり）。

```text
cpu gate: layer %d %s, %lld non-resident, %.2f ms (%.4f a expert) -> %s
```

`%s` は共有有無の位置で `shared` または `not shared`、末尾で `share` または `do not share` になる。計測値は対象レイヤー・chunk・実行環境に依存する診断ログであり、この変数についての性能測定値は Strata の資料で確認できなかった（`engine/src/prefill/prefill.cpp:5982-5986`）。

## 根拠

- `engine/src/prefill/prefill.cpp:691-703` — `STRATA_PREFILL_CPU_SHARE` による unset / auto / 数値 share の判定。
- `engine/src/prefill/prefill.cpp:3812-3896` — default share の arm 条件と backend 差。
- `engine/src/prefill/prefill.cpp:5876-5905` — CPU share 対象レイヤー条件と自動計測の開始。
- `engine/src/prefill/prefill.cpp:5969-5989` — 計測値からの gate 更新、対象変数の読み取り、ログ。
- `engine/src/prefill/prefill.cpp:6023-6057, 7610-7616` — CPU share の expert 選定と計測対象 layer の設定。
