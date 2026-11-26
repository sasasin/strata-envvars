# `STRATA_ATTN_DAILY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA decode attention で、通常の `attn_chunk_kernel` の代わりに Daily 系の `attn_chunk_kernel_pre75` を選ぶスイッチです。対応する通常 CUDA build では明示的に `1` を指定すると全 CUDA カードでこの chunk kernel を選び、未設定時は sm_120 / 測定対象の sm_121 と一部の起動時アーキテクチャ既定値で選びます。HIP build では `daily_attn()` が常に `false` を返すため、この変数は kernel 選択に使われません（`engine/src/kernels/cuda/qsa_decode_attn.cu:896-924, 926-975`）。

同じ関数の結果は `STRATA_ATTN_MERGE_V2` が未設定または空文字のときの merger 選択にも使われます。`STRATA_ATTN_MERGE_V2` に非空値がある場合はそちらが優先されるため、Daily chunk と v2 merger は個別に切り替えられます（`engine/src/kernels/cuda/qsa_decode_attn.cu:1003-1021`）。

## 値と判定

CUDA では `std::getenv` の結果を関数内 `static` に一度だけ保存し、文字列全体がちょうど `"1"` のときだけ有効です。未設定はアーキテクチャ既定値に委ねられます。空文字、`0`、`true`、`01`、`1x`、前後に空白のある ` 1` はすべて明示的な無効値です。数値変換はしません（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-922`）。

| CUDA build / 実行条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常 build、sm_86。全可視 CUDA GPU が同一 compute capability のとき起動時に既定値テーブルを適用 | `STRATA_SM86_PERF` が `0` で始まらなければ起動時に `1` が設定される。`0` または `0anything` なら既定値なし | `1` | `0`、空文字、`true`、`01`、`1x` 等 |
| 通常 build、sm_89。同一 capability のとき既定値テーブルを適用 | `STRATA_SM89_PERF` が `0` で始まらず、`STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` でなければ起動時に `1` が設定される（`STRATA_SM89_PERF=0anything` も抑止値） | `1` | 上記以外の設定値 |
| 通常 build、sm_120 | 未設定なら `sm120_default` により既定で有効。`STRATA_SM120_PERF` が未設定または整数変換結果が非 0 の場合に有効 | `1` | 上記以外の設定値 |
| 通常 build、sm_121（GB10） | 未設定なら `kGb10AttnDaily=true` のアーキテクチャ既定値で有効。ただし `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS` の 0.2.6 指定時は無効 | `1` | 上記以外の設定値 |
| 上記以外の通常 CUDA GPU | 未設定なら無効 | `1` | 上記以外の設定値 |
| CUDA `STRATA_EXPERIMENTAL_SM60` build、sm_75 未満 | unset 時にこの変数自体は通常の sm_12x 既定値に従う。ただし別の `STRATA_ATTN_PRE75` 判定が旧 kernel を選べる | `1` | 上記以外の設定値。ただし sm_75 未満では `STRATA_ATTN_PRE75` が別途選択を変える |

既定値を設定する `nv_default_env` は sm_86 / sm_89 の表にこの変数を含め、既に環境に値があれば値の内容を問わず上書きしません。sm_86 の表は `STRATA_SM86_PERF` で、sm_89 は `STRATA_SM89_PERF` または `STRATA_DEFAULTS` で無効になります（`engine/src/core/nv_defaults.cpp:41-58, 75-90, 222-237`）。sm_120 / sm_121 は同表からこの変数を設定せず、kernel 側の未設定時判定で既定値を決めます（同 `:104-129, 176-180`; `engine/src/kernels/cuda/qsa_decode_attn.cu:912-922`; `engine/include/strata/core/sm120_series.hpp:32-42, 60-81, 83-95`）。

## 有効になる条件

- 対象は CUDA の QSA decode attention 経路です。HIP では前処理分岐により `daily_attn()` が `false` 固定です（`engine/src/kernels/cuda/qsa_decode_attn.cu:902-910`）。
- Kernel の選択点が `STRATA_ATTN_PRE75_BUILT` でコンパイルされている必要があります。この define は全 CUDA build と、gfx906 wave64 以外の HIP build で立ちます。通常の CUDA build では Daily 系 kernel が組み込まれています（同 `:492-505`）。
- 通常 CUDA build では `STRATA_ATTN_DAILY=1` ならカード世代に関係なく `pre75_attn()` が Daily kernel を選びます。unset 時の既定は sm_120 および測定対象として定義された sm_121 に限られます（同 `:912-962`; `engine/include/strata/core/sm120_series.hpp:60-81, 93-95`）。
- `STRATA_EXPERIMENTAL_SM60` CUDA build では `STRATA_ATTN_PRE75=0` が `pre75_attn()` を先に無効化します。一方、sm_75 未満は `STRATA_ATTN_DAILY` が `0` 相当でも capability 判定から pre75 kernel を選びます。`STRATA_ATTN_PRE75=1` は sm_75 以上でもその kernel を選びます（`engine/src/kernels/cuda/qsa_decode_attn.cu:926-965`）。
- 起動時の sm_86 / sm_89 既定値適用は CUDA build で、可視 GPU が 1 枚以上あり、全カードの compute capability が同じ場合に限られます。混在 capability の multi-GPU ではこの既定値テーブルがスキップされます。ただし kernel 側の sm_120 / sm_121 未設定時判定はデバイスごとに評価されます（`engine/src/program/generate.cpp:4421-4450`; `engine/src/kernels/cuda/qsa_decode_attn.cu:912-922`）。
- sm_86 の既定値は `STRATA_SM86_PERF=0` で抑止されます。sm_89 は `STRATA_SM89_PERF=0` または `STRATA_DEFAULTS=026` 系の指定、sm_120 は `STRATA_SM120_PERF=0`、sm_121 は `STRATA_SM121_PERF=0` または `STRATA_DEFAULTS=026` 系の指定で、それぞれ unset 時の既定が抑止されます。いずれも明示的な `STRATA_ATTN_DAILY` 値がある場合はその値が優先します（`engine/src/core/nv_defaults.cpp:41-43, 75-106, 176-180, 227-233`; `engine/include/strata/core/sm120_series.hpp:32-42, 66-81`）。
- ソースコメントと `docs/DETAILS.md:1295, 1486-1490` は sm_120 などの既定動作を説明していますが、sm_120 の `sm120_default()` は `STRATA_DEFAULTS` を参照せず `STRATA_SM120_PERF` だけを見ます。そのため現行コードでは sm_120 の未設定時 Daily 既定値は `STRATA_DEFAULTS=026` だけでは抑止されません（`engine/include/strata/core/sm120_series.hpp:32-42, 60-81`）。
- multi-slot / batch rows の専用経路では、Daily / pre75 kernel が選ばれていても `STRATA_ATTN_PRE75_SLOTS` または `STRATA_BATCH_QSA_STREAM_OPT` が有効でなければ slots 経路は `false` を返すか per-row 経路へ戻ります。これは kernel を使う機会・バッチ化を制限します（`engine/src/kernels/cuda/qsa_decode_attn.cu:978-990, 1150-1172, 1245-1270`）。
- merger は別設定です。`STRATA_ATTN_MERGE_V2` が非空なら `atoi` の結果が 0 かどうかで v2 を選び、Daily の値を上書きします。未設定または空文字なら Daily の判定に追従します（`engine/src/kernels/cuda/qsa_decode_attn.cu:1003-1021`）。

## 実行時の詳細

`daily_attn()` の初回呼び出し時に環境値を読み、以後は関数内 `static` にキャッシュします。従ってプロセス実行中に環境を変更しても反映されません。unset の場合は GPU の compute capability をデバイスごとの配列にキャッシュし、`sm12x_default(major, minor, kGb10AttnDaily)` の結果を使います。CUDA device の取得・属性取得に失敗した場合はその呼び出しで `false`（kernel 不選択）です（`engine/src/kernels/cuda/qsa_decode_attn.cu:906-922`）。

通常起動の sm_86 / sm_89 では、`generate.cpp` が GPU を調べた後に `apply_nv_defaults()` を呼び、既存環境値がない場合だけ `STRATA_ATTN_DAILY=1` をプロセス環境へ設定します。設定済みなら空文字や `0` でも保持されます。sm_89 / sm_120 / sm_121 のアーキテクチャ表は `STRATA_DEFAULTS=026` により省かれますが、sm_120 は kernel 側の独立した既定判定が残ります（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:222-237`; `engine/include/strata/core/sm120_series.hpp:32-42, 60-81`）。

