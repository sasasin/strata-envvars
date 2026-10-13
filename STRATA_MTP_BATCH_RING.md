# `STRATA_MTP_BATCH_RING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

ドラフター層の prompt K/V を `Prefill::draft_kv()` でまとめて計算するとき、ドラフターの K/V が ring（ストリーミング）方式でもこのバッチ経路を試すかどうかを制御します。未設定時は ring でも許可します。`STRATA_MTP_BATCH=0` がバッチ経路全体を止めるのに対し、この変数を `0` にしても paged K/V のバッチ処理には影響しません。

対象実装は CUDA 系の `src/prefill/prefill.cpp` と SYCL の `sycl/src/prefill/prefill.cpp` で、判定と ring の適用条件は同じです。単一 GPU では MTP がある場合に prompt chunk ごとにバッチ経路を試します。CUDA の layer split では、さらに `STRATA_SPLIT_MTP_BATCH` が有効で、split の最終段に native embedding がある場合に試します。SYCL の server 呼び出し側は multi-GPU 時にこの経路を試しません。

## 値と判定

`getenv()` の値の先頭文字だけを調べます。文字列全体の parse や数値変換はありません。

| 値 | ring K/V での扱い |
|---|---|
| 未設定 | 許可（既定） |
| 空文字 | 許可（設定値の先頭が `\0`） |
| 先頭が `0`（例: `0`, `0foo`） | 不許可 |
| それ以外（例: `1`, `true`, `false`, ` 0`） | 許可 |

大文字小文字、後続文字、空白は判定しません。値は `Prefill::draft_kv()` 内の `static const bool` に初回評価結果が保存されるため、同一実行ファイル内で最初にこの関数へ到達した後の環境変更は反映されません。CUDA と SYCL は別実装です。

根拠: `src/prefill/prefill.cpp:1341-1356`、`sycl/src/prefill/prefill.cpp:1301-1315`。

## 有効になる条件

この変数だけではバッチ経路を開始しません。ドラフターを使い、呼び出し側が `Prefill::draft_kv()` を試す経路であり、かつドラフターの `kv_mode` が ring (`2`) の場合に限り、この値が許可/拒否を決めます。

- ring は、ドラフターが `--kv-resident` による K/V streaming の対象で、ドラフターの window が全 context より短い場合などに作られます。ドラフター用 K/V ring は `window + 4 * max_t + 64` cells を要求します。ring が成立しない場合や、pinned RAM が足りず全体を VRAM に置く fallback になった場合は ring ではなく、この変数の判定対象外です（`src/core/mtp.cpp:325-349`）。
- 実際の mode は `kv_plan()` が `ring_cells > 0` かつ `STRATA_KV_RING_OFF` が未設定のとき、ring slot 数が全 page 数より少なければ `2` にします（`src/core/layer.cpp:634-651`）。
- `STRATA_MTP_BATCH=0` なら、この変数の値に関係なくバッチ経路を拒否します。ring 以外で `kv_mode != 0` の場合、hybrid K/V、別 GPU の drafter、必要な scratch や tensor の不足などでもバッチ経路は拒否されます（`src/prefill/prefill.cpp:1346-1379`、SYCL 対応箇所は `sycl/src/prefill/prefill.cpp:1305-1338`）。
- CUDA layer split では `STRATA_SPLIT_MTP_BATCH` が未設定/無効なら split の既定動作としてドラフター自身の pass を使います。変数を有効にしても `--native` pack でなければバッチを試しません（`include/strata/program/draft_kv_plan.hpp:16-41`、`src/program/generate.cpp:8092-8117`）。

## 実行時の詳細

`STRATA_MTP_BATCH_RING=0` で ring 方式のドラフターに到達すると、`draft_kv()` は `the drafter's K/V is a ring and STRATA_MTP_BATCH_RING=0` を理由に `false` を返します。呼び出し側は通常の `mtp.prefill()`（ドラフター自身の K/V pass）へ進みます。CUDA split では、`STRATA_SPLIT_MTP_BATCH=1` によるバッチ試行が拒否された理由を一度 stderr に出します。表示形式は `strata serve: STRATA_SPLIT_MTP_BATCH=1 declined, the drafter's own pass runs: <reason>` です。単一 GPU の生成経路ではこの拒否理由をこの変数専用のログとしては出しません（`src/program/generate.cpp:8103-8119,12474-12480`）。

許可された ring バッチでは、1 batch の書き込み行が同じ ring slot を共有しないよう、batch 上限を `(n_slots - 1) * page_size` 以下（64 行単位に切り下げ）に制限します。CUDA では scratch から求めた上限とも比較します。SYCL でも同じ ring 上限を適用します（`src/prefill/prefill.cpp:1391-1394`、`sycl/src/prefill/prefill.cpp:1352-1357`）。

## 文書との照合

`docs/MULTI_GPU.md:103-123` は `STRATA_SPLIT_MTP_BATCH=1` の説明中で、`STRATA_MTP_BATCH_RING=0` にすると ring を旧来の pass に戻すと記載しています。これは実装の拒否と fallback に一致します。同節の性能値・出力比較は split batch 全体の測定であり、`STRATA_MTP_BATCH_RING` 単独の効果を測定したものではないため、本変数固有の性能や出力差は断定できません。

## 根拠

- `src/prefill/prefill.cpp:1341-1358,1391-1394,1485-1505` — 値の判定、ring の拒否条件、batch slot 上限、K/V 書き込みと完了。
- `sycl/src/prefill/prefill.cpp:1301-1317,1352-1357` — SYCL 側の同等の判定と ring 上限。
- `src/program/generate.cpp:8092-8119,12474-12480`、`sycl/src/program/generate.cpp:7665-7673` — 呼び出し条件、拒否時の通常 pass、ログ。
- `src/core/mtp.cpp:325-349`、`src/core/layer.cpp:634-651` — drafter ring のサイズと mode 設定。
- `include/strata/program/draft_kv_plan.hpp:16-41`、`docs/MULTI_GPU.md:103-123` — split 時の前提と文書記載。
