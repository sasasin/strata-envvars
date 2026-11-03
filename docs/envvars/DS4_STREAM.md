# `DS4_STREAM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata 所有ソースを調査し、外部ライブラリや GPU driver の環境変数動作は含めない。

## 役割

Maya DS4 の GGUF MoE decode で、VRAM に置けない expert を CPU lane から GPU に PCIe lane 経由でストリームする経路を opt-in します。値 `2` は比較用の hold モードで、ストリーミング用の slot と expert の配置を保ちながら、lane が expert を実際に送らない状態にします。いずれも Strata の `src/dsv41/ds4_model.cu` にある DS4 model 実装の設定です。

値が lane を許可しても、対象形式・decode 経路・GPU 上の空き容量・lane の計測結果などが合わなければ転送は行われません。別の環境変数 `STRATA_DS4_STREAM` は互換設定名としてのみ使われ、`DS4_STREAM` が設定されていればこちらが優先されます。

## 値と判定

読み取り値は `std::atoi` で整数化され、`lane_env_off()` は値が未設定、または変換結果が `0` なら lane を無効にします。文字列全体の検証、範囲検査、エラー報告はありません。

| `DS4_STREAM` の状態 | 判定と結果 |
|---|---|
| unset、かつ `STRATA_DS4_STREAM` も unset | 既定 OFF。lane は有効にならない |
| unset、`STRATA_DS4_STREAM` が設定済み | alias の値を使い、同じ `atoi` 判定を行う |
| 空文字 | 設定済みとして alias を遮り、`atoi("") == 0` なので OFF |
| `0`、`00`、`false`、数字で始まらない文字列 | `atoi` 結果が 0 なので OFF（`false` を真偽値として解釈しない） |
| `1`、負の非ゼロ整数、整数の後ろに文字が続く文字列 | `atoi` 結果が非ゼロなら lane を許可 |
| `2`、または `atoi` が 2 を返す文字列 | lane の slot と配置を用意するが、streaming は行わない hold モード |

`atoi` のため、先頭空白や符号は C の整数変換規則に従い、数値の後ろは検査されません（例: `1abc` は 1、`2abc` は 2）。この変数について Strata は整数の上限・下限を設けていません。`DS4_STREAM` が空文字でも設定自体は優先されるため、`STRATA_DS4_STREAM=1` があっても OFF になります。

## 有効になる条件

- 対象は `pk.gguf` の DS4 model 経路です。`lane_alloc()` は GGUF 以外、lane 無効、MoE token path でない場合、または同期 decode の場合は成功扱いで早期 return します。
- lane が対象にする layer は非 MTP、expert 数の条件を満たし、MXFP4 形式で、blob サイズが正のものです。各 GPU で expert 全体が現在の空き VRAM 予算に収まる場合、その GPU の lane slot は確保しません。
- 過去の lane-times ファイルがその GPU の lane を `off` と記録している場合は測定・slot 確保を飛ばします。`DS4_STREAM_FORCE` が設定されている場合はこの記録を無視します。確保失敗、pinned slot を GPU から参照できない場合、計測失敗などでも lane は使えないか解放されます。
- 自動の「one-GPU decode path」は、HIP build でなく、NVIDIA の単一 GPU・単一 group・単一 device で、GPU が integrated でない場合だけ初期 ON 候補になります。lane が無効、または lane-times ファイルが過去に `off` とした場合は候補から外れます。`DS4_STREAM_WIN` と `DS4_LAND` はこの自動候補を既定値に使いますが、この二つの明示設定だけでは lane 自体を有効にしません。
- 初回 lane 計測後、実際に stream する layer がなければ自動 one-GPU path は終了します。例外は `DS4_STREAM=2` の hold と、`DS4_STREAM_FORCE` が設定された場合です。明示的な `DS4_STREAM_WIN` / `DS4_LAND` の値や slot pinning 等はこの path 判定と個別に作用します。

## 実行時の詳細

`lane_env()` はまず `getenv("DS4_STREAM")` を呼び、非 null ならその値を返します。未設定のときだけ `STRATA_DS4_STREAM` を読みます。取得したポインタや判定結果を static cache せず、model load の `one_gpu_path()`、lane の確保、lane 計測後の `one_gpu_plan()` などから再評価します。通常の用途では model load 時に読み取られます。プロセス実行中の環境変更に対する同期・再設定 API はこのコードにありません。

有効な場合、lane は CPU/RAM側の MXFP4 expert を staging slot に読み込み、GPU 側の pull が対象 expert を取得します。初期化と計測を通った後、lane の計測・decode A/B 判定によって、streaming を使う layer が決まります。`DS4_STREAM=2` の場合は計測と配置を保ったまま layer の stream mapping を作らず、CPU lane のみで処理します。one-GPU path が後から無効になると、暗黙の `DS4_STREAM_WIN` / `DS4_LAND` も OFF に戻り、条件によりゼロコピー用の登録を解除して slot を返します。

観測可能な stderr の出力には、one-GPU path の初期判定、lane が使えない理由、各 lane の計測結果、最終的な stream layer 数があります。例として `ds4: the one-GPU decode path ...`、`ds4: PCIe lane off: ...`、`ds4: PCIe lane: ...` を出します。stream 中のファイル読み込み失敗は `ds4: PCIe lane: reading a streamed expert failed - that token went without it` と出し、その token は該当 expert なしで進む経路があります。lane の GPU pull が 200 ms 内にホストから確認できない場合は警告を出し、以後 decode timing は CPU lane のみとします。

## 根拠

- 値の優先順位と unset / 0 判定: `src/dsv41/ds4_model.cu:9711-9719`。
- DS4 GGUF の load 時判定、自動 one-GPU path の GPU 条件、lane-times による抑止、関連ログ: `src/dsv41/ds4_model.cu:6094-6138`。
- load 内の呼び出し順と one-GPU path の後段計画: `src/dsv41/ds4_model.cu:3789-3793,6140-6175`。
- lane の前提条件、対象 layer、VRAM 判定、過去の off 記録と slot 確保: `src/dsv41/ds4_model.cu:9721-9724,9753-9795`。
- lane setup 時の slot/pinned memory 失敗処理: `src/dsv41/ds4_model.cu:10431-10480`。
- hold 値による streaming mapping の抑止と最終ログ: `src/dsv41/ds4_model.cu:10616-10642`。
- streaming read 失敗と GPU pull timeout のログ: `src/dsv41/ds4_model.cu:9811-9840,9924-9925`。
