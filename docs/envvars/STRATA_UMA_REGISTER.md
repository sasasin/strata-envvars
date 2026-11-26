# `STRATA_UMA_REGISTER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP で認識した統合 GPU の一部環境で、expert arena を GPU driver に登録しない自動既定を抑止する。`STRATA_UMA_REGISTER` 自体が登録を呼ぶのではなく、`1` で始まる値を検出すると Strata が「自動では未登録にしない」分岐を選ぶ。実際の arena 登録・常駐ロック経路は `PinnedArena` が担う（`engine/src/core/arch_defaults.cpp:140-150`、`engine/src/program/generate.cpp:4320-4351`、`engine/src/core/pinned.cu:611-620,1054-1085`）。

この既定は Windows の統合 gfx1151（Strix Halo）と、Linux HIP の KFD NOREG 対象である gfx1103（Radeon 780M/同系統）で別々に設定される。前者は `igpu_uma_arena_default`、後者は Linux 専用の `kfd_quiet::noreg_default` を通る。CUDA build や対象外 GPU で、この変数が登録を強制する処理はない（`engine/src/program/generate.cpp:4287-4329,4337-4351`、`engine/include/strata/core/kfd_quiet.hpp:104-109,214-225`）。

## 値と判定

両読み取り箇所とも `std::getenv` の結果が null でないことに加え、`value[0] == '1'` を判定する。文字列全体の比較・数値変換・空白除去はしない。よって `1`, `1anything` は抑止条件に一致し、`0`, `0anything`, `true`, ` false`, 空文字、未設定は一致しない。大文字小文字は比較対象外で、先頭が文字 `'1'` かだけが関係する（`engine/src/core/arch_defaults.cpp:142-143`、`engine/include/strata/core/kfd_quiet.hpp:106-109`）。

| 経路 | 未設定・空文字・先頭が `'1'` でない値 | 先頭が `'1'` の値 |
|---|---|---|
| HIP / Windows / 統合 gfx1151 | 自動で未登録にする | その自動既定を抑止 |
| HIP / Linux / NOREG 対象（全 KFD GPU node が gfx1103） | KFD quiet の NOREG switch が有効なら未登録にする | NOREG を抑止 |
| その他の GPU / build | この変数による自動未登録なし | 登録を強制する効果もなし |

Windows gfx1151 の条件と Linux NOREG の条件は、`engine/src/core/arch_defaults.cpp:140-150`、`engine/src/program/generate.cpp:4337-4351`、`engine/include/strata/core/kfd_quiet.hpp:104-109,214-225` による。

## 有効になる条件

- `generate` の HIP build で、GPU 0 のプロパティ取得に成功する必要がある。iGPU 判定は device property の `integrated` による。自動既定の呼び出しは `generate.cpp` の HIP 条件ブロック内にある（`engine/src/program/generate.cpp:4287-4295,4320-4329`）。
- Windows では統合 gfx1151 のとき、値が `'1'` で始まらなければ未登録の既定が選ばれる。ほかの Windows GPU ではこの既定は選ばれない（`engine/src/core/arch_defaults.cpp:140-149`）。
- Linux の NOREG は `STRATA_USE_HIP && __linux__` 経路でのみ評価される。さらに `igpu_kfd_settle_default` が true になる統合 GPU 構成（全可視 GPU が統合 GPU で同一 gfx arch）で、KFD topology の GPU node が少なくとも 1 個あり、全 node が gfx1103 のとき対象クラスになる。gfx1150/gfx1151 や別 GPU node を含む構成は NOREG 対象外（`engine/src/program/generate.cpp:4295-4302,4337-4349`、`engine/src/core/arch_defaults.cpp:159-160`、`engine/include/strata/core/kfd_quiet.hpp:214-225`）。
- Linux NOREG はさらに `STRATA_KFD_QUIET` と `STRATA_KFD_QUIET_NOREG` の switch が有効である必要がある。どちらかが `'0'` で始まると無効、それ以外（未設定・空文字を含む）は有効。したがって `STRATA_KFD_QUIET=0` または `STRATA_KFD_QUIET_NOREG=0` でも未登録既定を止める（`engine/include/strata/core/kfd_quiet.hpp:47-52,106-109`）。
- `STRATA_ARENA_PIN_GIB` は最終的な arena mode を優先する。空でない値が `none` と完全一致すれば未登録、空でないそれ以外の値なら登録側を選ぶ。未設定・空文字なら engine の既定 flag に従う。このため `STRATA_UMA_REGISTER=1` でも `STRATA_ARENA_PIN_GIB=none` があれば未登録のまま。一方、`STRATA_ARENA_PIN_GIB=0` や `N` は登録側になる（`engine/src/core/pinned.cu:611-620`、`engine/include/strata/core/kfd_quiet.hpp:111-115`）。

