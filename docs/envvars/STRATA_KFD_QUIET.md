# `STRATA_KFD_QUIET`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux の HIP build で、統合 AMD GPU の特定世代に対して Strata が行う KFD 関連の起動・終了時調整をまとめて切り替えるスイッチです。対象は LOAD（ロード中に GPU 処理や初回 prompt 用バッファを前倒しする）、EXIT（終了 signal の前に GPU を止めて arena 登録を解除する）、XFER（未設定時の `GPU_PINNED_MIN_XFER_SIZE` を Strata が設定する）、NOREG（expert arena を未登録にする既定）、LEND（条件を満たす場合に prompt 用の cache slot 借用をやめる）の各経路です。これらは環境変数を読んだ Strata の選択・操作であり、GPU driver 内部の挙動をこの変数が直接制御するものではありません。実装は `include/strata/core/kfd_quiet.hpp` にあります（47-68行）。

値が `0` で始まると共通スイッチとして無効になり、LOAD/EXIT/XFER/NOREG を抑止します。各機能の個別変数で機能を無効化することもできます。LEND は例外的に既定 OFF で、`STRATA_KFD_QUIET_LEND=1` が必要です。共通変数が設定されていても、それだけでは LEND は ON になりません（同 47-68、125-143行）。

## 値と判定

値全体の parse はせず、`getenv` の戻り値の先頭 1 文字だけを調べます。未設定 (`nullptr`)、空文字、先頭が `0` 以外の値は共通スイッチを OFF にしません。したがって `0`、`0anything` は OFF、`1`、`true`、`false`、` 0`、空文字は ON 側です。大文字小文字・空白除去・数値妥当性の検査はありません（`include/strata/core/kfd_quiet.hpp:47-52`）。ただし ON/OFF の意味は個別経路の既定値にも依存します。

| 経路 | `STRATA_KFD_QUIET` 未設定・空文字・先頭が `0` 以外 | `0` または `0anything` | 個別変数との関係 |
|---|---|---|---|
| LOAD / EXIT | 対象 GPU class なら有効 | 無効 | `_LOAD` / `_EXIT` が `0` で始まる場合はその機能だけ無効。個別変数で共通 OFF を上書きして有効にはできない。 |
| XFER | 条件を満たせば Strata が値を設定 | 設定しない | `_XFER` の先頭が `0` なら設定しない。個別値も共通値も `1` で始まる必要はない。 |
| NOREG | gfx1103 class なら既定で有効 | 既定を無効化 | `_NOREG` が `0` で始まる場合は無効。`STRATA_UMA_REGISTER` が `1` で始まる場合も NOREG しない。 |
| LEND | 既定 OFF のまま | 無効 | `_LEND` が `1` で始まる場合に有効化できるが、共通値の先頭が `0` なら無効。`STRATA_PREFILL_BORROW` が `1` で始まる場合も無効。 |

この表の判定は `switch_on`、`noreg_default`、`lend_rule_on` の実装によります（`include/strata/core/kfd_quiet.hpp:47-68,104-109,135-143`）。XFER は加えて caller が `GPU_PINNED_MIN_XFER_SIZE` を設定済みなら Strata は上書きしません（同 251-257行）。

## 有効になる条件

