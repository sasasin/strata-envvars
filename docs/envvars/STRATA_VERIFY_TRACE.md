# `STRATA_VERIFY_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

verifier の handshake イベントと各 GPU window の進捗 breadcrumb を記録し、失敗や watchdog 診断時に `stderr` へ出す診断用フックである。通常の推論結果や verifier の待ち時間・timeout 値を選ぶ設定ではない。trace 有効時は verifier の初期化で breadcrumb 用 mapped 領域を要求し、記録点を追加する。CUDA/HIP 共通の `engine/src/core/verify.cpp` と SYCL の `engine/sycl/src/core/verify.cpp` に実装があり、ほかの verifier 実装からこの名前を読む箇所は確認できなかった（それぞれ `:344`, `:191`）。

## 値と判定

両実装の `env_on` は `std::getenv` の結果が null でなく、先頭文字が NUL でも `'0'` でもない場合に true を返す。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（CUDA/HIP: `engine/src/core/verify.cpp:336-339`; SYCL: `engine/sycl/src/core/verify.cpp:151-154`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP verifier | off | 空でない文字列で先頭が `0` 以外。例: `1`, `true`, `false`, ` 0`, `0anything` 以外 | 空文字、`0`, `0anything`（先頭文字だけを見る） |
| SYCL verifier | off | 同上 | 同上 |

したがって `false` や `00` は有効、`0anything` は無効である。空白を含む値は trim されず、先頭が空白なら有効になる。CLI 引数、設定ファイル、別環境変数による上書きや優先順位はない。

## 有効になる条件

- 実行バイナリに該当する CUDA/HIP verifier または SYCL verifier が含まれ、その verifier 経路が実行されること。名前の直接読み取りはこれら 2 実装のみである（`engine/src/core/verify.cpp:344`; `engine/sycl/src/core/verify.cpp:191`）。
- 設定はプロセス内での初回評価ではなく、各実装の翻訳単位スコープにある `const bool g_trace` 初期化時に読み込まれるため、プロセス開始後の環境変更は反映されない（同上）。
- GPU breadcrumb は verifier 初期化時に `mapped` が成功した場合だけ記録される。失敗時には pointer と長さを null/0 に戻すが、trace 全体を off には戻さない。この場合も host event ring と `strata verify trace (#649): on` の表示は残り得るが、dump には GPU breadcrumb が出ない（CUDA/HIP: `engine/src/core/verify.cpp:1245-1260`; SYCL: `engine/sycl/src/core/verify.cpp:800-814`）。
- 追加の server-mode や CLI 条件はない。serve watchdog が verifier 診断を要求する経路でも dump を含められるが、通常の推論中に常時 dump する設定ではない。

## 実行時の詳細

有効時、全 verifier が共有する 4096 件の host-side ring に時刻、verifier、window、step、layer、イベント名、handshake word を記録する。dump はそのうち直近最大 160 件を出力する。GPU breadcrumb 領域は model layer 数と profiling stamp 数から大きさを決め、window ごとに zero clear し、GPU stamp 地点を mapped 領域へ書き込む（CUDA/HIP: `engine/src/core/verify.cpp:634-644`, `:699-723`, `:1245-1251`, `:1516-1519`, `:3720-3723`; SYCL: `engine/sycl/src/core/verify.cpp:379-389`, `:501-525`, `:800-805`, `:1052-1056`, `:2413-2414`）。

trace は timeout の閾値を変更しない。層の doorbell timeout では診断と GPU wait 解放の前後に trace を出す（CUDA/HIP: `engine/src/core/verify.cpp:4031-4061`; SYCL: `engine/sycl/src/core/verify.cpp:2673-2684`）。stream/queue が完了したのに層が応答しない `NEVER-RANG` 経路や、adaptive copy gate timeout でも dump する（CUDA/HIP: `engine/src/core/verify.cpp:4023-4028`, `:3673-3689`; SYCL: `engine/sycl/src/core/verify.cpp:2654-2670`）。

## ログと測定値

初期化時の stderr 表示は CUDA/SYCL では `strata verify trace (#649): on`。HIP では同じ接頭辞に加え、Strata が `STRATA_VERIFY_COHERENT` と `STRATA_DOORBELL_STORE` の判定、および `HIP_HOST_COHERENT`, `HSA_ENABLE_SDMA`, `GPU_MAX_HW_QUEUES` の現在値を表示する（CUDA/HIP: `engine/src/core/verify.cpp:1252-1260`; SYCL: `engine/sycl/src/core/verify.cpp:806-814`）。後者 3 変数の外部側の意味はこの文書の対象外。

dump は `strata verify trace (#649): the last ... handshake events ...` で始まり、GPU breadcrumb がなければ `strata verify trace: no GPU breadcrumb in this window (the GPU never started it)` と出す。ある場合は到達 layer と stamp 時刻を表示する（CUDA/HIP: `engine/src/core/verify.cpp:714-753`; SYCL: `engine/sycl/src/core/verify.cpp:516-555`）。timeout 時は既存の `verify: timed out at layer ...` などの失敗文字列も返る。性能値の計測・主張は確認していない。

server の `death_note()` は watchdog の `issue #29` 行を engine log 全体の末尾 256 KiB から探す。trace dump は約 30 KB になり得るため、4 KiB tail だけを見て watchdog 行を取り落とさないための処理である（`terminal/serve/server.py:1086-1103`; 補足テスト記述 `terminal/serve/test_server.py:6196-6206`）。

## 根拠

- `engine/src/core/verify.cpp:336-345` — env 判定と CUDA/HIP 共通の一度限りの値保持。
- `engine/src/core/verify.cpp:634-644`, `:699-723` — host event ring と dump の出力。
- `engine/src/core/verify.cpp:1245-1260`, `:1516-1519`, `:3720-3723` — breadcrumb 領域、記録点、window ごとの初期化。
- `engine/src/core/verify.cpp:3673-3689`, `:4023-4028`, `:4031-4061` — gate timeout、応答欠落、通常 timeout の診断経路。
- `engine/sycl/src/core/verify.cpp:151-194`, `:379-389`, `:501-557`, `:800-814`, `:1052-1056`, `:2413-2414`, `:2654-2684` — SYCL 側の対応実装。
- `engine/include/strata/core/verify.hpp:104-108`, `:641-646`; `engine/sycl/include/strata/core/verify.hpp:68-72`, `:412-417` — 公開診断 API と trace 領域の説明。
- `terminal/serve/server.py:1086-1103` — 長い trace 出力後も watchdog 行を見つける server の診断処理。
