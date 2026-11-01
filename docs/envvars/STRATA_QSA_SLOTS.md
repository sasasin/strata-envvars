# `STRATA_QSA_SLOTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

QSA（query selection and attention）を含むバッチ窓で、各 slot の block scores、top-k 選択、attention を行ごとに呼び出す代わりに、最大 8 行ずつまとめた launcher を使う opt-in です。各行はそれぞれの slot の indexer keys と K/V を読み、行ごとの出力領域に書きます。これは処理のスケジュールを変える設定で、値から QSA の計算対象や slot 数を指定するものではありません（`src/core/verify.cpp:316-320,1948-1979`; `include/strata/kernels/qsa_decode_attn.hpp:54`）。

## 値と判定

`src/core/verify.cpp:299-302` の `env_on()` が `getenv()` の戻り値を確認し、`STRATA_QSA_SLOTS` の結果を namespace-scope の `const bool g_qsa_slots` に保存します（同:320）。数値変換や文字列全体の比較は行いません。

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0`（例: `0`, `0abc`） | OFF |
| 先頭文字が `0` 以外（例: `1`, `2`, `true`, `false`, `off`, 空白で始まる文字列） | ON |

大文字小文字、後続文字、数値としての妥当性は判定されません。したがって `false` や `off` も ON です。環境値を読むのはこのグローバル初期化時の一度であり、engine 起動後に環境を変更してもこの値は更新されません（`src/core/verify.cpp:299-302,320`）。既定値は OFF です。

## 有効になる条件

- **バッチ窓であること**: `record_window()` 内の `batch_rec_` が true の経路だけが対象です。通常の単一系列窓ではこの環境変数による grouped launcher は使われません。バッチ窓の capture 中に `batch_rec_` が true にされ、記録後に false に戻ります（`src/core/verify.cpp:3744-3757`）。
- **QSA layer が処理されること**: QSA layer ごとに block scores/top-k/attention の処理を分岐します（同:1658-1660,1916-1993）。QSA layer を持たないモデルには効果がありません。
- **streamed KV でないこと**: 有効値かつバッチ窓の場合、いずれかの行の `kv_mode == 1` なら `streamed` となり、slot launcher の分岐を通りません。代わりに行ごとに block scores、top-k、`qsa_kv_resolve`、attention を行います。コメントは、streamed cache では同じ slot の前の行が選んだ block を後の行の resolve が退避させる可能性があるため順序を保つと説明しています（同:1916-1918,1981-1993）。
- **他の行まとめ launcher との関係**: `STRATA_BATCH_ATTN_ROWS` による `rows_ok` が true の場合、その分岐が `STRATA_QSA_SLOTS` 分岐より先に選ばれます。この経路も scores/top-k/attention を行まとめで処理します（同:1923-1948）。
- **backend / server**: server の `parallel_stack_env()` は、Linux、2 slot 以上の batch、DeepSeek 以外、HIP/SYCL/Metal/Vulkan 以外の設定で QSA を含む parallel stack を `setdefault` で追加します。HIP はこの自動設定の対象外です（`serve/server.py:3670-3712`）。ここで明示されているのは server が環境値を渡す条件であり、変数そのものの engine 側判定は `verify.cpp` の条件に従います。server による自動設定以外に、環境値を有効化する OS 判定や build macro は `g_qsa_slots` の読み取り箇所にはありません。Metal の Verifier は `window_run()` に委譲され、Metal stub の slot launchers は `false` を返す実装です（`src/core/verify.cpp:3056-3061`; `metal/src/engine/stubs_144.cpp:57-64`）。

## 実行時の詳細

engine は `serve/server.py:child_env()` で親環境を複製し、config の `env` をその上に設定してから `parallel_stack_env()` を呼びます。その helper は `env.setdefault()` を使うため、親環境または config が `STRATA_QSA_SLOTS` を明示していれば server の parallel stack は上書きしません。server の自動設定において `--batch` / `--slots` または `parallel` が 2 以上かどうかは適用条件を決めますが、それらの CLI 値自体が engine 内の `g_qsa_slots` を ON にするわけではありません（`serve/server.py:3747-3764,3684-3712`）。

有効なバッチ窓では、`g_qsa_slots` が true かつ `streamed` でなければ、行を最大 8 個ずつに区切って launcher を実行します。slot scores launcher が対応しない場合は block scores を行ごとに fallback し、attention launcher が対応しない場合は attention も行ごとに fallback します。top-k は `m` 行まとめて呼ばれます（`src/core/verify.cpp:1948-1979`; launcher の最大行数は `include/strata/kernels/qsa_decode_attn.hpp:54`）。CUDA の実装場所は `src/kernels/cuda/qsa_select.cu:1937` と `src/kernels/cuda/qsa_decode_attn.cu:1072` です。

この変数を直接名指しする実行時ログ、警告、専用終了・失敗分岐は見つかりませんでした。launcher が使われない場合も、コード上は別の per-row 経路または launcher 内の fallback に移ります。batch capture 自体の失敗は `verify: begin batch capture failed`、`verify: end batch capture: ...` など一般的な verifier エラー経路を返しますが、これは環境変数専用の診断ではありません（`src/core/verify.cpp:3744-3766`）。

## 根拠

- 候補名の全参照を検索し、engine における実読取は `src/core/verify.cpp:320` の `env_on("STRATA_QSA_SLOTS")` のみと確認しました。ほかの参照は server の環境設定、プロファイル / ツールの env 値、文書、テスト、コメントです。
- 実装の説明と適用条件: `src/core/verify.cpp:299-320,1916-1979`。
- batch capture の状態設定: `src/core/verify.cpp:3744-3766`。
- server の環境優先順位と自動設定: `serve/server.py:3670-3712,3747-3764`。
- 文書照合: `docs/BATCHING.md:110-127` は一般的な opt-in スイッチとして動作を記載し、`docs/BATCHING.md:576-592` は四枚の R9700 profile が値を設定する構成を記載しています。現行 server には Linux CUDA の batch slot 向けに複数スイッチを `setdefault` で追加する経路もあります（`serve/server.py:3670-3712`）。
