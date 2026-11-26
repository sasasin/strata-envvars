# `STRATA_PREFILL_EQUAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプト prefill のチャンク長の決め方を切り替える。通常は上限チャンクを満杯に使い、最後に短いチャンクを読む。equal cut が選ばれると、同じチャンク数を保ちながら長いセグメントを均等な長さに分け、最後だけ短くなる分割を避ける。これはトークンの処理順を変える設定ではなく、チャンクの境界と、それに伴うバッファ借用量の計算に使われる。実装は CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL の `engine/sycl/src/program/generate.cpp` にある（`engine/include/strata/prefill/equal_cut_rule.hpp:49-56,96-112`、`engine/src/program/generate.cpp:11183-11218`、`engine/sycl/src/program/generate.cpp:6647-6664`）。

## 値と判定

この名前を読むのは C++ の `std::getenv` で、数値や真偽値への parse はしない。実装経路によって既定値と有効条件が異なる。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_PREFILL_FUSED` 定義、`STRATA_PREFILL_MMQ` 未定義 | 単一 GPU は equal cut。layer split は通常 cut。 | 単一 GPU: 値の先頭文字が `0` でなければ equal cut（空文字を含む）。layer split: 先頭文字が `1` のとき旧 opt-in cut。 | 先頭文字 `0` は両経路で通常 cut。layer split は先頭文字 `1` 以外も通常 cut。 |
| 上記以外（SYCL を含む） | equal cut 無効。 | 値の先頭文字が `1` のとき旧 opt-in cut。 | 空文字、`0`、`true`、`01` など先頭文字が `1` でない値。 |

比較は先頭の 1 byte のみで、大文字小文字、空白、残りの文字列、数値としての妥当性を検査しない。従って、前者の単一 GPU 経路では `0anything` は無効、`1anything`・`true`・空文字は有効。前者の layer split と後者では `1anything` が有効だが、`true` と空文字は無効。`STRATA_PREFILL_FUSED` と `STRATA_PREFILL_MMQ` の組み合わせはコードのプリプロセッサ分岐条件であり、CUDA/HIP CMake の fused prompt library は `STRATA_PREFILL_FUSED=1` を定義する（`engine/cmake/backends/cuda.cmake:152`、`engine/cmake/backends/hip.cmake:47`）。

## 有効になる条件

- fused prompt build で MMQ が無効のとき、単一 GPU 判定は「layer split なし、複数 GPU なし、peer card なし、head alias なし、`--batch` が 1 以下」。この経路は unset でも equal cut を選び、値の先頭が `0` なら通常 cut に戻す（`engine/include/strata/prefill/equal_cut_rule.hpp:49-56`、`engine/src/program/generate.cpp:11183-11194,20580-20585`）。
- 同じ build の layer split / peer / batch 等では unset は通常 cut。先頭文字 `1` のときだけ旧 opt-in cut になり、先頭文字 `0` は通常 cut（同上）。
- その他の build では `1` で始まる値が旧 opt-in cut を選ぶが、セグメントが一つのチャンク内に収まる場合、または通常 cut の最終端が `stream_all_min_tokens()` 未満の場合はチャンク長を変更しない（`engine/src/program/generate.cpp:11209-11218`、`engine/sycl/src/program/generate.cpp:6654-6664`）。
- fused / non-MMQ 経路の equal cut は、要求セグメントが一チャンクを超え、等分後の最終チャンクが floor 以上で、計算された等分チャンクが configured chunk 上限を超えない場合に使う。上限が 8192 以上のとき、等分チャンクが 6144 未満（2 分割なら 5400 未満）なら通常 cut に戻す（`engine/include/strata/prefill/equal_cut_rule.hpp:65-76,96-112`）。
- この経路の単一 GPU 判定を満たさないとき、先頭 `1` は旧 opt-in 規則を選ぶ。旧規則も一チャンクだけの場合や通常 cut の端が floor 未満なら通常 cut を維持する（`engine/include/strata/prefill/equal_cut_rule.hpp:83-94`）。
- host-aware prefill plan が `0 < plan < cap` を選ぶ場合は `balanced_chunk()` が使われ、この環境変数の cut 関数を通らない（`engine/src/program/generate.cpp:11197-11199,11224-11226`）。CLI の `--prefill` / `--prefill auto` が決める上限や自動計画、空き cache に収まるかどうかは別途適用される。serve の自動計画が equal cut のバッファ tail を数える条件も限定される（fused / non-MMQ、one GPU、tail loan 有効、small path でない等。`engine/src/program/generate.cpp:11846-11857,12664-12676`）。
- `--prefill-pipe` の pipeline 分割は別の処理で、`Prefill::pipeline_chunk()` が独自にチャンク数と floor を評価する。そこではこの環境変数を読まない（`engine/src/prefill/prefill.cpp:3647-3658`）。

## 実行時の詳細

値は `generate.cpp` 内の関数ローカル `static` 初期化で読み取られるため、各 engine process で該当関数に初めて到達した時点の値が cache され、その後の環境変更は反映されない。fused / non-MMQ 経路は `equal_cut_one` と `equal_cut_split` をそれぞれ初期化し、他経路は `equal_chunks` を初期化する（`engine/src/program/generate.cpp:11190-11209`、`engine/sycl/src/program/generate.cpp:6654`）。

equal cut は `n = ceil(tokens / max_chunk)` を保ち、各チャンクの基準長を `ceil(tokens / n)` とする。旧 opt-in 規則はこの長さを 256-token 境界に切り上げるが、新しい単一 GPU equal cut は切り上げない。通常 cut は入力トークン数を 256 境界に切り上げて `max_chunk` で上限を設ける（`engine/include/strata/prefill/equal_cut_rule.hpp:58-63,83-112`、`engine/src/program/generate.cpp:11159-11164,11213-11218`）。選ばれたチャンク長は prompt path の必要バッファ数・cache 借用量の計算にも使われる。借用量が合わない場合は通常 cut に戻すか、利用可能な slot に合うまで chunk を縮める。なお、等分化を見送ったケースでも新 cut の方だけが cache に収まる場合には equal cut を採用する分岐がある（`engine/src/program/generate.cpp:20588-20606,20661-20689,24027-24049`）。

## ログと測定値

環境変数の値や不正値を報告する専用ログはない。`--prefill auto` では選択した prompt chunk を `strata generate: prompt chunk auto: %lld tokens` と出力し、borrow 不能時は `strata generate: prompt path allocates its own buffers (no cache slots to borrow)` と出る（`engine/src/program/generate.cpp:24061-24063`、`engine/sycl/src/program/generate.cpp:13325-13353`）。equal cut を使うかどうかではなく、借用可能な slot の差による調整が発生した場合は `strata generate: prompt chunk ...` または `strata serve: prompt chunk ...` の行が出る（`engine/src/program/generate.cpp:20667-20689,24046-24049`）。この変数の無効値だけを理由とする警告・終了経路はない。

`docs/DETAILS.md:1275` は CUDA の `STRATA_PREFILL_EQUAL=1` を opt-in として記載している。現行ソースでは fused / non-MMQ の単一 GPU 経路は unset でも有効で、先頭 `0` で無効化するため、この記述はその経路の既定値を反映していない。測定値はこの文書では記載しない。

## 根拠

- 直接の読み取りと static cache: `engine/src/program/generate.cpp:11190-11209`、`engine/sycl/src/program/generate.cpp:6654`。
- 値から cut を選ぶ規則、chunk 算出: `engine/include/strata/prefill/equal_cut_rule.hpp:49-56,58-63,65-112`。
- prompt / serve path への適用と fallback: `engine/src/program/generate.cpp:11183-11226,11846-11857,20580-20689,24018-24063`、`engine/sycl/src/program/generate.cpp:6647-6664,11404-11451,13312-13353`。
- build macro 定義と関連 pipeline 経路: `engine/cmake/backends/cuda.cmake:152`、`engine/cmake/backends/hip.cmake:47`、`engine/src/prefill/prefill.cpp:3647-3658`。
