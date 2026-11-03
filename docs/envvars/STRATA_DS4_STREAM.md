# `STRATA_DS4_STREAM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 用の独立実行ファイル `strata-dsv41` で、decode 時に CPU lane が担当する expert の一部を PCIe lane 経由で GPU に読み込み、CPU lane と並行して計算する機能を opt-in します。`STRATA_DS4_STREAM` は `DS4_STREAM` の代替名です。`DS4_STREAM` が設定されていればそちらが優先されます。

## 値と判定

選択された文字列を `std::atoi` で整数化し、結果が 0 かどうかで判定します。文字列全体の妥当性検査はありません。

| `DS4_STREAM` | `STRATA_DS4_STREAM` | 判定 |
|---|---|---|
| 未設定 | 未設定 | 無効（既定） |
| 設定あり | 任意 | `DS4_STREAM` の値だけを判定。`STRATA_DS4_STREAM` は無視 |
| 未設定 | 設定あり | `STRATA_DS4_STREAM` の値を判定 |

選択値の変換結果が 0 なら無効、0 以外なら PCIe lane の準備に進みます。空文字、数字で始まらない文字列、`0`、`0tail` は 0 となり無効です。`1`, `true` のような数字で始まらない文字列も無効です。`1tail`, `-1`, `2` は非ゼロです。`atoi` は先頭の空白と符号を許し、数字の後の文字列を無視します。

値 `2` は通常の streaming opt-in とは異なり、テスト用 hold モードです。GPU staging slots を確保して配置を保ちますが、lane setup 後に streamed layer を割り当てず、実際のストリーミングは行いません。`DS4_STREAM` が空文字でも「設定済み」なので、fallback せず無効になります。

## 有効になる条件

- CMake の `STRATA_BUILD_DSV41` が有効で、実行対象が独立した `strata-dsv41` であること。この CMake option は既定で OFF です。通常の `strata` 実行ファイルや server がこの変数を読む根拠は見つかりません。
- モデルが GGUF、MoE token path が有効で、同期 decode ではないこと。どれかを満たさない場合 `lane_alloc()` は正常終了し、lane 用資源を確保しません。
- 対象 layer が MoE で、`nm == 1`、形式が MXFP4、expert 数と blob size が有効であること。さらに、その GPU に全 expert が収まる場合や、校正ファイルがその GPU の lane を `off` と記録している場合（`DS4_STREAM_FORCE` 未設定）はその GPU の staging を確保しません。
- 後続の lane setup が pinned memory を確保し、GPU がその領域を参照でき、計測または保存済みコストから streaming split を採用すること。コスト判定・一回ごとの A/B 判定によって、設定が非ゼロでも実リクエストで stream しないことがあります。

自動の「one-GPU decode path」は、HIP build では有効化されません。これは `STRATA_DS4_STREAM` の非ゼロ判定とは別の経路です。`DS4_STREAM_WIN` と `DS4_LAND` はこの one-GPU path の既定値を変え、`DS4_STREAM_FORCE` は校正済みの lane-off 判定を迂回して強制 split を指定しますが、どれも `STRATA_DS4_STREAM=0` による lane allocation の早期終了は解除しません。

## 実行時の詳細

値の読み取りは `lane_env()` を呼ぶたびに `getenv` で行われ、static cache はありません。モデル初期化中に `one_gpu_path()` と `lane_alloc()` などが判定し、`lane_setup()` と `one_gpu_plan()` が streaming layer と資源の状態を確定します。その後の decode は確定した `ln_layer` / `ln_dev` の計画を使います。環境変数の変更をリクエストごとに反映する実装ではありません。

通常の非ゼロ値では、GPU の staging slots を用意し、CPU lane の routed expert から計測コストに基づいて一部を選びます。読み取り thread が expert を pinned host memory に読み、GPU が PCIe 経由で受け取って expert kernel を実行する間、CPU lane は残りを計算します。`STRATA_DS4_STREAM` 自体に CLI 引数との優先順位はなく、同名を処理する CLI 引数も確認できません。`DS4_RECENT` が設定されていない場合、stream lane 有効時の GGUF recent slot 既定数にも影響します。明示的な `DS4_RECENT` はその既定値を上書きします。

観測できる stderr 出力には、one-GPU path の on/off 理由、lane timing の失敗、pinned memory を確保できない場合の `ds4: PCIe lane off: ...`、GPU が pinned slots を参照できない場合の CPU lane fallback、最終的な `ds4: PCIe lane: ... layers ... stream ...` があります。非同期 expert 読み込みに失敗すると `ds4: PCIe lane: reading a streamed expert failed - that token went without it` を一度出し、その token は当該 expert なしで進みます。未設定・0 の場合に `STRATA_DS4_STREAM` 固有の警告を出す処理はありません。

## 根拠

- 候補一覧には `STRATA_DS4_STREAM` が載っています（`docs/envvars/000_envvers.md:1091`）。実際の環境読み取りは次の `lane_env()` だけで、`DS4_STREAM` 優先の fallback と `atoi` 判定を行います（`src/dsv41/ds4_model.cu:9711-9720`）。同名の他のコード参照はこの実装コメントと `src/dsv41/ds4_model.cu:9617-9619` のコメントです。
- `strata-dsv41` は CMake option `STRATA_BUILD_DSV41` で追加され、option は OFF が既定です（`CMakeLists.txt:931-945`）。
- recent slot の既定値への影響（`DS4_RECENT` の明示値が優先）: `src/dsv41/ds4_model.cu:2793-2800`。
- lane allocation の gate と GPU / layer ごとの staging 条件: `src/dsv41/ds4_model.cu:9722-9724,9753-9795`。
- 非 HIP の one-GPU 自動経路、明示的な `DS4_STREAM_WIN` / `DS4_LAND`、one-GPU path のログ: `src/dsv41/ds4_model.cu:6086-6138`。
- lane setup の時期、pinned memory failure、stream layer の計測・割当・結果ログ、`2` の hold 動作: `src/dsv41/ds4_model.cu:3789-3793,10418-10432,10457-10479,10581-10595,10616-10642`。
- decode 時に CPU lane と stream lane が分担する処理、および読み取り失敗時の警告: `src/dsv41/ds4_model.cu:9604-9616,9912-9955,9830-9839`。
- `DS4_RECENT` の設定解析: `src/dsv41/ds4_model.cu:2793-2800`。
- `docs/DETAILS.md` には `DS4_STREAM` の動作や測定値の説明が見つからなかったため、性能値は記載していません。