- **共通 class**: LOAD、EXIT、XFER は Linux の HIP build で、統合 GPU として検出された全 GPU が gfx1103 / gfx1150 / gfx1151 のいずれかの場合に対象になります。class flag は GPU 名・構成を確認した後に設定されます。CUDA、SYCL、Windows、または対象外 GPU ではこの KFD quiet 経路は有効になりません（`src/core/arch_defaults.cpp:151-159`、`src/program/generate.cpp:4124-4127`）。
- **NOREG class**: さらに狭く、KFD topology 上の全 GPU node が gfx1103 の場合だけです。gfx1150 / gfx1151 や別 GPU が混在する場合には NOREG の既定分岐に入りません（`include/strata/core/kfd_quiet.hpp:214-225`、`src/program/generate.cpp:4133-4138`）。
- **LOAD**: class と共通スイッチおよび `_LOAD` の判定が ON であること。前倒しする hyper-connection check は GPU 名の取得にも成功している場合だけです（`src/program/generate.cpp:7961-7970`）。初回 prompt 用 device buffer は `T > 0` の場合だけ作成を試し、CPU share 用 pinned buffer は `T > 0`、CPU pool があり、CPU share が有効な場合だけです（`src/prefill/prefill.cpp:2561-2580`）。KV prefetch stream/event の先行作成には別途 `STRATA_KV_PREFETCH` が設定され、`atoi` が 0 でないことが必要です（同 2568-2573行）。
- **LOAD の別処理**: READY 前の KFD settle は class/flag によって呼ばれます。settle 自体は counter が読めない場合には待たず、別の `STRATA_NO_KFD_SETTLE=1` 条件もありますが、これは `STRATA_KFD_QUIET` の判定ではありません（`src/program/generate.cpp:4121-4123,9062-9066`、`include/strata/core/kfd_settle.hpp:113-130`）。
- **XFER**: 上記共通 class に加え、KFD topology から少なくとも 1 GPU node が読め、全 GPU node が対象 gfx の場合に判定されます。`GPU_PINNED_MIN_XFER_SIZE` がすでに存在すれば（空文字を含む）Strata は設定しません。`STRATA_ARENA_MMAP=1` の経路は先にこの値を設定するため、そちらがある場合も KFD quiet 側は上書きしません（`src/program/generate.cpp:3582-3590,3591-3603`、`include/strata/core/kfd_quiet.hpp:198-212,228-257`）。
- **NOREG**: gfx1103 class で共通スイッチと `_NOREG` が ON で、かつ `STRATA_UMA_REGISTER` が `1` で始まらないこと。実際の arena mode は `STRATA_ARENA_PIN_GIB` が空でない値ならそちらが優先され、値が厳密に `none` のときだけ未登録になります。未設定または空なら engine flag に従います（`include/strata/core/kfd_quiet.hpp:104-115`、`src/core/pinned.cu:583-592`）。
- **LEND**: 共通 class で、`pf_borrow` が有効、prompt chunk が正、共通スイッチが OFF でなく、`STRATA_PREFILL_BORROW` / `_LEND` の規則を満たすことが入口条件です。その後、単一 GPU・layer stage なし・peer device なし・remote expert cache なし、chunk 1..16384、prompt の自前 buffer が cache と reserve 以外に 3072 MiB を残して収まることが必要です。条件不足なら借用を維持します。CLI 等で `pf_borrow` が false ならこの環境変数の分岐自体に入りません（`include/strata/core/kfd_quiet.hpp:125-161`、`src/program/generate.cpp:8861-8895`）。

## 実行時の詳細

