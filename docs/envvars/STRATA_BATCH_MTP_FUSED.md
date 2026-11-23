# `STRATA_BATCH_MTP_FUSED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

既に `--batch-mtp` が有効なサーバーのバッチ生成で、各 slot の MTP draft を個別に実行する代わりに、複数 slot をまとめた MTP forward pass を試す opt-in スイッチです。この変数だけではバッチ MTP を有効にしません。適格性チェックを通り、2 slot 以上を一緒に処理できる場合にだけ fused 経路を使います。非対応条件では従来の slot ごとの draft に戻ります。実装は `engine/src/program/generate.cpp` のバッチ生成ループと `engine/src/core/mtp.cpp` の `MtpDrafter::can_draft_slots` / `draft_slots` です（`engine/src/program/generate.cpp:17186-17192,17306-17345`; `engine/src/core/mtp.cpp:2244-2272,2735-2748`）。

## 値と判定

`generate.cpp` の関数内 `static const bool` 初期化子が `std::getenv` で読み、文字列全体や数値には変換せず、先頭バイトだけを調べます。未設定、空文字、先頭が `0` の値は off。それ以外の非空値は on です。したがって `0`、`0anything`、`0.1` は off、`1`、`2`、`true`、`false`、先頭に空白がある文字列は on です。大文字小文字や後続文字の妥当性検査はありません（`engine/src/program/generate.cpp:17188-17191`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 非 Metal ビルド | off | 空でなく先頭バイトが `0` 以外（例: `1`, `true`, `false`, ` 0`） | 空文字、先頭が `0`（例: `0`, `0anything`） |
| Metal ビルド | 設定判定は同じだが fused 実行不可 | なし | `can_draft_slots` が常に false を返すため個別 draft に戻る |

このフラグの値はプロセス内で最初に該当するバッチ生成ループが判定箇所へ到達した時に一度だけ読み込まれ、その後は `static` に保持されます。実行中に環境値を変えても反映されません（`engine/src/program/generate.cpp:17188-17192`）。

## 有効になる条件

- `--batch-mtp` が別途有効であること。これは `--batch-mtp` CLI、または `STRATA_BATCH_MTP` の空でない先頭文字が `0` 以外の場合などで成立します。この fused 変数単独では `batch_mtp` を true にしません（`engine/src/program/generate.cpp:7770-7777,17192`）。
- 通常のサーバー型 batch MTP の条件を満たすこと。`--batch` は 2 以上、MTP draft があり、`--spec T` は `T >= 2`、`--serve` が必要です。Metal は batch MTP の slot draft を無効にします。複数 GPU の layer split では各 stage が別 GPU にあり、複数 slot の pipelined groups も fused の対象外です（`engine/src/program/generate.cpp:7772-7785,7786-7802,17192`）。
- `batch_df2` が false で `stages.empty()`、つまり DFlash2 slot draft ではなく layer split でもない経路であること（`engine/src/program/generate.cpp:17192,17271-17274`）。
- その window で draft を続ける slot が少なくとも 2 つあり、`can_draft_slots` の前提を満たすこと。slot と共有 drafter のモデル・device・window・head 等が一致し、重複 slot がなく、各 slot の `keep` は 1 または 2、位置は非負である必要があります。hybrid KV、cell-floor、catch-up-all、top-2 診断、live chain、借用中 expert なども fused を不可にします（`engine/src/core/mtp.cpp:2244-2272`; `engine/src/core/mtp.cpp:98-105,699-702`）。
- 適格性チェックが false、または pending slot が 2 未満なら、同じ window の各 slot について residual 行をコピーして既存の `slot_mtp[b]->draft(...)` を呼ぶ経路になります。fused 側の実行中に初期化・GPU 処理が失敗した場合は個別経路に戻さず、エラーとして生成を終了します（`engine/src/program/generate.cpp:17271-17290,17323-17345`）。

## 実行時の詳細

バッチ verifier が slot の確定済み行を処理した後、fused 対象 slot の情報（drafter、residual 行、token、位置、確定行数）を集めます。先に `BT` / `BDONE` を stdout に flush し、その後で fused draft を開始するため、draft 完了前に確定済み token がクライアントへ出る構造です（`engine/src/program/generate.cpp:17217-17235,17306-17322`）。

実行可能なら `mtp.draft_slots` を一度呼びます。初回呼び出し時に staging buffer を遅延確保して `bm_ready_` に保持し、以後再利用します。処理 chunk の上限は `max_t`、fused GR / QSA の上限、および 8 の最小値です。slot 数や状態のため一括実行できなければ上記の個別 draft に戻ります（`engine/src/core/mtp.cpp:2275-2288,2331-2348,2735-2748`; `engine/src/program/generate.cpp:17323-17345`）。

GPU 完了待ちは `cudaStreamSynchronize` で行い、失敗時は `mtp batch: <CUDA/HIP runtime error>` 系のエラーを返します。`draft_slots` の false 戻りは呼び出し元で `ERR batch MTP fused: ...` と stdout に出し、生成を false で終了します（`engine/src/core/mtp.cpp:2851-2855`; `engine/src/program/generate.cpp:17323-17327`）。

## ログと測定値

初回の staging buffer 確保が成功した時に stderr へ `strata mtp: STRATA_BATCH_MTP_FUSED=1 active (chunk_cap=%d, staging %.2f MiB, attn_slots=%s)` を出します。値が on でも fused 経路に到達しない、適格性チェックに落ちる、または staging 確保前に失敗する場合、この active ログは出ません。`--batch-mtp` 自体の起動条件を満たさない場合は stderr に `strata generate: WARNING: %s is off: %s` を出して batch MTP を無効化します（`engine/src/program/generate.cpp:7772-7802`; `engine/src/core/mtp.cpp:2331-2348`）。`docs/DETAILS.md` にはこの変数自体の測定値を確認できません。

## 根拠

- `engine/src/program/generate.cpp:17186-17192` — 環境値の読み取りと fused 経路の3条件。
- `engine/src/program/generate.cpp:7770-7802` — `--batch-mtp` の独立した有効条件と未対応時の警告・無効化。
- `engine/src/program/generate.cpp:17271-17290,17306-17345` — slot の収集、個別経路への fallback、fused 呼び出しとエラー伝播。
- `engine/src/core/mtp.cpp:2244-2272` — fused slot 実行の前提と Metal での無効化。
- `engine/src/core/mtp.cpp:2275-2348,2735-2748,2851-2868` — buffer の遅延確保、active ログ、GPU 実行と完了待ち。
