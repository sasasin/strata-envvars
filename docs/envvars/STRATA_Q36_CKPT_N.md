# `STRATA_Q36_CKPT_N`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 エンジンが各 session で保持する GDN（SSM）の状態 checkpoint のリング深度を指定する。正数なら checkpoint の保存を有効にし、値が大きいほど古い分岐位置まで復元できる checkpoint を多く保持する。`0` 以下なら checkpoint を保存せず、serve の prompt 再利用は保持 session 全体が次の prompt の厳密な prefix である場合に限られる。checkpoint は生成 token の選択を変える設定ではなく、共通 prefix の途中から再開するための session state を保持する（`engine/src/qwen35/q36_engine.cu:1687-1692, 1740-1747, 4972-4985`）。

読み取りは `Engine::init()` 内のローカル `envn` helper 一箇所で行い、`ckpt_n` に格納する（`engine/src/qwen35/q36_engine.cu:2224-2233`）。

## 値と判定

`std::getenv` で取得し、未設定または空文字なら既定値 `4` を返す。その他は `std::strtoll(v, &e, 10)` で 10 進整数として変換し、数字を一つも変換しなかった場合（`e == v`）は既定値 `4` に戻す。変換後は `max(0, 値)` で負数を `0` に clamp し、その後 `int` に cast する（`engine/src/qwen35/q36_engine.cu:2225-2233`）。

| 条件 | unset / 空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Q36 engine の `envn` | `4`（checkpoint 深度 4） | 整数として先頭部分が変換され、結果が正の値。例: `1`, `+2`, ` 3`, `3tail` はそれぞれ深度 1, 2, 3, 3 | `0`, `0tail`, 負数（例 `-1`）は深度 0 となり無効。`true` のように数字がない文字列は無効値として扱われず、変換失敗時の既定値 4 になる |

変換後の文字列全体は検証しないため、数字の後ろの文字列は無視される（`0anything` は 0、`2x` は 2）。小数点以下も parse されず、`1.5` は 1 になる。先頭の空白と符号は `strtoll` の規則で受け付ける。大文字小文字による判定はない。上限検査はなく、`long long` から `int` への cast で表現範囲を超える入力の結果は移植可能な深度として保証されない（同 `2225-2233`）。

## 有効になる条件

- `engine/src/qwen35/q36_engine.cu` を含む CUDA/HIP GPU build の Qwen3.6 (`qwen35moe`) エンジン経路で有効。`strata` は build 時に `STRATA_HAVE_QWEN35` が定義されている場合にこの family の処理を `strata::qwen35::run()` へ渡し、standalone の `strata-q36` も同じ engine を使う（`engine/cmake/strata_gpu_engine.cmake:565-584`; `engine/src/program/generate.cpp:3799-3812`; `engine/src/qwen35/q36_main.cpp:1-5`）。
- gfx906 build では Qwen35 engine target を作らない。CPU-only、SYCL、Metal はこの `.cu` engine を使わないため、この環境変数の読み取り箇所はない（`engine/cmake/strata_gpu_engine.cmake:565-584`; `engine/CMakeLists.txt:1-6, 23-32`）。
- 保存には `ckpt_n > 0` に加えて checkpoint 対象となる GDN layer があり、計算した `ckpt_bytes > 0` であることが必要。深度が正の場合、モデルの geometry と `!L.attn` の layer 数から checkpoint 一つ分の大きさを計算する。サイズが 0 の場合も保存・復元は無効（`engine/src/qwen35/q36_engine.cu:2232-2241, 2296-2298, 2317-2324, 4976-4985`）。
- 実際の分岐した prompt prefix からの再開は `--serve` の session 選択経路で行われる。保存の確認自体は `process()` の decode step、prompt chunk、speculative step の後に呼ばれるため、engine の他モードでも条件が合えば保存は起きるが、serve の request 再利用経路がなければ、その checkpoint による prefix 再開は行われない（`engine/src/qwen35/q36_engine.cu:3713-3717, 3737-3741, 4013-4019, 4972-5001, 5092-5129`）。
- `STRATA_Q36_CKPT_EVERY` は保存を確認する token 間隔を別に指定する。未設定・空・変換失敗時は 4096、値は最低 1 に clamp される。間隔は深度を上書きせず、深度 0 の保存を有効化もしない（`engine/src/qwen35/q36_engine.cu:2232-2233, 2317-2324`）。CLI 引数による `ckpt_n` の上書きはこの読み取り経路にない。

