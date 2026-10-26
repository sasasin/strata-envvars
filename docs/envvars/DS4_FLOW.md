# `DS4_FLOW`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

DeepSeek-V4.1 用の独立実行ファイル `strata-dsv41` にある、chunked prompt 中の expert stream 経路を選びます。flow 経路では、各 chunk と layer でルーティングされた expert を読み込み、次の layer の候補を先読みしながら転送し、到着した expert から計算します。無効時は既存の batch stream 経路を使います（`src/dsv41/ds4_model.cu:563-569, 7381-7410, 7611-7649`）。

## 値と判定

値は `std::atoi()` で整数に変換し、変換結果が 0 かどうかで判定します。文字列全体の妥当性検査や範囲制限はありません。

| 設定 | `flow_on` |
|---|---:|
| unset | 有効（既定） |
| 空文字、非数値で始まる文字列、`0`、`0suffix` | 無効（`atoi` の結果が 0） |
| `1`、負の整数、または先頭の整数部が 0 以外の文字列 | 有効 |

`atoi` は先頭の空白と符号を許し、数字列の後ろは無視します。したがって `  +2tail` は有効、`0x1` は 10 進変換が `0` で止まるため無効です。大文字小文字の比較はありません。根拠: `src/dsv41/ds4_model.cu:2704-2710`。

## 有効になる条件

値が有効でも、次の条件が必要です。

- `strata-dsv41` がビルドされている。CMake の `STRATA_BUILD_DSV41` は既定で `OFF` で、`STRATA_HIP_GFX906` 構成でもこのターゲットは作られません（`CMakeLists.txt:797-811`）。
- chunked prompt が有効で `chunk > 0`。chunk の選択は prompt parallelism、`--prefill-chunk`、`DS4_CHUNK` などに依存します（`src/dsv41/ds4_model.cu:1925-1931, 1990-2000`）。
- expert をモデルファイルから読む `file_experts` 経路である。GGUF はこのフラグが常に設定されます。非 GGUF 形式では `--mmap-experts` またはメモリ状況によって決まります（`src/dsv41/ds4_model.cu:1953-1973`）。
- 対象 GPU に割り当てられた非 MTP layer が MXFP4 形式である。複数 GPU の tensor-parallel group の layer は、さらに `DS4_FLOW_TP` が非ゼロで、down projection の分割サイズが expert block size の倍数である必要があります（`src/dsv41/ds4_model.cu:2706-2729`）。

いずれかを満たさない device では `Chunk::flow` が立たず、通常の batch 経路に進みます。全 device が flow を使う場合に限り、`DS4_CHUNK_MIN` が未設定なら `chunk_min` を flow 用既定値へ置き換えます。`DS4_CHUNK_MIN` が設定されていればその値を維持します（`src/dsv41/ds4_model.cu:2752-2758`）。

## 実行時の詳細

`DS4_FLOW` はモデルのロード中、`chunk > 0` の初期化ブロックで評価されます。結果は初期化時のローカル変数から各 device の `Chunk::flow` に反映されます。リクエストごとの再読み込みや子プロセスへの転送はこの実装にはありません。ロード後に環境変数を変えても、ロード済みモデルの flow 設定は変わりません（`src/dsv41/ds4_model.cu:2685-2738`）。

flow device は `run_dev_chunks()` で layer ごとの stream 状態を準備し、各 layer の expert 計算で `flow_layer()` を呼びます。無効 device は `run_set()` で届いた expert batch を計算する経路を使います（`src/dsv41/ds4_model.cu:7381-7410, 7603-7649`）。初期化時に `DS4_FLOW` 自体の有効・無効を示す専用ログは確認できません。verbose 時または `DS4_FLOW_STATS` 設定時には flow device の prompt stream 統計を stderr に出します（`src/dsv41/ds4_model.cu:8385-8405`）。

## 根拠

- 読み取りと各 device の適用条件: `src/dsv41/ds4_model.cu:2694-2738`
- 全 device が flow の場合の chunk 閾値: `src/dsv41/ds4_model.cu:2752-2758`
- flow と batch の prompt 実行分岐: `src/dsv41/ds4_model.cu:7381-7410, 7603-7649`
- 独立ターゲットとビルド条件: `CMakeLists.txt:797-811`
- `docs/DETAILS.md` と `docs/` の設計資料には `DS4_FLOW` の独立した説明を確認できませんでした。このため、速度や正確性への効果は本書では主張しません。
