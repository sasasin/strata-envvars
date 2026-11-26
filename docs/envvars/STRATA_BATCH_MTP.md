# `STRATA_BATCH_MTP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数のリクエストを batch slot で処理する際、各 slot が MTP（multi-token prediction）の proposal を出し、対象モデルの verifier がその proposal を同じ window 内で検証する機能を opt-in にします。通常の batch decode では各 slot は一度に現在 token の行だけを持ちますが、この機能では slot ごとに proposal の行も加わります。環境変数と `--batch-mtp` は OR 条件で、変数を無効値にしても CLI の `--batch-mtp` を打ち消しません。CUDA/HIP 系の通常 engine と SYCL engine では同じ読み方ですが、Qwen3.6-35B 専用 engine の読み方は異なります。`engine/src/program/generate.cpp:7841-7843`、`engine/sycl/src/program/generate.cpp:4377-4378`、`engine/src/qwen35/q36_engine.cu:5556-5560`。

## 値と判定

通常 engine は `getenv` の戻り値を一度取得し、未設定でなく、空文字でなく、先頭文字が `'0'` でない場合に有効とします。文字列全体の parse や大文字小文字の変換はしません。したがって `1`、`true`、`yes`、` 1` は有効、`0`、`0anything`、空文字、未設定は無効です。通常 engine では `--batch-mtp` があれば環境変数の値にかかわらず有効候補になります。`engine/src/program/generate.cpp:7841-7843`、`engine/sycl/src/program/generate.cpp:4377-4378`。

| 実行経路 | 未設定 | 有効になる値 | 無効になる値 |
| --- | --- | --- | --- |
| CUDA/HIP `strata generate`、SYCL `strata generate` | 環境変数だけでは無効 | 空でなく先頭が `0` 以外（例: `1`, `true`, ` 1`） | 空文字、先頭が `0`（例: `0`, `0anything`） |
| Qwen3.6-35B 専用 engine (`strata-q36`) | 環境変数だけでは無効 | 値全体が文字列 `0` と異なる（空文字、`00`、`0anything` も有効） | 値全体が `0` |

Qwen3.6-35B では二度 `getenv` し、値全体を `std::string` として `"0"` と比較します。`--batch-mtp` と環境変数は OR され、その後 `E.n_sess > 1` かつ GGUF に MTP block があり `--mtp N` が正値 (`E.mtp_d > 0`) の場合だけ `E.bmtp` が true になります。`--batch-mtp` を明示したのに条件を満たさない場合は stderr に `strata-q36: --batch-mtp needs --batch N (2 or more) and --mtp N: ignored` と出ます。環境変数だけで有効化した場合は、この条件不足を知らせる同じ警告は出ません。`engine/src/qwen35/q36_engine.cu:5373-5383,5556-5560`。

## 有効になる条件

- 通常 CUDA/HIP engine と SYCL engine は `--batch N` を伴う serve mode が必要です。さらに `--mtp` と `--spec T`（`T >= 2`）が必要です。CUDA/HIP は `split_same`（同じ GPU に複数 stage を割り当てる分割）では動かず、SYCL は helper を含む複数 GPU・layer split では動きません。SYCL の対象は一 GPU の serve 経路です。条件不足では batch MTP を切り、通常の batch は可能な範囲で継続します。`engine/src/program/generate.cpp:7843-7855`、`engine/sycl/src/program/generate.cpp:4379-4385`。
- CUDA/HIP の layer split で slot group が複数になる場合、既定の pipelined groups は batch MTP を落とします。明示的な `--batch-groups` / `auto` も複数 group の pipeline にします。`--batch-groups 1`、`STRATA_BATCH_MTP_SERIAL` が空でなく先頭文字が `0` 以外、または `--adapt-async 1` などで serial group になる場合は継続できます。`STRATA_PIPED_MTP` を使う pipelined path は別の draft 経路です。layer split で helper expert cache がある場合も batch MTP は停止します。`engine/src/program/generate.cpp:7803-7820,7857-7869`。
- Metal build は batch MTP window に必要な slot の token と proposal の二行を処理できないため無効化されます。通常 batching は継続し、stderr に `strata generate: WARNING: --batch-mtp is off: the Mac (Metal) engine's batch windows take one row per request, so the slots run without draft rows (#5674)` を出します。`engine/src/program/generate.cpp:7849-7856`。
- Qwen3.6-35B 専用 engine では複数 session (`E.n_sess > 1`) と MTP block、および正の `--mtp N` が必要です。環境変数の読取り箇所には通常 engine の `--serve`、GPU 構成、`--spec` の gate はありません。実際の batch window は active slot、proposal 対象 slot、verify row の空きがある時だけ MTP window へ進み、それ以外は plain window になります。`engine/src/qwen35/q36_engine.cu:5556-5560,4899-4909`。
- Terminal の Python 制御コードは engine とは別にこの変数を読み、slot draft の表示や Auto の DFlash2 選択、`parallel` 上限の警告判断に使います。これは環境変数の値を変換して engine に渡す処理ではありません。`terminal/strata_control/drafting.py:930-937,940-961,1146-1164`、`terminal/serve/server_parts/engines.py:847-851`。