## 実行時の詳細

`generate` は HIP build で GPU 情報を取得後、`igpu_uma_arena_default` を呼び、true なら `arena_uma_no_register_flag` を立てる。Linux の対象経路では続いて KFD topology を調べ、`noreg_default` が true なら同じ arena flag と `noreg_flag` を立てる（`engine/src/program/generate.cpp:4287-4329,4337-4351`）。Windows gfx1151 の `igpu_uma_arena_default` は `on` 引数に関わらず既定を適用する。一方 Linux gfx1103 の同関数の `on` は既定 false だが、Linux NOREG は別の条件で判断される（`engine/include/strata/core/arch_defaults.hpp:52-58`、`engine/src/core/arch_defaults.cpp:140-150`）。

対象変数はこの起動時の判定で読み取られ、arena 作成時に再読されない。arena 側は `STRATA_ARENA_PIN_GIB` と engine flag から登録状態を決める。Linux HIP で NOREG が選んだ未登録経路では、別途 `STRATA_ARENA_LOCK` の設定に従ってロックするかを判断するが、NOREG の既定ではロックしない（`engine/include/strata/core/kfd_quiet.hpp:111-123`、`engine/src/core/pinned.cu:611-620,1054-1085`）。対象変数の読み取り値を static cache する実装はなく、実行中に環境値を書き換えても、すでに設定された起動時 flag の判定は変わらない。

`STRATA_UMA_REGISTER` は CLI 引数より優先する設定ではなく、対応する `--register` 等の CLI 引数はこの経路にない。モデル／arena を使わない経路では arena の登録動作も発生しない。登録されない場合、Strata は arena note に `NOT registered with the GPU driver (integrated GPU, UMA mode; STRATA_ARENA_PIN_GIB=0 registers it); ` を付け、`generate.cpp` が `strata generate: expert arena: ...` として stderr に出す。Linux NOREG が選ばれた場合は `STRATA_TRACE` が設定されていれば `strata trace: kfd quiet: expert arena not registered with the driver, no mlock (...)` も出る（`engine/src/core/pinned.cu:1084`、`engine/src/program/generate.cpp:4352-4354,8934-8936`）。この変数専用の警告・エラー・終了経路は確認できない。

## 根拠

- `engine/src/core/arch_defaults.cpp:140-150` — `STRATA_UMA_REGISTER` の先頭文字判定と統合 GPU の自動既定。
- `engine/src/program/generate.cpp:4287-4329,4337-4354` — HIP build での GPU 条件判定、engine flag の設定、Linux NOREG 判定と trace ログ。
- `engine/include/strata/core/kfd_quiet.hpp:47-52,104-123,214-225` — KFD switch の値判定、NOREG helper、arena mode 優先規則、対象 topology。
- `engine/src/core/pinned.cu:611-620,1054-1085` — engine flag と `STRATA_ARENA_PIN_GIB` による最終的な未登録判定、未登録時の arena note。
- `engine/src/program/generate.cpp:8934-8936` — arena note の stderr 出力。
