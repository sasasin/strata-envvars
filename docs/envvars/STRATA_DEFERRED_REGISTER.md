# `STRATA_DEFERRED_REGISTER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows で expert arena を開く際、GPU 用の host registration を読み込みより先に同期実行する代わりに、レイヤー単位でバックグラウンド登録し、登録とファイル読み込みを重ねる opt-in です。値が有効でも後述の条件を満たさなければ通常の arena 構築経路を使います。CUDA/HIP 実装と SYCL 実装の `ArenaExpertSource::open` が値を読みます（`engine/src/core/expert_source.cpp:6745-6759`、`engine/sycl/src/core/expert_source.cpp:3434-3449`）。

CUDA/HIP ではこの分岐は `by_need` の登録範囲選択を変えず、pin-by-need 経路の対象外です。SYCL では同じ Windows 条件で分岐しますが、CUDA 版と異なり `by_need` の条件はありません（同上）。この設定だけでは読み込む expert やモデルの出力選択を変えません。ソースコメントには RTX 5070 / Windows の測定として、従来順より decode が約 10% 遅く、出力は同一だったとの記載があります。これはその構成についてのコメントであり、他の環境での性能値ではありません（`engine/src/core/expert_source.cpp:6742-6747`、`engine/sycl/src/core/expert_source.cpp:3434-3439`）。

## 値と判定

両実装とも `std::getenv` の結果が null でなく、先頭文字が NUL でも `'0'` でもないとき `deferred` を true にします。文字列全体の比較、数値変換、空白除去はありません。したがって空文字・`0`・`0anything` は無効、`1`・`true`・`false`・` 0` は有効です。大文字小文字は変換されず、先頭文字だけで判定されます（`engine/src/core/expert_source.cpp:6748-6754`、`engine/sycl/src/core/expert_source.cpp:3440-3446`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| Windows で下記の適用条件を満たす | false | `1`, `true`, `false`, ` 0` | 空文字, `0`, `00`, `0anything` |
| Windows 以外 | 常に false（この変数を読む分岐なし） | なし | すべて（設定値は使われない） |

## 有効になる条件

- `_WIN32` でビルドされた実行経路であること。Windows 以外はコンパイル時に `deferred = false` となります（`engine/src/core/expert_source.cpp:6748-6754`、`engine/sycl/src/core/expert_source.cpp:3440-3446`）。
- `ArenaExpertSource::open` が arena を作る経路まで進むこと。Windows では `STRATA_ARENA_MMAP` による既存 mmap の早期 return は無効化されています（`engine/src/core/expert_source.cpp:6484-6523`、`engine/sycl/src/core/expert_source.cpp:3350-3388`）。
- 変数の値判定が true であること。
- CUDA/HIP では `by_need` が false、`max_pinned_bytes == 0`、`arena_pin_cap_gib() == -1`、`shared_arena_file` が空であること。pin-by-need、エンジンから渡された pin 上限、`STRATA_ARENA_PIN_GIB` による cap、共有 arena のいずれかがあるとこの変数による deferred 分岐は無効です（`engine/src/core/expert_source.cpp:6698-6715,6749-6759`）。
- SYCL では `max_pinned_bytes == 0`、`arena_pin_cap_gib() == -1`、`shared_arena_file` が空であること。同実装の条件式には CUDA/HIP の `by_need` 判定はありません（`engine/sycl/src/core/expert_source.cpp:3441-3449`）。
- `arena_pin_cap_gib()` は `STRATA_ARENA_PIN_GIB` を別途読み、未設定・空・`none`・負数などで `-1` を返すと条件を満たします。`auto` は `-2`、非負数はその値を返すため条件を満たしません。これは CLI 引数の優先順位ではなく、`open` に渡された `max_pinned_bytes` と別環境変数による条件です（`engine/src/core/pinned.cu:623-630`、`engine/sycl/src/core/pinned.dp.cpp:311-317`）。

## 実行時の詳細

