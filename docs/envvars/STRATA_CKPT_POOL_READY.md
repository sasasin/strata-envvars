# `STRATA_CKPT_POOL_READY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

serve 中の checkpoint pool に、次の checkpoint 保存で再利用するための「ready checkpoint」を何個まで先行確保するかを指定する。ready checkpoint は現在の session state と同じ大きさの host vector を持ち、保存時の vector resize と未使用ページの初回 fault を避けるために使われる。保存内容を変える設定ではない。pool 内に ready checkpoint がなければ、通常の新規 vector で保存する。値は `generate.cpp` の `ckpt_pool_ready_env()` が読み、serve loop の `pool_topup` と `CheckpointPool` に反映される（`engine/src/program/generate.cpp:516-531, 14139-14171, 14512-14530`）。

## 値と判定

`std::getenv` の結果を関数内 `static const long` に一度保存し、設定されていれば `std::atol` で変換する。文字列全体の検証はしない。`atol` が読める先頭の整数部分を使い、後続文字を無視するため、空文字や先頭が数値でない文字列は `0` になる。未設定は内部 sentinel の `-1` になる。読み取り後、負数は engine default の値を返し、0 以下（負数を除く）は ready 数 0、正数は最大 16 に clamp される（`engine/src/program/generate.cpp:522-529`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常の判定 | engine default を参照。自動 pool が有効なら `park_pool_plan` の値（cache の 1/12 に入る数、最大 4）、それ以外は 0。 | `1`〜`16`。`17` 以上も 16 に clamp。前後の空白や `+` の後に数字があればその数を使う。`2tail` は 2。 | 空文字、`true`、`x2`、`0anything` は 0。`-2` など負の数は 0 ではなく engine default に戻る。大文字小文字や末尾文字の検証はない。 |
| Strata の起動時 default 注入が適用された場合 | 注入後の値を設定値として読む。対象の parallel-request default では `4`。 | ユーザーが設定済みならその値を保持する。空文字も「設定済み」なので注入されず、上記の通り 0 と判定される。 | — |

`STRATA_CKPT_POOL_READY` 自体に範囲エラーや警告を出す処理はない。なお、`atol` の変換範囲外の入力について Strata は `errno` 等を検査していないため、動作を個別に保証できない。値を指定した場合は unset 時の engine default より優先される（`engine/src/program/generate.cpp:522-529, 13826-13836`）。

## 有効になる条件

- ready 数が実際に使われるのは `CheckpointPool` が on の場合だけ。pool は `STRATA_CKPT_POOL` が非ゼロ判定、`STRATA_SLOT_CKPT_MOVE` が有効、または build の既定条件を満たすと on になる。`STRATA_CKPT_POOL=0` は既定 pool を止めるが、`STRATA_SLOT_CKPT_MOVE` が pool を必要とする経路までは止めない（`engine/src/program/generate.cpp:506-515, 13826-13836`）。
- build の既定で pool が on になるのは Metal build 以外で、`STRATA_CKPT_POOL` が unset、conversation cache の予算が正、layer split でなく、checkpoint state の GDN 部分がある場合。Metal ではこの既定 on を無効にするが、明示的な `STRATA_CKPT_POOL` や `STRATA_SLOT_CKPT_MOVE` による pool まで無効化する条件ではない（`engine/src/program/generate.cpp:13826-13836`）。
- unset のときの ready 数は、上記の自動 pool が on なら `park_pool_plan` が決める。cache が 0 なら計画値は 0、そうでなければ checkpoint 1 個あたり cache の 1/12 を割り当てる整数個数で、最大 4（`engine/include/strata/core/park_pool_policy.hpp:13-33`）。明示した値はこの計画値に置き換わる。
- `STRATA_CKPT_POOL_READY` の値が正でも、layer split、pool off、ready 数 0、checkpoint の GDN state がない場合は先行確保されない（`engine/src/program/generate.cpp:14139-14147`）。
- top-up は idle 時に限られ、conversation cache が有効なら cache の未使用予算を超えず、さらに `--conversation-cache-min-free-mib` の floor と追加 1 GiB を残す RAM 範囲に制限される。RAM telemetry が取れず `STRATA_CKPT_POOL` が明示的に on でもない場合は top-up しない（`engine/src/program/generate.cpp:14139-14159`）。
- Strata は一部の parallel-request default で、この変数を未設定のときだけ `4` に設定する。Linux CUDA では 2 個以上の batch slot の場合、Windows gfx1151 では 2 個以上の場合、また discrete RDNA3 gfx1100/1101/1102 では 2 個以上の batch slot かつ `STRATA_GFX11_DEFAULTS` が無効化されていない場合が該当する。HIP 側の gfx1151 default は Windows 条件で、`STRATA_GFX1151_DEFAULTS=0` で抑止される。明示値（空文字を含む）は保持される（`engine/src/core/arch_defaults.cpp:226-250, 302-358, 433-443`; `engine/include/strata/core/gfx11_extra.hpp:116-136`; 呼び出しは `engine/src/program/generate.cpp:4315, 4405-4409`）。

