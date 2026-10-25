# `STRATA_TEST_PIN_LEFT_KIB`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

これは通常利用者向け設定ではなく、ピン留めメモリ上限のテスト用ノブです。expert arena の読み込みが終わった時点で、シミュレーション上の上限を「その時点で計上済みの量 + 指定 KiB」に設定します。arena 以後の必須 pinned buffer の確保失敗や再試行を、より小さい余裕で発生させるために使えます。

この変数だけでは何も変わりません。先に `STRATA_TEST_PIN_BUDGET_MIB` でシミュレーション上限を有効にする必要があります。上限は Strata のピン留め用 wrapper を通る確保・登録にだけ適用されます。

## 値と判定

| 状態 | 動作 |
|---|---|
| `STRATA_TEST_PIN_BUDGET_MIB` が未設定、空、または数値変換後に 0 | `sim_budget` が 0 のままなので、この変数は無視される |
| `STRATA_TEST_PIN_LEFT_KIB` が未設定または空文字 | arena 後も既存のシミュレーション上限を維持 |
| 空でない値 | `strtoull(value, nullptr, 10)` の結果を KiB として 1024 倍し、arena 後の `sim_used` に加えた値を新しい上限にする |

文字列全体や範囲の検証はありません。10進数として読める先頭部分を変換し、後続の非数字は無視します。数値に変換できない文字列は 0 として扱われます。符号や空白も `strtoull` の規則で受け付けられ、負値を拒否する処理や上限 clamp はありません。計算は `uint64_t` に格納してから 10 ビット左シフトするため、非常に大きい値では unsigned 整数の範囲で折り返します。

空でない `0` は有効な指定です。この場合、新しい上限が現在の `sim_used` と等しくなり、それ以後の正のサイズのシミュレーション確保・登録は上限超過になります。

## 有効になる条件

- `STRATA_TEST_PIN_BUDGET_MIB` により初期 `sim_budget` が 0 以外になっていること。
- `generate` の expert arena 起動経路で arena の読み込みが実行され、`pin_note_arena()` が呼ばれること。
- その呼び出し時点で `STRATA_TEST_PIN_LEFT_KIB` が空でないこと。

`sim_budget` は最初の `pin_detail::st()` 呼び出し時に `STRATA_TEST_PIN_BUDGET_MIB` から初期化される一方、この変数は arena 読み込み後の `pin_note_arena()` 呼び出し時に読み取られます。そのため、後者の値は arena 後のその時点で反映されます。ソース上の呼び出しは `generate.cpp` の起動経路に1箇所です。

## 実行時の詳細

`generate` は arena を開いた直後に `pin_note_arena(arena_src.pinned_arena_bytes())` を呼びます。`sim_budget != 0` かつこの変数が空でない場合、そこで `sim_budget = sim_used + (指定値 << 10)` に更新されます。直後のシミュレーション報告は stderr に `strata: test pinned budget ...` を出します。`STRATA_TEST_PIN_BUDGET_MIB` が無効なら、報告も出ません。

更新後は `pin_register()` や `host_alloc_guarded()` などが新しい上限を参照します。expert arena のスライス登録はシミュレーション上限を超えると失敗扱いとなり、arena 実装は残りを resident lock にする経路へ進みます。必須 pinned buffer の確保が拒否された場合、保持中の reserve を解放して一度だけ再試行します。これらのシミュレーションがどの実際の OS/driver の上限を再現するかは、この変数のコードだけからは保証されません。

値は環境から読み取った後に保存されず、`pin_note_arena()` が呼ばれるごとに評価されます。ただし通常の `generate` 起動経路では呼び出しは一度です。

## 根拠

- 初期シミュレーション上限の取得と `State` の遅延初期化: `include/strata/core/pin_budget.hpp:38-58`。
- ピン登録・確保がシミュレーション上限を検査: `include/strata/core/pin_budget.hpp:61-81,100-117,191-209`。
- arena 後の上限更新と stderr 報告: `include/strata/core/pin_budget.hpp:171-188`。
- arena 起動、`pin_note_arena()`、soft reserve の解放: `src/program/generate.cpp:5800-5811`。
- arena の登録失敗からスライス登録・残りの resident lock へ進む処理: `src/core/pinned.cu:445-490,626-645`。
- 必須 mapped buffer が guarded allocation を通る例: `src/core/verify.cpp:414-426`。
- `docs/DETAILS.md:223-224` はこの変数を「arena 後に上限を残り N KiB に下げる」テストノブとして記載しています。実装では先行する `STRATA_TEST_PIN_BUDGET_MIB` が非ゼロでなければこの調整は行われないため、その前提も含めて読む必要があります。
