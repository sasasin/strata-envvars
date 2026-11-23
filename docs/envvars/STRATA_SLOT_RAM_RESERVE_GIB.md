# `STRATA_SLOT_RAM_RESERVE_GIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata generate` のサーバー batch slot を追加で確保する際、各 slot の KV streaming 用 pinned RAM と、後から読み込む expert arena・明示予算の conversation cache を見積もり、RAM に残す GiB を指定します。正の値を明示すると、見積もり上その余裕を残せる数まで batch slot を減らします。未設定時は 8 GiB を基準に不足を警告しますが、slot 数は減らしません。GPU 上の session の確保数や `--batch` の要求値を直接設定する変数ではありません。判定箇所は `engine/src/program/generate.cpp` の batch slot 初期化です。`--batch` または同義の `--slots` が必要で、batch が無効になる場合はこの判定に到達しません（`engine/src/program/generate.cpp:4036-4037, 7883-7899, 7929-7947`）。

候補名のソース全体検索では `engine/src/program/generate.cpp` に環境からの読み取りが 1 箇所あり、`terminal/data/settings-register.json` に設定名の登録があります。設定レジストリの記載自体は読み取り根拠ではありません。別の helper や動的な名前を通じた読み取りは見つかりませんでした。

## 値と判定

読み取りは slot 作成ブロックでの `std::getenv` 1 回です。未設定または空文字なら `reserve_asked` は false、値は 8.0 GiB になります。空でない設定値は `std::atof` で `double` に変換し、変換後の値が正のときだけ RAM 判定を行います。`atof` の変換結果全体や末尾は検査しません。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `engine/src/program/generate.cpp` の batch slot 経路 | 8 GiB を警告判定に使用。slot は減らさない | 正の数値。`1`、`8`、`0.5`。正数で始まる `2GiB` や `2anything` も `atof` が数値部分を変換し、2 GiB として扱う | 空文字は unset と同じ。空白だけの値、`0`、`0anything`、負数、`true`、`abc` は変換後が 0 以下となり RAM 判定をしない |

値の形式検証、末尾文字の拒否、明示的な最小値・最大値の clamp はありません。`atof` は先頭空白を読み飛ばすため、たとえば ` 2` は正の値になります。空白だけの非空文字列は `reserve_asked` が true になりますが、`atof` の結果が 0 なので判定は行いません。正の値は GiB をバイトに換算する際に `uint64_t` へ変換されます。巨大値など変換先の範囲を超える入力の結果は、このコードから安全な値域として保証できません（`engine/src/program/generate.cpp:7948-7964`）。

## 有効になる条件

- `--serve` が必要で、`--batch` / `--slots` は 2 以上である必要があります。`--batch` が 0、1、または `--serve` なしの場合は先に batch が無効化され、この環境変数による RAM 判定を行いません（`engine/src/program/generate.cpp:4036-4037, 7883-7890`）。
- 同じ GPU に複数 stage を置く layer split (`split_same`) では batch が無効化されます。通常の単一 GPU と、別 GPU ごとの stage に分けた layer split はこの条件では除外されません（`engine/src/program/generate.cpp:7885-7890`）。
- session 初期化後の `qsa_kv_host_bytes()` が 0 より大きい必要があります。これは QSA KV streaming の host KV コピー量で、KV streaming がない場合は 0 のままです。その場合は環境変数による RAM 判定も警告もありません（`engine/src/core/layer.cpp:920-940`; `engine/src/program/generate.cpp:7637-7675, 7952-7954`）。
- Strata が host available memory を取得できる必要があります。取得に失敗した場合はこの分岐を通らず、環境変数による slot 調整・診断はありません。helper は Windows、Linux、macOS、およびその他の `sysconf` 対応経路で空き RAM を取得します（`engine/src/core/expert_source.cpp:414-442, 513-556`）。
- Linux では helper が `STRATA_MEM_CREDIT_INACTIVE` も読みます。値の先頭文字が `1` のとき、cgroup の空き RAM 見積もりで reclaimable cache を inactive 分に限るため、本変数の `ram_fit` に間接的に影響します。他の OS ではこの helper 内で読みません（`engine/src/core/expert_source.cpp:428-449`; `engine/src/core/conversation_memory.cpp:72-89`）。
- 明示的な `--conversation-cache-mib` の予算は、prompt cache が有効 (`o.prompt_cache > 0`) の場合に限って後続使用量の見積もりへ足されます。`--serve` が自動サイズする conversation cache はここでは加算されません。expert arena の見積もりは全 layer の expert blob サイズから計算します（`engine/src/program/generate.cpp:7955-7967`）。
- この読み取りは CUDA/HIP の共通 engine source と Metal engine が使う `src/program/generate.cpp` にあります。SYCL は別の `engine/sycl/src/program/generate.cpp` を使い、同じ環境変数の読み取りはありません（`engine/cmake/strata_gpu_engine.cmake:548-551`; `engine/metal/CMakeLists.txt:135-139, 176-177`; `engine/sycl/CMakeLists.txt:40`; `engine/sycl/src/program/generate.cpp:4371-4495`）。

