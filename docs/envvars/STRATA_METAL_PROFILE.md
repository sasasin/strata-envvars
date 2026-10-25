# `STRATA_METAL_PROFILE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal エンジンの処理時間内訳を stderr に出します。window ごとの処理時間、prompt 処理の集計、commit と draft の所要時間が対象です。Metal エンジン用の計測・診断フックで、通常のモデル計算の分岐を切り替える設定ではありません。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |

実装は値を文字列や数値として parse せず、`std::getenv("STRATA_METAL_PROFILE") != nullptr` で設定有無だけを判定します。したがって `0` や `false` も有効です。値を読む箇所の一部は初回呼び出し時に `static` へ保存されます。

## 有効になる条件

この環境変数を読む実装は `metal/src/engine/` にあります。従って Metal エンジンの経路でのみ、ここに記した profile 出力が行われます。`docs/MAC.md` も `STRATA_METAL_TRACE`、`STRATA_METAL_PROFILE`、`STRATA_METAL_KPROF` を Metal の per-window 計測として挙げています。

## 実行時の詳細

- `Window::finish()` は最初の呼び出し時に設定有無を `static const bool` に保存します。有効なら window のサイズと head 有無ごとに計数し、window 全体、host 前処理、`run_graph`、GPU 時間、patch/finish の時間を累積します。この判定後にプロセス内で環境を変更しても、この累積処理の判定には反映されません。
- `Window` のデストラクタはその時点で環境変数を再確認します。有効なら累積した window、commit、draft の統計を stderr に出します。window の行は `strata metal profile: ...` で始まり、呼び出し数と平均時間を表示します。window 集計は `finish()` で profile が有効と判定された分に限られます。commit/draft の時間は `window_commit()` と `mtp_draft()` で計測・累積され、表示自体はデストラクタ時点で環境変数が設定されている場合に限られます。
- `Window::prompt()` は各 prompt 呼び出しの終わりに、この変数または `STRATA_METAL_TRACE` の設定有無を確認します。どちらかが設定されていれば stderr に入力 token 数、全体・GPU・host rows・drafter rows の時間と tok/s を出します。この判定は `Window::finish()` の static 判定とは別で、prompt ごとに行われます。

環境変数を設定すると計測値が追加出力されます。ここで確認したコードは時間を測定・表示するもので、性能改善や token の変化を保証するものではありません。

## 根拠

- `metal/src/engine/window.cpp:315-322` — profile 集計の構造と commit/draft 用 accumulator。
- `metal/src/engine/window.cpp:1302-1317` — デストラクタでの設定有無の確認と profile 出力。
- `metal/src/engine/window.cpp:1319-1329` — window 計時の static 設定判定と集計項目。
- `metal/src/engine/window.cpp:2508-2512,2593-2599` — commit と draft の計時・集計。
- `metal/src/engine/prompt_chain.inc:394-419` — prompt 処理の profile/trace 条件と stderr 出力。
- `docs/MAC.md:201-205` — Metal engine の診断環境変数と実装位置の説明。