QSA batch 経路は選択に応じて chunk kernel を起動し、別途 `attn_merge_v2()` で部分結果をマージします。CUDA API の起動エラーがあれば stderr に `qsa_decode_attn_batch: <CUDA error>` または slots 経路の同様の文言を出し、プロセスを終了コード 1 で終了します。不正な geometry / buffer も具体的な `unsupported geometry or missing buffers` を出して終了します（`engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1147, 1150-1156, 1217-1223`）。

## ログと測定値

sm_86 / sm_89 の起動時既定値が少なくとも一つ追加された場合、`apply_nv_defaults()` は stderr に `strata: sm_86 (Ampere): ... speed switches on by default ...` または `strata: sm_89 (Ada): ...` の形式で追加したスイッチ名を列挙します。環境値が既にある場合や既定値テーブルが空の場合は、この関数から既定値一覧の行は出ません（`engine/src/core/nv_defaults.cpp:227-255`）。この行は `STRATA_ATTN_DAILY` 専用の有効ログではありません。

Strata の `docs/DETAILS.md:1295` は sm_86 と 12.0 で exact、既定 ON と記載しています。`engine/include/strata/core/sm120_series.hpp:4-9` は RTX PRO 5000 Blackwell 72 GB / IQ3_S の 4-token verify で複数スイッチを合わせた測定として 13.70 ms から 12.23 ms を記しますが、単独の `STRATA_ATTN_DAILY` の効果値ではありません。`docs/DGX_SPARK_LINUX.md:120-123` と同 header `:83-90` は DGX Spark GB10 での測定を記載します。これらは資料記載値であり、本調査で性能測定はしていません。

## 根拠

- `engine/src/kernels/cuda/qsa_decode_attn.cu:896-965` — CUDA の値判定、unset 時の capability 既定、pre75 条件。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:978-990, 1003-1021, 1132-1147, 1150-1223, 1245-1270` — slots/batch rows の条件、merger、呼び出しとエラー経路。
- `engine/src/core/nv_defaults.cpp:41-58, 75-106, 176-180, 222-255` — sm_86 / sm_89 起動時の値設定と優先順位、ログ。
- `engine/src/program/generate.cpp:4421-4450` — 起動時 default 適用条件。
- `engine/include/strata/core/sm120_series.hpp:32-42, 60-95` — sm_120 / sm_121 未設定時既定と測定資料。
- `engine/include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS` の受理値と cache。