## 実行時の詳細

通常 engine では CLI option の parse 後、batch MTP の gate で環境変数を読みます。値を `static` cache する実装ではなく、この起動時の判定結果から `batch_mtp` を設定します。実行中の環境変更を再評価する経路はありません。機能が有効だと各 slot に MTP drafter を作り、CUDA/HIP は solo drafter の weights を共有しつつ slot ごとの K/V state と buffers を用意します。MTP drafter のロードに失敗した場合は stderr に `strata generate: batch MTP slot ...` を出して status 1 で終了します。serve 起動時の slot residual buffer の確保・bind に失敗した場合も `strata serve: batch MTP slot ...` と理由を出し status 1 で終了します。`engine/src/program/generate.cpp:8351-8379,13641-13660`。

decode 時は各 active slot の現在 token 行に proposal 行を加えて verifier を呼びます。proposal が verifier の選択 token と一致し、EOS・stop 条件に当たらず、生成上限と context に余裕がある場合だけ proposal も commit されます。条件を満たさない proposal は採用されず、その slot は通常 token だけを確定します。window 容量を超える slot は順番に回ります。`engine/src/program/generate.cpp:17119-17123,17175-17200,17268-17274`。

Qwen3.6-35B 専用 engine も起動時に `E.bmtp` を設定します。decode window ごとに active/eligible slot と空き verify row を調べ、MTP proposal を走らせられなければ `window_plain()` に fallback します。`STRATA_Q36_MTP_SAMPLED` が設定されていない場合、sampling が logits を必要とする slot は MTP proposal の対象外です。`engine/src/qwen35/q36_engine.cu:4900-4910`。

Python 側の `os.environ.get` 判定は関数が呼ばれるたびに行われます。`slots_draft_nothing` と `batch_mtp_dropped` は環境変数が unset / 空 / `0` のときを無効側と扱います。一方 `slot_drafts_by_default` は unset / 空 / `0` 以外を有効側とします。engine の実読み取りとは値判定が異なる部分があります。`terminal/strata_control/drafting.py:930-960,1155-1164`。

## ログと測定値

通常 engine では条件不足を stderr の `strata generate: WARNING: --batch-mtp is off: ...` で知らせます。batch MTP が有効で slot drafter を作成できた CUDA/HIP 経路では `strata generate: --batch-mtp: N slot drafters on CUDA...` と、各 drafter の private K/V state と buffers の概算 MiB、残 VRAM を stderr に出します。SYCL の環境変数ゲートは同じ warning 形式ですが、確認した箇所に有効化を示す同等の drafter 数ログはありません。Qwen3.6-35B の専用 engine では、環境変数による有効化そのものを示すログは確認できません。`engine/src/program/generate.cpp:7843-7855,8372-8378`、`engine/sycl/src/program/generate.cpp:4379-4385`、`engine/src/qwen35/q36_engine.cu:5559-5562`。

この文書では性能値を記載しません。`docs/BATCHING.md` には特定の構成に限った測定がありますが、環境変数単独の測定ではなく CLI の batch MTP 経路の測定です。

## 根拠

- `engine/src/program/generate.cpp:7841-7879` — 環境変数の判定、条件 gate、warning、pipelined MTP との関係。
- `engine/src/program/generate.cpp:8351-8379,13641-13660,17119-17200` — slot drafter の作成、serve の失敗経路、decode window。
- `engine/sycl/src/program/generate.cpp:4377-4385,7929-7940,9987-10042` — SYCL の判定、residual buffer、decode window。
- `engine/src/qwen35/q36_engine.cu:5373-5383,5556-5562,4900-4910` — Qwen3.6-35B 専用 engine の CLI / env 判定と runtime window。
- `terminal/strata_control/drafting.py:930-961,1146-1164`、`terminal/serve/server_parts/engines.py:847-851` — Terminal 側の予測・表示用判定。
