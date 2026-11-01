# `DS4_SETTLE_STORE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main`。

## 役割

DeepSeek V4.1 の chunked prompt 処理後、次の decode に備えて RAM store に熱い expert を先読みするかを切り替えます。これは VRAM expert cache の入れ替えを止めるスイッチではありません。`DS4_SETTLE_MS` による通常の cache swap 処理の後に、追加で RAM store の preload を行うかを決めます（`src/dsv41/ds4_model.cu:7153-7182`）。

## 値と判定

`env_f` は環境変数が未設定なら渡された既定値を返し、設定されていれば `std::atof` の結果を `float` にして返します。`DS4_SETTLE_STORE` の判定はその値が `0.0f` と異なるかです（`src/dsv41/ds4_model.cu:1165,7182`）。文字列全体の妥当性検査や値域制限はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 通常は `0`（無効）。`DS4_DEFAULTS` が 0.2.6 モードなら `1`（有効） |
| 空文字 | `atof("")` 相当で `0`（無効） |
| 数値のゼロ（`0`, `0.0`, `-0` など） | 無効 |
| 数値の非ゼロ（負数を含む） | 有効 |
| 数値として読めない文字列 | `atof` は `0` を返すため無効 |
| 数値の後ろに文字が続く文字列（例: `1abc`） | `atof` が認識する先頭の数値部分が非ゼロなら有効。全体 parse はしない |

`atof` の結果を `float` に変換した後で比較するため、実装に明示的な最小値・最大値、clamp、エラー処理はありません。値が設定されているだけでは有効にならず、変換結果が非ゼロである必要があります。

## 有効になる条件

- `cache_settle()` に到達し、expert cache が有効で cache thread が存在する必要があります。条件を満たさない場合は関数冒頭で戻り、`DS4_SETTLE_STORE` を読みません（`src/dsv41/ds4_model.cu:7162-7164`）。CLI の `--no-expert-cache` は expert cache を無効化します（`src/dsv41/ds4_main.cpp:1331`）。
- RAM store が存在する必要があります。`store` が null なら短絡評価で変数判定と preload は行われません（`src/dsv41/ds4_model.cu:7182`）。store の初期化には正の store 容量、非空の layer、MXFP4 layer、file-backed experts が必要です。容量は CLI `--ssd-cache` または `DS4_STORE_GB` 等で決まり、ここでのスイッチ自体は store を作成しません（`src/dsv41/ds4_model.cu:5367-5382,5410-5418,5487-5492`; `src/dsv41/ds4_main.cpp:1325`）。
- `DS4_DEFAULTS` は変数が未設定のときの既定値だけに作用します。`DS4_DEFAULTS` が `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致すると 0.2.6 モードになり、未設定時の既定値が 1 になります。それ以外は既定値 0 です。設定された `DS4_SETTLE_STORE` の値がこの既定値に優先します（`include/strata/core/defaults_026.hpp:22-28`; `src/dsv41/ds4_experts_rule.hpp:210-211`; `src/dsv41/ds4_model.cu:7182`）。
- `--ssd-cache` は RAM store の容量を決めますが、`DS4_SETTLE_STORE` の値を上書きする同等の CLI 引数はありません（`src/dsv41/ds4_main.cpp:1325`; `src/dsv41/ds4_model.hpp:37-44`）。

## 実行時の詳細

`cache_settle()` は prompt stream の処理後、cache tick と layer cache の後処理に続いて呼ばれます（`src/dsv41/ds4_model.cu:9525-9533`）。関数はまず最大 `DS4_SETTLE_MS`（未設定時 800 ms）の範囲で通常の expert cache swap を処理します。RAM store の preload はその後に別途判定されるため、`DS4_SETTLE_STORE=0` でもこの VRAM cache swap 処理は無効になりません（`src/dsv41/ds4_model.cu:7162-7182`）。

有効で store がある場合、MTP layer を除き、VRAM にない expert のうち heat が 4.0 以上のものを集め、heat の降順に並べます。copy mode で CPU lane の RAM copy を既に持つ expert は、通常モードでは対象から除外されます。リストは store の最大 slot 数で打ち切られ、`store->preload(list, 0)` に渡されます（`src/dsv41/ds4_model.cu:7182-7202`; `src/dsv41/ds4_experts_rule.hpp:212-213`）。preload は空き容量に収まる対象の読み込みを開始し、読み込み完了を待ってから件数を返します（`src/dsv41/ds4_store.hpp:221-257`）。

対象変数は `cache_settle()` 内で `static` に保存されず、関数に到達するたびに評価されます。一方、既定値を決める `defaults_026()` は `DS4_DEFAULTS` の判定結果を static cache します。したがって `DS4_SETTLE_STORE` の変更は後続の評価に反映されますが、`DS4_DEFAULTS` の変更は最初の判定後には反映されません（`include/strata/core/defaults_026.hpp:25-28`; `src/dsv41/ds4_model.cu:1165,7182`）。

`o.verbose` が有効なら stderr に `ds4: RAM store: %zu hot experts read after the prompt (%.0f ms)` が出ます。無効ならこの preload 件数ログは出ません。preload の返却件数は `start_fill` できた件数で、読み込み完了数の成功検査として扱われてはいません。ここには preload 失敗時の専用エラーやプロセス終了処理はありません（`src/dsv41/ds4_model.cu:7200-7203`; `src/dsv41/ds4_store.hpp:224-257`）。

この変数は server idle 時の cache settling を切り替えません。idle 経路は `DS4_SETTLE_IDLE_MS` を参照して VRAM cache swap を行い、RAM store preload のコードを通りません（`src/dsv41/ds4_main.cpp:716-739`; `src/dsv41/ds4_model.cu:7213-7231`）。

## 根拠

- 候補名の全参照は `src/dsv41/ds4_model.cu:7182` の実読み取り、`src/dsv41/ds4_model.cu:7181` のコメント、`src/dsv41/ds4_experts_rule.hpp:210` のコメントです。値を読む実装は `env_f` を経由するこの1箇所です。
- `docs/release-notes-0.2.7.md:17,32-35` も、既定で post-prompt preload を止め、`DS4_SETTLE_STORE=1` で戻せること、および `DS4_DEFAULTS=026` で 0.2.6 の既定動作に戻すことを説明しています。数値性能の記載はこの文書ではソースコメント以外から一般化していません。
