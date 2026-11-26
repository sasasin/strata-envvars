# `STRATA_BATCH_SELF_COMMIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP verifier の batch window で、各行が別々の slot に属する（一 slot 一行）場合に、window 自身が slot の GDN 状態などを進めるようにします。通常の batch window が後段で行う commit graph の replay を省き、状態を window 内で保持します。対象は「一行-per-slot」の batch window のみで、同一 slot に複数行がある window には適用されません。実装は `Verifier::record_window` と batch commit/launch 経路です（`engine/src/core/verify.cpp:350-358,396-403,1620-1625`）。

## 値と判定

`verify.cpp` の `env_on` は `std::getenv` の結果について、未設定または空文字なら false、先頭文字が `'0'` なら false、それ以外は true とします。文字列全体の解析や数値変換はしません。よって `1`、`true`、`false`、`00x` は true、`0`、`0anything` は false、先頭に空白を置いた ` 0` も true です。値の長さや後続文字は検査しません（`engine/src/core/verify.cpp:336-339`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| verifier の batch window 判定 | false。ただし起動時既定値が注入される条件あり | `1`, `true`, `false`, ` 0` | 空文字, `0`, `0anything` |
| `STRATA_PIPED_MTP` の併用可否判定 | PIPED_MTP 側の条件で判定 | 空でない値の先頭が `0` 以外なら併用不可 | 未設定、空文字、先頭が `0` ならこの変数を理由とする停止なし |

既定値注入では、変数が**未設定**の場合だけ Strata が `1` を設定します。明示的な空文字や `0` はユーザー設定として保持されます（`engine/src/core/arch_defaults.cpp:218-223,253-260,302-310,433-437`; `engine/include/strata/core/gfx11_extra.hpp:116-132`）。

## 有効になる条件

- 値判定が true であること。
- `batch_rec_` の batch window であること。
- その window の各行の slot 番号が互いに異なること。slot 数は1以上です（`engine/src/core/verify.cpp:396-403,1620-1625`）。通常の server/parallel batch window では各 active slot を一行ずつ window に入れます（`engine/src/program/generate.cpp:17110-17123`）。
- `STRATA_PIPED_MTP` と同時に使う場合、`generate.cpp` はこの値の先頭文字を別に判定し、未設定・空文字・先頭 `0` 以外なら pipelined MTP を無効にします。MTP 条件で無効になった場合も通常の `--batch-mtp` に戻り、stderr に理由付き warning を出します（`engine/src/program/generate.cpp:8120-8145`）。
- Metal verifier の同等動作は確認できません。Metal の commit は別の `window_commit` 経路へ委譲され、この変数の batch self-commit 分岐は `verify.cpp` の CUDA/HIP batch 実装にあります（`engine/src/core/verify.cpp:4527-4530,4587-4594`）。

### 起動時の既定値

engine は GPU と batch slot 数を調べ、いくつかの条件で unset の変数に `1` を設定します。呼び出しは HIP build の GPU 初期化内と Linux CUDA build の並列設定内にあります（`engine/src/program/generate.cpp:4287-4320,4410-4415`）。

- Linux CUDA では `--batch` の slot 数が2以上なら parallel stack の一部として設定します。既に設定済みなら `=0` を含めて保持します（`engine/src/core/arch_defaults.cpp:248-260`）。
- Windows HIP の gfx1151 では batch slot が2以上で、`STRATA_GFX1151_DEFAULTS` が先頭 `0` でない場合に parallel stack の一部として設定します（`engine/src/core/arch_defaults.cpp:240-246,433-442`）。
- gfx1100/1101/1102（discrete RDNA3）の HIP build では slot が2以上で、`STRATA_DEFAULTS=026` でなく、かつ `STRATA_GFX11_DEFAULTS` が先頭 `0` でない場合に設定します（`engine/include/strata/core/gfx11_extra.hpp:27-30,116-132`）。
- どの条件でも、空文字を含む既存設定は既定値より優先されます。`STRATA_GFX1151_DEFAULTS` と `STRATA_GFX11_DEFAULTS` は既定値テーブルを抑止する条件であり、この変数自体の値判定方法とは別です。

## 実行時の詳細

`batch_self_commit_on()` は初回呼び出し時に `env_on("STRATA_BATCH_SELF_COMMIT")` を評価して function-local `static` に保存します。起動時に namespace-scope 初期化されると GPU 別既定値より先に cache されるため、初回使用まで読み取りを遅らせています。したがって初回判定後に環境を変更しても verifier の判定は変わりません（`engine/src/core/verify.cpp:350-358`）。

batch window の各 slot 行を `keep_rows` として扱い、GDN convolution history と recurrence の実行に keep 指定を渡します。また indexer tail の snapshot を省き、各行の状態を window 内で保持します（`engine/src/core/verify.cpp:1620-1625,1938-2007,2096-2104`）。その後 `capture_commit_batch` はこの条件で commit graph を作らず、batch launch と commit 経路も commit graph の起動を飛ばします。結果として同じ window の後段で状態を再適用する commit graph がなくなります（`engine/src/core/verify.cpp:4710-4713,5542-5548,5652-5660`）。

この変数は CLI 引数として直接解析されず、`--batch` / server の parallel slots が作る batch window の実装スイッチです。GPU/OS 固有の既定値注入を除き、CLI 値がこの環境変数を上書きする処理は見つかりません。明示的な空値は verifier では off ですが、`STRATA_PIPED_MTP` との競合判定でも off 扱いです（`engine/src/program/generate.cpp:8120-8132`）。

## ログと測定値

batch verifier 初期化時、変数判定が true なら stderr に `strata verify: batch windows of up to %lld sequences (layers [%lld, %lld)), one-row windows keep their rows` と出ます。false の場合は末尾の説明がありません（`engine/src/core/verify.cpp:4661-4663`）。

`STRATA_PIPED_MTP` が設定済みでこの変数が空でない非 `0` 文字列の場合は、stderr に `strata generate: WARNING: STRATA_PIPED_MTP is off: it does not combine with STRATA_BATCH_SELF_COMMIT (the window would keep its rows itself)` と出し、pipelined MTP を off にします（`engine/src/program/generate.cpp:8125-8140`）。

## 根拠

- `engine/src/core/verify.cpp:336-339,350-358` — 値判定と初回読み取り cache。
- `engine/src/core/verify.cpp:396-403,1620-1625` — 一 slot 一行の条件。
- `engine/src/core/verify.cpp:1938-2007,2096-2104` — GDN 状態の keep と indexer snapshot の分岐。
- `engine/src/core/verify.cpp:4661-4663,4710-4713,5542-5548,5652-5660` — ログ、commit graph の省略、batch launch 経路。
- `engine/src/program/generate.cpp:4287-4320,4410-4415,8120-8145` — 既定値設定呼び出しと pipelined MTP との競合。
- `engine/src/core/arch_defaults.cpp:218-223,240-260,302-310,423-442` — platform default の注入。
- `engine/include/strata/core/gfx11_extra.hpp:27-30,116-132` — discrete RDNA3 の既定値条件。
