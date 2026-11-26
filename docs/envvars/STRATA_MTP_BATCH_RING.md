# `STRATA_MTP_BATCH_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter の K/V が ring mode のとき、プロンプト処理中に drafter の K/V をまとめて作る経路を使うか決める。未設定または値の先頭文字が `0` 以外なら、その経路を許可する。先頭文字が `0` なら ring mode でのまとめ処理を辞退し、呼び出し側は drafter 本来の `mtp.prefill` に戻る。CUDA/HIP 共通実装と SYCL 実装に読み取りがある（`engine/src/prefill/prefill.cpp:2991-3013`、`engine/sycl/src/prefill/prefill.cpp:1857-1873`）。

これは MTP 自体を有効・無効にする設定ではない。K/V が通常の常駐 mode（`kv_mode == 0`）なら、`0` を指定してもこの設定を理由にまとめ処理を辞退しない。ring mode では、許可時も一つの batch の行が ring slot を共有しないよう、batch 行数を slot 数と page size から制限する（`engine/src/prefill/prefill.cpp:3007-3012,3050-3052`、`engine/sycl/src/prefill/prefill.cpp:1867-1872,1911-1913`）。

## 値と判定

`std::getenv` の戻り値を文字列全体として parse せず、未設定か、設定値の先頭文字が `0` かだけを見る。空文字では先頭文字が `0` ではないため許可される。数値変換、範囲検査、空白除去、大文字小文字変換はない（`engine/src/prefill/prefill.cpp:3006`、`engine/sycl/src/prefill/prefill.cpp:1866`）。

| 条件 | 未設定 | 許可される値の例 | ring mode のまとめ処理を辞退する値の例 |
|---|---|---|---|
| CUDA/HIP・SYCL の `Prefill::draft_kv` | 許可 | 空文字、`1`、`true`、`false`、` 0`（先頭文字が `0` 以外） | `0`、`00`、`0anything`（先頭文字が `0` のものすべて） |

## 有効になる条件

- MTP drafter がロードされ、プロンプト chunk の `Prefill::draft_kv` が呼ばれる必要がある。通常は `--mtp` と `--spec`（2 以上）を使う。`--mtp` が指定されても `--spec` が 2 未満なら `--mtp` は無視される（`engine/src/program/generate.cpp:8243-8247,8264`）。
- drafter の K/V が `kv_mode == 2`（ring）である必要がある。ring の構成には、K/V resident 設定が有効で、drafter の window が全 context より短く、`STRATA_KV_RING_OFF` が未設定であることが関わる。ring の K/V copy 用 pinned RAM が確保できない場合、MTP 初期化はログを出して fully resident に戻すため、この変数は ring 分岐を変えない（`engine/src/core/mtp.cpp:511-535`、`engine/src/core/layer.cpp:738-755`）。
- `STRATA_MTP_BATCH=0` は先に判定され、値が先頭 `0` なら batch 処理全体を辞退する。この場合も呼び出し側は通常の drafter prefill に戻る（`engine/src/prefill/prefill.cpp:3001-3011`、`engine/sycl/src/prefill/prefill.cpp:1861-1871`）。
- `kv_mode` が 0 なら、この変数による拒否はない。その他の非ゼロ mode は ring mode ではないとして辞退する。`kv_hybrid`、別 device、scratch 不足など別条件でも辞退し、この変数では解除できない（`engine/src/prefill/prefill.cpp:3007-3013,3052`、`engine/sycl/src/prefill/prefill.cpp:1867-1873,1909-1913`）。
- CUDA/HIP 共通実装では Metal build の場合、関数は環境変数を読む箇所より前に `false` を返す。SYCL には別実装がある（`engine/src/prefill/prefill.cpp:2991-3006`、`engine/sycl/src/prefill/prefill.cpp:1857-1866`）。
- server か CLI かでこの変数の判定値は変わらない。CLI の MTP drafter と server の MTP drafterが同じ `Prefill::draft_kv` の判定を通る。CUDA multi-GPU server の layer-split 経路では、さらに `STRATA_SPLIT_MTP_BATCH=1` などの計画条件が満たされた場合にだけ `draft_kv` を試す（`engine/src/program/generate.cpp:14763-14784`）。

## 実行時の詳細

値は `Prefill::draft_kv` の関数内 `static const bool ring_ok` を初期化するときに読み、以後その process の当該実装では cache される。最初の関数呼び出し後に環境を変更しても再評価されない。関数が一度も呼ばれなければ読み取りも起きない（`engine/src/prefill/prefill.cpp:2991-3007`、`engine/sycl/src/prefill/prefill.cpp:1857-1866`）。

`ring_ok` が false で `st.kv_mode == 2` の場合は、`draft_kv` が理由文字列 `the drafter's K/V is a ring and STRATA_MTP_BATCH_RING=0` を設定して `false` を返す。prompt callback はエラー文字列 `err` が空なら通常の `mtp.prefill` を呼ぶため、ring K/V をまとめて作らず drafter 自身の pass で処理する。許可時は ring でもまとめ処理を続け、batch の行数を `((n_slots - 1) * page_size)` 以下に丸めて制限する（`engine/src/prefill/prefill.cpp:3007-3013,3050-3052`、`engine/src/program/generate.cpp:24142-24148`、`engine/sycl/src/prefill/prefill.cpp:1867-1873,1911-1913`、`engine/sycl/src/program/generate.cpp:13365-13370`）。

## ログと測定値

この変数の読み取りだけでログは出ない。CUDA multi-GPU server の layer-split batch 経路では、辞退理由が空でない場合に一度だけ `strata serve: STRATA_SPLIT_MTP_BATCH=1 declined, the drafter's own pass runs: ...` を stderr に出すため、ring 拒否時は末尾に上記理由が付く。single-GPU の通常経路と SYCL の callback はこの理由をログに出さず、通常の drafter pass に戻る。`STRATA_SNAPSHOT_VERIFY` が設定されている server では、結果として `DRAFT_PREFILL path=token` が stderr に出る（`engine/src/program/generate.cpp:14781-14795,14806-14808`、`engine/sycl/src/program/generate.cpp:8622-8635`）。

`docs/SETTINGS.md:422` には on/off 設定として掲載されているが、許可・拒否の詳細は上記ソースの先頭文字判定に従う。この変数による性能測定値は確認できなかった。

## 根拠

- `engine/src/prefill/prefill.cpp:2991-3013,3050-3052` — CUDA/HIP 共通 `draft_kv` の設定読み取り、判定、ring batch の行数制限。
- `engine/sycl/src/prefill/prefill.cpp:1857-1873,1911-1913` — SYCL `draft_kv` の同等処理。
- `engine/src/core/mtp.cpp:511-535`、`engine/src/core/layer.cpp:738-755` — drafter ring K/V の成立と resident fallback。
- `engine/src/program/generate.cpp:8243-8247,24142-24148,14781-14798,14806-14808`、`engine/sycl/src/program/generate.cpp:8622-8635,13365-13370` — MTP の前提、呼び出し元、辞退後の fallback と観測ログ。