値は `ArenaExpertSource::open` の分岐で都度取得され、関数内 static cache はありません。モデルの expert arena を開く時点で一度判定され、判定後にプロセス環境を変えても、その `open` の選択には反映されません。別の `open` 呼び出しでは再取得します（`engine/src/core/expert_source.cpp:6445-6449,6748-6759`、`engine/sycl/src/core/expert_source.cpp:3311-3315,3440-3449`）。

有効時は `PinnedArena::Deferred` を構築し、登録用スレッドを開始します。CUDA/HIP はデバイスを選んで `register_slices` を実行し、SYCL も現在の device id を選択して同関数を実行します。読み込み関数には `ready` の atomic を渡し、各レイヤーの書き込み前に対応スライスの登録完了を spin-yield で待ちます。読み込み完了後に登録スレッドを join します（`engine/src/core/expert_source.cpp:6755-6759,6821-6845,6276-6287`、`engine/sycl/src/core/expert_source.cpp:3447-3449,3474-3496,3146-3153`）。

CUDA の `register_slices` はレイヤーごとに登録し、失敗すると残りの領域を resident lock の対象にして `ready` を完了状態にします（`engine/src/core/pinned.cu:1295-1322`）。SYCL 側の同関数には「SYCL currently does not support registering of existing host memory」という DPCT コメントがあり、`cudaHostRegister` 相当の箇所は `if (0 != 0)` の到達不能分岐です。そのため、このコードは slice の bookkeeping と読み込み同期を行いますが、SYCL コードから host memory registration の実行は確認できません（`engine/sycl/src/core/pinned.dp.cpp:530-567`）。

arena の予約失敗時は `open` が false を返し、`ArenaExpertSource: the arena could not be reserved (...)` を `err` に設定します。読み込み失敗時は `ArenaExpertSource: the expert load was refused: ...`、読み込み byte 数不一致時は `ArenaExpertSource: the load read ...` を設定して false を返します（`engine/src/core/expert_source.cpp:6760-6766,6848-6858`、`engine/sycl/src/core/expert_source.cpp:3450-3456,3499-3507`）。

## ログと測定値

正常に読み込みが完了すると stderr に `strata generate: expert arena read unbuffered (...)` または `strata generate: expert arena read through the file cache (...)` が出ます。生成経路は arena の note も `strata generate: expert arena: %s` として stderr に出します。CUDA の deferred 経路では note に `cudaHostRegister per layer, pipelined with the load: N of M slices pinned` が含まれます（`engine/src/core/expert_source.cpp:6845-6853,8936`、`engine/src/core/pinned.cu:1309-1322`）。SYCL の note も同じ registered slice 数を記録しますが、前節のとおり SYCL 実装内の registration 呼び出しは到達不能です（`engine/sycl/src/core/pinned.dp.cpp:530-567`、生成経路 `engine/sycl/src/program/generate.cpp:4782`）。予約・読込失敗時は `open` が false と `err` を返します。`STRATA_DEFERRED_REGISTER` 固有の警告文やエラー文はありません。

測定値はソースコメントにある RTX 5070 / Windows の約 10% decode 低下・同一出力の記述のみです。測定回数やモデル・量子化条件はそのコメントに記載されていないため、一般化できません（`engine/src/core/expert_source.cpp:6745-6747`、SYCL 側にも同文 `engine/sycl/src/core/expert_source.cpp:3437-3439`）。

## 根拠

- `engine/src/core/expert_source.cpp:6445-6449,6698-6759,6821-6864` — CUDA/HIP の arena open、適用条件、登録と読み込み、失敗経路。
- `engine/sycl/src/core/expert_source.cpp:3311-3315,3434-3509` — SYCL の同等経路と読み込み結果。
- `engine/src/core/pinned.cu:623-630,1274-1322` — `STRATA_ARENA_PIN_GIB` の cap 判定と CUDA deferred slice 登録。
- `engine/sycl/src/core/pinned.dp.cpp:311-317,519-573` — SYCL の cap 判定と deferred slice 実装。
- `engine/src/program/generate.cpp:8936`、`engine/sycl/src/program/generate.cpp:4782` — expert arena note の stderr 出力。