## 実行時の詳細

`ckpt_pool_ready_env()` の環境文字列は関数内 static で初回呼び出し時に読み取られ、その後の環境変更は反映されない。未設定時は `ckpt_pool_ready_default()` の atomic 値を返す。serve setup は自動 pool 条件を満たした場合に `park_plan.ckpt_ready` をそこへ一度保存し、その後 `CheckpointPool::configure` に pool の on/off と cap を渡す（`engine/src/program/generate.cpp:521-531, 13826-13836`）。

pool の cap は `max(2, ready 数)`。ready 数は `pool_topup` の上限で、実際には空き pool 数と cache/RAM 予算の範囲で background thread が vector を作る。起動時、checkpoint の take 後、park 後、および request 間の idle 時に top-up が試みられる。request が in-flight の間は top-up せず、take 時に pool が空なら空の checkpoint が返り、保存処理が新しい vector を使うため、request は top-up を待たない（`engine/src/program/generate.cpp:2586-2642, 14139-14173, 14503-14515, 18296-18303`; idle gate は `engine/include/strata/core/park_pool_policy.hpp:36-40`）。

ready checkpoint が使われる保存先は host vector で、`checkpoint_save` の内容をその vector に書く。pool の ready 数は生成 token、sampling、checkpoint の採用順を指定しない（`engine/src/program/generate.cpp:14512-14530`）。conversation cache への park では、pool から取った checkpoint storage を snapshot save に渡し、残った storage を pool に戻してから再 top-up する（`engine/src/program/generate.cpp:14353-14380`）。

## ログと測定値

`STRATA_PARK_TRACE` が設定されていれば、serve setup で `strata parktrace: park pools: ... checkpoint pool ... (ready ..., cap ..., ... MiB each) ...` を stderr に出し、判定後の ready 数・cap・checkpoint 1 個の MiB 数を確認できる。ready pool または通常 pool から checkpoint を使った request では、stderr に `strata serve: checkpoint pool: this request took ... checkpoint(s) ready from the pool and allocated ... fresh` が出る。どちらも観測ログであり、設定値が指定数まで確保されたことを保証しない（`engine/src/program/generate.cpp:13876-13879, 14512-14514, 23660-23663`）。

ready 不足自体はエラーにせず、新規 vector で続行する。checkpoint save 自体が失敗した場合は `strata serve: checkpoint save: ...` が stderr に出る。失敗がコピー用メモリだけなら checkpoint を飛ばして request を続け、GPU sync も失敗した場合は `ERR saving a conversation checkpoint failed...` を stdout に出して request を終了する（`engine/src/program/generate.cpp:2561-2575, 21504-21511`）。

`docs/DETAILS.md:1764-1778` には以前の測定値（ready pool に `STRATA_PARK_ASYNC=1` と `STRATA_CKPT_GATHER=1` を併用した park 時間）があるが、同節の説明は「全て opt-in」としており、現行コードの自動 pool 条件とは一致しない。また対象行だけではモデルと測定回数を特定できないため、この文書では測定値を現行挙動の根拠として採用しない。

## 根拠

- 値の parse、clamp、unset default: `engine/src/program/generate.cpp:516-531`。
- pool on 条件と自動 ready 数: `engine/src/program/generate.cpp:13826-13836`; 計画関数: `engine/include/strata/core/park_pool_policy.hpp:13-33`。
- 起動時に設定される値と適用条件: `engine/src/core/arch_defaults.cpp:226-260, 302-358, 433-443`; `engine/include/strata/core/gfx11_extra.hpp:116-136`; 呼び出し: `engine/src/program/generate.cpp:4315, 4405-4409`。
- top-up、memory gate、request 中の fallback: `engine/src/program/generate.cpp:14139-14173, 14503-14515, 18296-18303`; `engine/include/strata/core/park_pool_policy.hpp:36-40`。
- pool の保管・取り出しと park 保存: `engine/src/program/generate.cpp:2586-2642, 14353-14380`。
- 観測ログと save failure: `engine/src/program/generate.cpp:13876-13879, 23660-23663, 2561-2575, 21504-21511`。
