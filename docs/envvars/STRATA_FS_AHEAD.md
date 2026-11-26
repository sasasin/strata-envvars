# `STRATA_FS_AHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP の生成経路で、Foresight swap space が有効な場合に router look-ahead を cold source でも起動できるようにする条件を制御する。未設定時は有効。`0` はこの cold-source 起動条件を無効にするが、別条件（通常の warming source、または統計目的）で起動した look-ahead が swap space に接続されることまでは止めない。したがって、この値だけでは swap への予測 copy を一律に無効化しない（`engine/src/program/generate.cpp:10296-10303`, `engine/src/program/generate.cpp:14896-14899`, `engine/src/core/expert_source.cpp:3791-3793`）。

## 値と判定

生成処理で `std::getenv` の戻り値を `std::atoi` に渡し、未設定なら有効、設定済みなら変換値が 0 以外で有効とする。文字列全体の検証はせず、空文字・数値で始まらない文字列は `atoi` が 0 とする。先頭の空白や符号、数字以降の文字列は `atoi` の変換規則に従う（例: `"  +2x"` は 2、`"0x"` は 0）。負の非ゼロ値も有効。範囲チェックや clamp はない。`atoi` の int 範囲外入力の結果は保証されない（`engine/src/program/generate.cpp:10298-10299`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_FS_SLOTS` が正数で、`srcp` が存在 | 有効 | `1`, `-1`, `2tail` | 空文字, `0`, `0tail`, `false`, `tail` |
| `STRATA_FS_SLOTS` が未設定、0、負数、または `srcp == nullptr` | 無効 | なし | すべて（`STRATA_FS_AHEAD` の値にかかわらず） |

## 有効になる条件

- `srcp` が存在し、`STRATA_FS_SLOTS` が `atoi` で正数になり、かつ `STRATA_FS_AHEAD` が未設定または `atoi` で非ゼロであること。この条件で `fs_ahead` が true になり、通常は warming しない source でも look-ahead を起動する条件を満たせる（`engine/src/program/generate.cpp:10296-10303`）。swap space 自体は後段で `foresight_swap_from_env` が初期化する。
- `STRATA_LOOKAHEAD` が未設定か、設定値の `atoi` が非ゼロであること。設定済みの空文字や `0` は look-ahead の起動条件を止めるため、`STRATA_FS_AHEAD` が有効でも予測は行われない（`engine/src/program/generate.cpp:10288-10290`, `engine/src/program/generate.cpp:10302-10303`）。
- look-ahead の router 重みを全層から取得でき、各重みが `Bf16InF32` で期待 byte 数と一致し、device-to-host copy が成功すること。取得失敗時は look-ahead を起動しない（`engine/src/program/generate.cpp:10304-10318`）。
- `RouterLookahead::start` が `n_embd % 8 == 0` と各 router の形状を満たすこと。`fs_ahead` は cold source を許可する引数となり、通常なら warm しない source でも swap への予測用途で起動できる（`engine/src/program/generate.cpp:10319-10320`, `engine/src/core/expert_source.cpp:3534-3544`）。`STRATA_LOOKAHEAD_STATS` が非ゼロなら、別途統計目的でも cold source を許可する。
- `STRATA_VERIFY_DEVICE_PLAN` または `STRATA_VERIFY_DEVICE_HITS` が非ゼロだと swap space 初期化は拒否される。これらは look-ahead の起動と別判定であり、その場合 `fs_ahead` が true でも swap space へ接続されない（`engine/src/core/expert_source.cpp:7294-7305`）。
- ソース上でこの変数を読むのは `engine/src/program/generate.cpp` の CUDA/HIP 生成経路。SYCL と Metal の実装にはこの名前の読み取りがない。

## 実行時の詳細

`fs_ahead` は生成処理内で通常の bool として一度評価され、関数内 static cache はない。設定変更は次にこの判定を通る生成処理から反映される。判定が true なら、通常は warming しない source でも look-ahead 起動条件を満たせる。`STRATA_FS_AHEAD=0` ではこの経路がなくなるが、source が `warms()` する場合は別条件で look-ahead が起動し得る。また統計モードも cold source での起動条件となる。look-ahead が起動して swap space も作られた場合、`fs_swap && drive.d.lookahead != nullptr` だけで接続されるため、`fs_ahead` が false でも予測を swap space に渡し得る（`engine/src/program/generate.cpp:10302-10303`, `engine/src/program/generate.cpp:10328-10333`, `engine/src/program/generate.cpp:14896-14899`）。

look-ahead は前層の入力から次層 router を CPU で評価し、GPU cache にない top-k expert を選ぶ。`fs_ahead` が true のとき `lookahead.start(..., allow_cold_source=true)` となる。起動した look-ahead は swap space があれば接続され、次層の予測を `ForesightSwap::predict` に送り、source の pinned arena から swap slot への非同期 copy を要求する。この接続は `fs_ahead` の真偽を再確認しないため、通常の warming source や統計モードから起動した場合も同じである。slot の予測は実際の router 選択を変更せず、後の host-side plan が copy 完了済み slot を利用できる場合に限り GPU 側で処理する（`engine/src/program/generate.cpp:10319-10333`, `engine/src/program/generate.cpp:14887-14899`, `engine/src/core/expert_source.cpp:3791-3793`, `engine/include/strata/core/foresight_swap.hpp:76-84`）。

予測 copy が pinned arena の expert を得られない、budget 超過、利用可能 slot がない場合はその予測を採用しない。非同期 copy 失敗時は swap space が無効化され、slot は利用されない（`engine/src/core/expert_source.cpp:7146-7158`, `engine/src/core/expert_source.cpp:7229-7278`）。

## ログと測定値

look-ahead の起動時は stderr に `strata generate: routing-aware prefetch on (the next layer's router%s)` の形式で出る。ここで suffix は `fs_ahead` が true なら `, feeding the Foresight swap space`、false なら `, file tier` になる。ただし後者の表示でも、warm source 等から起動した look-ahead は swap space に接続され得るため、この文言だけでは接続の有無を表さない。swap space 初期化成功時は slot 数・card 数・copy budget 等の `strata serve: foresight swap: ...` 行が出る。router 重みが BF16 でない、取得・形状条件を満たさないなどで look-ahead が起動しない場合は `strata generate: routing-aware prefetch off (...)` が出る。device-plan/hits 検証との併用時は `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN/HITS (the device would plan resident layers without the host)`、copy 失敗時は `strata serve: foresight swap: a copy failed - swap space off` が出る（`engine/src/program/generate.cpp:10328-10338`, `engine/src/core/expert_source.cpp:7151-7155`, `engine/src/core/expert_source.cpp:7301-7304`, `engine/src/core/expert_source.cpp:7318-7320`）。この変数単独の測定値はソースから確認できない。

## 根拠

- `engine/src/program/generate.cpp:10288-10338` — look-ahead と `STRATA_FS_AHEAD` の判定、起動条件、起動・停止ログ。
- `engine/src/program/generate.cpp:14887-14907` — swap space の生成と look-ahead/source への接続。
- `engine/src/core/expert_source.cpp:3534-3551` — look-ahead 起動条件。
- `engine/src/core/expert_source.cpp:3791-3793` — swap space への予測。
- `engine/src/core/expert_source.cpp:7146-7158`, `engine/src/core/expert_source.cpp:7223-7278`, `engine/src/core/expert_source.cpp:7294-7321` — slot copy、失敗処理、swap space の有効条件とログ。
- `engine/include/strata/core/foresight_swap.hpp:76-84` — slot が実際の expert 選択を決めず、先読み copy に使われること。
