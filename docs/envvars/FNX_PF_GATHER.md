# `FNX_PF_GATHER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata-split` の Qwen3.8-Flash-Next prompt path で、カード間の chunk sum を各カードへ配る all-gather を、従来の ring forwarding にするか direct gather にするか選ぶ。CUDA build は既定で ring、HIP build は既定で direct gather。ring は完成した行部分をカード間で順に転送し、direct gather は各部分の加算完了時に全カードの host gather buffer へ書き込む。どちらも `pf_ring_run` 内で chunk sum を `x` に戻す実装であり、変わるのはこの配布計画である。選択値を表示する専用ログはない。

このコードは `STRATA_BUILD_SPLIT` が有効で、Linux CUDA または HIP の `strata-split-N` executable を組み込む場合のもの。通常の `strata` engine の設定ではない。split engine の起動経路は `docs/SPLIT_ENGINE.md` に記載されている（ソース根拠: `engine/CMakeLists.txt:922-926`, `engine/src/split/CMakeLists.txt:1-7,76-91`）。値の読み取りと選択は `Engine::prefill_alloc()` にある（`engine/src/split/src/prefill.cu:854-857,1201-1208`）。

## 値と判定

`std::getenv` で文字列を取得し、`std::strcmp` による大文字小文字を区別する完全一致だけを判定する。数値変換、trim、部分一致は行わない。未設定と空文字はともにどの比較にも一致せず、backend ごとの既定値になる。

| build | unset / 空文字 | direct gather になる値 | ring になる値 | その他（例） |
|---|---|---|---|---|
| CUDA (`FNX_HIP == 0`) | ring | `direct` のみ | `ring`、および `direct` 以外の全値 | `DIRECT`, ` ring`, `0`, `true`, `ring-extra` は ring |
| HIP (`FNX_HIP != 0`) | direct gather | `ring` 以外の全値 | `ring` のみ | `direct`, `RING`, ` ring`, `0`, `true` は direct gather |

この差は `r.direct = gather && strcmp(gather, "direct") == 0`（CUDA）と `r.direct = !(gather && strcmp(gather, "ring") == 0)`（HIP）による（`engine/src/split/src/prefill.cu:1203-1208`）。

## 有効になる条件

- split engine がビルドされ、対象モデルを実行する `strata-split-N` の prompt path が使われる必要がある。split は CMake option `STRATA_BUILD_SPLIT` が既定 OFF の別 executable で、CMake はカード数 2、3、4 を対象に構成する（`engine/CMakeLists.txt:922-926`, `engine/src/split/CMakeLists.txt:1-7,116-120`）。
- 変数が選ぶ計画が実行されるのは、HIP RCCL all-reduce が選ばれておらず、かつ HIP の小 chunk all-to-all 経路にも入らず、`pf_ring_run()` が呼ばれる場合。`pf_ring()` は RCCL を先に処理し、HIP では `p.a2a_rows > 0 && C <= p.a2a_rows && !own_out` のときも ring runner を迂回する（`engine/src/split/src/prefill.cu:723-755`）。
- CUDA/HIP とも、CLI 引数による同等の上書きはこの読み取り箇所にない。`FNX_PF_GATHER` は `Engine::prefill_alloc()` の初期化時に各カード分読み取られ、その時点で `r.plan` を作る。実行中にプロセス環境を変えても既存 Engine の計画は更新されず、Engine を作り直した場合は新しい環境値を読む（`engine/src/split/src/prefill.cu:854-857,1197-1208,1223`）。
- 変数の値によってアプリケーションログを出したり、モデル・CLI 引数・token 選択を変えたりする分岐はない。直接の効果はカード間 chunk sum の gather 計画に限られる（`engine/src/split/src/prefill.cu:1201-1208,1223`; `engine/src/split/src/pf_ring_plan.hpp:43-73,83-105`）。

## 実行時の詳細

`prefill_alloc()` は各カードの prompt buffer を初期化するループ内で環境値を読み、backend 別に `r.direct` を設定し、カード数とカード番号から `pf_ring_plan_direct()` または `pf_ring_plan()` の step 列を保存する（`engine/src/split/src/prefill.cu:854-857,1197-1208,1223`）。関数内 static cache はなく、prompt chunk ごとに環境を読み直す実装でもない。

prompt の `prefill()` は chunk ごとに `prefill_pass()` を実行する（`engine/src/split/src/prefill.cu:1300-1308,1358-1369,1391-1403`）。各カードの chunk sum は `pf_ring()` から保存済み計画を使う `pf_ring_run()` へ進む（`engine/src/split/src/prefill.cu:723-755`）。通常 ring 計画は reduce-scatter 後、完成した行部分を ring 上で順送りして全カードに揃える。direct 計画は同じ reduce-scatter の後、完成した部分を各カードの gather buffer に直接書き、各カードの flag を待ってから出力する（`engine/src/split/src/pf_ring_plan.hpp:1-7,43-73,83-105`; `engine/src/split/src/pf_common.cuh:130-149,298-379`）。`pf_ring_run()` は gathered half を `OUT` で `x` に戻す（`engine/src/split/src/pf_common.cuh:383-399`）。

既定時の ring/direct は値を文字通り選択する規則を示すもので、RCCL や小 chunk all-to-all が使われればその chunk sum の実処理は別経路になる。HIP RCCL は `rccl_on_` の場合 `p.rccl` に設定され、`pf_ring()` はその場合に all-reduce の後 return する（`engine/src/split/src/prefill.cu:1014-1020,723-742`）。

## ログと測定値

この変数の選択値や ring/direct の選択理由を出すログは見つからない。split prompt path は ring wait の flag が来ない場合を含め、pass 完了を最大 120 秒待ち、超過時に `prefill: a pass did not finish in 120 s (a ring step's flag never came?)` を `std::runtime_error` として送出する。ring error が立った場合は `prefill: ring error <数値>` を送出する（`engine/src/split/src/prefill.cu:1787-1803`）。これらは共通の prompt ring 経路の失敗であり、`FNX_PF_GATHER` 固有の診断ではない。

コードコメントには4カード時の ring host-to-host forwarding のコストに関する記述があるが、対象構成や測定条件を本調査で裏付けられる公開資料は確認できなかったため、性能値としては記載しない。

## 根拠

- `engine/CMakeLists.txt:922-926` — split engine は opt-in。
- `engine/src/split/CMakeLists.txt:1-7,76-91,116-120` — split executable、CUDA/HIP 条件、カード数。
- `engine/src/split/src/prefill.cu:854-857,1197-1208,1223` — 読み取り、backend 別判定、計画作成。
- `engine/src/split/src/prefill.cu:723-755` — RCCL・小 chunk 回避経路と ring runner 呼び出し。
- `engine/src/split/src/pf_ring_plan.hpp:1-7,43-73,83-105` — ring と direct の計画。
- `engine/src/split/src/pf_common.cuh:130-149,298-399` — direct gather の書き込み・同期と ring 出力。
- `engine/src/split/src/prefill.cu:1787-1803` — prompt pass の timeout と ring error。