- `STRATA_KFD_QUIET` と個別スイッチは `getenv` で読みます。`env_on` / `load_moves` は呼び出しごとに読み直し、関数内 static cache はありません（`include/strata/core/kfd_quiet.hpp:65-68,81-93`）。LOAD の hyper-connection check、settle、prompt buffer 前倒し、READY 前 copy warm はそれぞれの呼び出し時に判定されます（`src/program/generate.cpp:7967-7970,9062-9066,15142-15158`、`src/prefill/prefill.cpp:2561-2597`）。
- class 判定と NOREG は GPU 検出後の起動時に flag を設定します。XFER も起動処理で topology を読み、条件成立時は Strata が `GPU_PINNED_MIN_XFER_SIZE=1000000` を `setenv(..., 0)` で設定します。以後の `STRATA_KFD_QUIET` 変更でこの設定を再評価しません（`src/program/generate.cpp:3591-3603,4124-4138`）。
- EXIT は起動時にスイッチが ON のときだけ handler を install します。最初の SIGTERM / SIGINT / SIGHUP では request stop、GPU wait 解放、最大合計 3 秒の device drain を試み、drain 成功時だけ arena range を unregister して同じ signal で終了します。drain が完了しない場合は unregister せず signal 終了へ進みます。2回目の signal は default action です（`src/program/generate.cpp:372-378,396-429,4145-4150`、`include/strata/core/kfd_quiet.hpp:261-295`）。
- NOREG flag は起動時に決まり、その flag と `STRATA_ARENA_PIN_GIB` が arena の登録・lock 経路で使われます。NOREG が選ばれた場合、未指定の `STRATA_ARENA_LOCK` では mlock を要求しません。明示した `STRATA_ARENA_LOCK` は既存ルール（値が厳密に `0` なら no lock、それ以外は lock）に従います（`include/strata/core/kfd_quiet.hpp:111-122`、`src/core/pinned.cu:583-592,800-813`）。
- LEND は cache を loan ありのサイズにした後に判定します。適用時は `no_prefill_borrow` を true にし、`pf_borrow` を false、auto を false にしますが、chunk 値は変更しません（`src/program/generate.cpp:8864-8894`）。
- LOAD の前倒し allocation や staged copy warm が失敗しても、該当コードは error を返さず後続の通常経路に任せる実装です。たとえば `Prefill::init` の buffer 作成失敗は pointer を空に戻して request 側に再試行させ、warm copy の失敗は無視します（`src/prefill/prefill.cpp:2557-2573,2575-2597`、`src/program/generate.cpp:15147-15156`）。

## ログと測定値

`STRATA_TRACE` が設定されている場合（値の内容は問わず presence 判定）、該当経路で次の stderr trace を出します。

- NOREG flag を立てたとき: `strata trace: kfd quiet: expert arena not registered with the driver, no mlock (%s)`。`%s` は `in effect` または `STRATA_ARENA_PIN_GIB set: registered as it says` です（`src/program/generate.cpp:4135-4141`）。
- LOAD が有効なとき: `strata trace: kfd quiet: load order active (check first, settle after the expert cache, first prompt's buffers at init)`（同 4143-4144行）。
- EXIT handler を install したとき: `strata trace: kfd quiet: stop on SIGTERM / SIGINT / SIGHUP drains the GPU first (at most 3 s)`（同 4145-4150行）。実 signal 後は wait 解放・drain・unregister 数・所要時間を `strata trace: kfd quiet: signal ...` として出します（`src/program/generate.cpp:419-423`）。
- XFER の設定時: `strata trace: kfd quiet: GPU_PINNED_MIN_XFER_SIZE=%s (pageable copies staged by the runtime)`（同 3598-3602行）。
- staged copy warm の試行時: `strata trace: kfd quiet: staged copy before READY done` または `... skipped (no device memory)`（同 15147-15158行）。
- LEND の判定入口に入った場合は自前 buffer 必要量、空き量などと `yes` / 不成立理由を trace します（同 8882-8888行）。既定状態や条件不成立を個別に通知する trace はありません。

## 根拠

- 共通 switch、動的な個別スイッチ名、LOAD/EXIT helper: `include/strata/core/kfd_quiet.hpp:47-93`
- NOREG / LEND / topology class / XFER helper: `include/strata/core/kfd_quiet.hpp:95-161,198-257`
- GPU class と Linux HIP build 条件: `src/core/arch_defaults.cpp:151-159`、`src/program/generate.cpp:4124-4138`
- XFER 設定と既存値の優先: `src/program/generate.cpp:3582-3603`
- LOAD、NOREG、EXIT の起動時分岐: `src/program/generate.cpp:4124-4151`
- LOAD の処理: `src/program/generate.cpp:7967-7970,9062-9066,15142-15158`、`src/prefill/prefill.cpp:2555-2597`
- arena の登録・lock: `src/core/pinned.cu:583-592,800-813`
- LEND の入口、余裕量判定、適用: `src/program/generate.cpp:8861-8895`
- EXIT teardown: `src/program/generate.cpp:372-429`、`include/strata/core/kfd_quiet.hpp:261-295`