## 実行時の詳細

`envn` は engine 初期化中に一度呼ばれ、結果を `Engine::ckpt_n` に保存する。static cache や request ごとの再読込ではないため、初期化後にプロセス環境を変更してもこの engine instance の深度には反映されない（`engine/src/qwen35/q36_engine.cu:2224-2233, 5466-5474, 5522`）。

正の深度では session ごとの checkpoint ring は最初の保存時に作られ、各 ring slot の pinned host buffer も保存時に確保される。各 checkpoint は全 GDN layer の `conv` と `S`、および `hlast` を device から host へコピーし、stream 同期後に position と rotary offset を記録する。保存間隔をまたいだ処理境界で `pos / ckpt_every` が前回値より大きいとき、その時点の状態を一つ保存するため、保存位置は処理境界であり厳密な間隔の倍数とは限らない。ring が満杯なら次の保存が古い slot を置き換える（`engine/src/qwen35/q36_engine.cu:1738-1747, 2294-2324`）。

serve が prompt と保持済み session の共通 prefix を調べ、session 全体より短い位置から再開する必要がある場合、共通 prefix 以下で最も新しい checkpoint の conv/S/hlast state を戻し、position と rotary offset を復元する。再開点より後の checkpoint は無効化され、attention K/V cache は prefix の cell に残る。該当 checkpoint がない場合は `resume_len` が 0 を返し、request は session を reset して prompt を読み直す（`engine/src/qwen35/q36_engine.cu:2280-2285, 2326-2353, 4972-4985, 5110-5129`）。

## ログと測定値

`ckpt_n > 0` かつ `ckpt_bytes > 0` の場合、初期化時に stderr へ `strata-q36: GDN checkpoints: ...` の行を出す。深度/セッションごとの pinned host memory 見積もり、間隔、GDN layer 数、各 state の byte 数が含まれる。深度 0 またはサイズ 0 ならこの行は出ない（`engine/src/qwen35/q36_engine.cu:2234-2247`）。serve の request 終了時は stderr の `strata serve: session ...` 行にその session が保持する checkpoint 数が `... %d ckpt` として出る。stdout の `DONE` 行には checkpoint 数は含まれない（`engine/src/qwen35/q36_engine.cu:5266-5273`）。

`cudaHostAlloc`、device-host / host-device copy、stream 同期など `CK(...)` で包まれた GPU runtime 呼び出しに失敗すると、stderr に `strata-q36: <式> failed: <エラー> (<ファイル>:<行>)` を出し、終了コード 1 で終了する。無効値専用の警告や fallback ログはない（`engine/src/qwen35/q36_engine.cu:82-89, 1720-1730, 2300-2311, 2334-2343`）。

該当する条件付き測定値は資料にない。

## 一覧との記載差

Strata の `docs/SETTINGS.md` はこの変数を `on / off` と分類し、`terminal/data/settings-register.json` も `parse: "flag"` としているが、実装は整数を checkpoint ring 深度として parse し、既定値は 4 である（`docs/SETTINGS.md:271`; `terminal/data/settings-register.json:37238-37267`; `engine/src/qwen35/q36_engine.cu:2225-2233`）。この分類は実装の値規則と一致しない。

## 根拠

- 全参照の確認: `engine/src/qwen35/q36_engine.cu:1687, 1692, 1745, 2232, 4974`。実際の環境読み取りは `envn` helper 経由の `2232`。
- 値の parse と clamp: `engine/src/qwen35/q36_engine.cu:2224-2233`。
- 保存状態の計算・記録・復元: `engine/src/qwen35/q36_engine.cu:2234-2247, 2280-2353`。
- 保存タイミングと serve の再利用: `engine/src/qwen35/q36_engine.cu:3713-3741, 4013-4019, 4972-5001, 5092-5129`。
- build と family の経路: `engine/CMakeLists.txt:1-6, 23-32`; `engine/cmake/strata_gpu_engine.cmake:565-584`; `engine/src/program/generate.cpp:3799-3812`。
- ログ・runtime failure: `engine/src/qwen35/q36_engine.cu:82-89, 1720-1730, 2234-2247, 2300-2311, 2334-2343, 5268-5273`。
