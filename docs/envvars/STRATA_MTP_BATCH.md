# `STRATA_MTP_BATCH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

MTP（draft layer）を使うとき、プロンプト読み込み中に draft layer の K/V cache を `Prefill::draft_kv` のバッチ計算で埋める経路を抑止する。未設定時はこの経路を試し、値の先頭文字が `0` のときだけ試さない。抑止または適用条件を満たさない場合、呼び出し元は drafter 自身の `MtpDrafter::prefill` にフォールバックする。

## 値と判定

| 環境変数の状態・値 | `Prefill::draft_kv` の判定 |
|---|---|
| 未設定 | 有効（抑止しない） |
| 空文字 | 有効（`v[0]` は NUL であり `'0'` ではない） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効。`false` を返し、理由は `STRATA_MTP_BATCH=0` |
| その他（例: `1`, `true`, ` 0`, `false`） | 有効（抑止しない） |

数値変換や文字列全体の比較はなく、先頭1文字だけを大文字小文字の区別なく（数字なので該当なし）比較する。したがって `STRATA_MTP_BATCH=0anything` も無効化する一方、`STRATA_MTP_BATCH= 0` は無効化しない。この変数はバッチを強制的に成功させる設定ではなく、コードがバッチを試すのを止めるための設定である。

## 有効になる条件

- MTP が有効な経路でプロンプトの chunk が処理されること。MTP が無効なら `draft_kv` は呼ばれない。
- レイヤー分割（multi-GPU）では CUDA 側のサーバー経路が別の `STRATA_SPLIT_MTP_BATCH` によってバッチ経路を opt-in する。`STRATA_MTP_BATCH` はその経路でも追加の抑止条件になる。SYCL のサーバー経路は `!multi_gpu` のときだけ `draft_kv` を試す。
- `draft_kv` 内で prompt scratch と対象データが利用可能で、drafter の K/V が paged（`kv_mode == 0`）であること。ring（`kv_mode == 2`）は `STRATA_MTP_BATCH_RING` が未設定、または先頭文字が `0` 以外の場合に限り対象となる。その他の K/V mode、hybrid K/V、異なるデバイスは対象外。
- 必須 drafter tensor が揃い、token embedding がこの経路で gather 可能であり、 scratch が少なくとも64行分確保できること。満たさない場合は通常の drafter pass に戻る。

## 実行時の詳細

CUDA の `src/prefill/prefill.cpp` と SYCL の `sycl/src/prefill/prefill.cpp` の両方に同じ `static const bool off` 判定がある。値は `draft_kv` の最初の呼び出し時に一度だけ読み取られて static local に保持されるため、そのプロセス内で後から環境を変更しても判定は更新されない。

抑止された場合、`draft_kv` は `false` を返すがエラー文字列は設定しない。通常の単一 GPU の generate/serve 呼び出し元はこの戻り値を見て `mtp.prefill(...)` を呼ぶ。CUDA のレイヤー分割経路も、試行が不成立でエラーがなければ同じ drafter pass に戻す。実際にバッチ処理が成功すると、各 chunk の次トークン埋め込みと prompt の最終 residual 行から drafter の K/V を計算して cache に append する。GPU 処理のエラーは `err` に記録され、通常の fallback ではなく呼び出し元へ伝わる。

この分岐は通常ログを出さない。`STRATA_DRAFT_TIMING` が設定されている場合、成功した CUDA または SYCL バッチ処理は標準エラーに `strata draft kv: ...` の timing 行を出す。サーバー側の `STRATA_SNAPSHOT_VERIFY` 診断は `DRAFT_PREFILL path=batched` または `path=token` を出し、経路を区別できる。

## 文書との照合

`docs/MULTI_GPU.md` はレイヤー分割での `STRATA_SPLIT_MTP_BATCH` と `STRATA_MTP_BATCH_RING` を説明しているが、`STRATA_MTP_BATCH` 自体の既定動作や値判定は説明していない。現行実装では単一 GPU の経路でバッチ試行が既定で有効であり、この変数の先頭が `0` のとき無効になる。

## 根拠

- `src/prefill/prefill.cpp:1341-1358` — CUDA 側の読み取り、値判定、無効化理由、K/V mode・hybrid・device 条件。
- `sycl/src/prefill/prefill.cpp:1301-1317` — SYCL 側の同じ判定と適用条件。
- `src/prefill/prefill.cpp:1373-1394`、`sycl/src/prefill/prefill.cpp:1332-1357` — tensor / embedding 条件と64行単位の scratch 条件。
- `src/prefill/prefill.cpp:1485-1509`、`sycl/src/prefill/prefill.cpp:1467-1503` — K/V の計算、cache append、エラーと任意の timing 出力。
- `src/program/generate.cpp:8092-8123` — CUDA サーバーでのレイヤー分割 opt-in、fallback、診断出力。
- `src/program/generate.cpp:12469-12480`、`sycl/src/program/generate.cpp:11679-11689` — generate 経路でのバッチ試行と drafter pass fallback。
- `sycl/src/program/generate.cpp:7665-7673` — SYCL サーバーでの単一 GPU 条件、fallback、診断出力。
- `include/strata/program/draft_kv_plan.hpp:21-42` — CUDA サーバー側で multi-GPU 時に使う別の `STRATA_SPLIT_MTP_BATCH` 計画条件。
- `docs/MULTI_GPU.md:103-110` — 関連するレイヤー分割経路についての説明。