## 実行時の詳細

変数は `strata generate` の batch session を作る段階で読み取られます。最初の session を初期化して `qsa_kv_host_bytes()` が確定した後、slot 用 session を GPU に確保する前です。関数内 `static` やグローバル cache はなく、この箇所で一度だけ環境から取得します。実行中に環境を変更してもこの判定には反映されず、子プロセスへの転送処理もありません（`engine/src/program/generate.cpp:7637-7675, 7929-7954`）。

RAM 判定では、`slot_host` を 1 slot の host KV 量、`avail` を helper が報告した空き RAM とし、expert arena と条件に合う明示的 cache 予算を `later` に加えます。予約量は、`avail >= later + base` なら `later + base`、そうでなければ `base` です。`base` は指定 GiB をバイト換算した値です。残り RAM を slot 量で割って整数個の `ram_fit` を求め、要求数を上限とします。layer split で slot が十分残る場合は stage 数に応じた倍数へ切り下げます（`engine/src/program/generate.cpp:7955-7967`）。

明示した正の値で `ram_fit` が要求数より少なければ、警告を出して slot 数を `ram_fit` に抑えます。結果が 2 未満なら通常の `--batch is off` 経路で batch を無効にし、server は batch なしで続行します。値を未設定または空文字にした場合、同じ不足判定は警告だけで、要求した全 slot を確保しようとします。明示値で十分な場合と unset 時に 8 GiB を保てる場合は slot 数を変えません（`engine/src/program/generate.cpp:7968-7991, 8025-8045`）。

`STRATA_KV_RESIDENT` など KV streaming の設定、モデル形状、`--max-context`、KV 形式は `slot_host` の実量を左右しますが、この環境変数はそれらを上書きしません。Linux では `STRATA_MEM_CREDIT_INACTIVE=1` が cgroup 空き量の見積もりを変えます。RAM の空き量は判定時点のスナップショットです。後続のメモリ使用が見積もりを超えた場合に確保成功を保証する処理ではありません（`engine/src/core/layer.cpp:738-765, 920-940`; `engine/src/core/expert_source.cpp:428-449`; `engine/src/core/conversation_memory.cpp:72-89`; `engine/src/program/generate.cpp:7952-7967`）。

## ログと測定値

正の値を明示して要求数を抑える場合は、次の形式の stderr 警告を出します（GiB 数や slot 数は実行時の値です）。

```text
strata generate: WARNING: --batch ...: a slot's K/V takes ... GiB of pinned RAM, ... GiB are available and the engine still loads ... GiB (the experts' arena, the conversation cache's --conversation-cache-mib): ... slots keep ... GiB free (a smaller --max-context makes a slot smaller; STRATA_SLOT_RAM_RESERVE_GIB sets what stays free)
```

未設定時に 8 GiB を残せない見積もりでは、全 slot を確保するとシステムが engine を終了させる可能性がある旨を警告し、要求数を維持します。RAM 判定を通り、見積もり上 slot 数を抑える必要がない場合は `strata generate: --batch ...: the slots' K/V takes ...` の情報行です。RAM 取得失敗または `slot_host == 0` の場合、この RAM 判定からのメッセージはありません。ここに記載できる本変数の性能測定値はありません（`engine/src/program/generate.cpp:7968-7991`）。

## 根拠

- `engine/src/program/generate.cpp:7883-7899` — `--serve`、batch 数、layer split による batch の有効条件。
- `engine/src/program/generate.cpp:7929-7954` — slot session 作成前の環境変数読み取りと RAM 判定の入口。
- `engine/src/program/generate.cpp:7955-7991` — 残存 RAM・後続使用量・slot 数の計算、明示値と unset の分岐、stderr 文言。
- `engine/src/program/generate.cpp:8025-8045` — slot 数が 2 未満の場合の batch 無効化と、最終 slot 数の反映。
- `engine/src/core/layer.cpp:920-940` — KV streaming 用 host copy の確保と `qsa_kv_host_bytes()` の集計対象。
- `engine/src/core/expert_source.cpp:414-442, 513-556` — host available memory の OS 別取得経路。
- `engine/src/core/conversation_memory.cpp:72-89` — Linux cgroup の cache credit に関係する `STRATA_MEM_CREDIT_INACTIVE` の判定。
- `engine/cmake/strata_gpu_engine.cmake:548-551`, `engine/metal/CMakeLists.txt:135-139, 176-177`, `engine/sycl/CMakeLists.txt:40` — backend ごとの generate source 配置。
