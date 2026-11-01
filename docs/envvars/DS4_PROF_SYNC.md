# `DS4_PROF_SYNC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 engine の `DS4_PROF` decode 計測方式を切り替えます。通常の計測は GPU event を記録して後から経過時間を集計しますが、この変数を設定すると各計測 mark で device stream を同期し、host clock の差を stage 時間として加算します。`DS4_PROF` が unset なら計測自体が動かないため、この変数だけでは推論動作や通常の出力を変えません。

## 値と判定

| 状態 | 判定 |
|---|---|
| unset | 無効 |
| 空文字を含む、何らかの値が設定されている | 有効 |

値の内容は parse せず、`std::getenv("DS4_PROF_SYNC") != nullptr` だけで判定します。`0`、`false`、空文字も有効です。既定値は無効で、数値範囲や無効値 fallback はありません。

`DS4_PROF` は別の設定有無判定です。`DS4_PROF_SYNC` が有効でも `DS4_PROF` が unset なら `prof_window` / `prof_chunk` は立たず、profile mark と集計は行われません。CLI による同機能の指定や、別変数との優先順位は実装にありません。

## 有効になる条件

- DeepSeek-V4.1 の `strata-dsv41` engine のモデル実装で参照されます。
- decode window のうち `T == 1` で、かつ `DS4_PROF` が設定されていると `prof_window` が有効になります。この場合、`DS4_PROF_SYNC` が設定されていれば同期方式になります。
- chunked prompt では `prof_chunk = prof_on && !prof_sync_on` のため、`DS4_PROF_SYNC` が設定されていると `DS4_PROF` が設定済みでも prompt の chunk GPU profile は無効になります。
- 同じソースは CUDA/HIP/Metal の device API 互換層を利用します。`DS4_PROF_SYNC` 判定に OS、backend、GPU 世代の分岐はありません。

## 実行時の詳細

`prof_sync_on` は `Model::Impl` のメンバー初期化時に一度読みます。static cache ではありません。環境変数を変更しても、その `Model::Impl` が存続する間は値を再読しません。別の CLI 引数や設定ファイルから値を渡す処理、子プロセスへの転送もこの実装にはありません。

decode 計測中、各 `prof_mark()` は mutex を取り、対象 device を選び、`cudaStreamSynchronize(d.st)` でその stream を同期します。2回目以降の mark では host clock の差を `st.prof_ms[stage]` に足し、時刻を更新して戻ります。`prof_collect()` は累積時間を reset し、計測 token 数を増やします。通常の event 方式ではなく host 時間を集計する経路です（`src/dsv41/ds4_model.cu:1380-1429`）。

集計対象 token があれば stderr に `GPU per token (DS4_PROF): ...` と stage ごとの時間を出します（`src/dsv41/ds4_main.cpp:1623-1631`）。この変数固有の警告・終了処理はありません。`prof_mark()` 内の stream 同期の戻り値はこの箇所では検査されません。

## 根拠

- 読み取りと `DS4_PROF` の独立した設定有無判定: `src/dsv41/ds4_model.cu:1311-1336`。
- decode window の対象条件: `src/dsv41/ds4_model.cu:9733-9750`。
- 同期方式の処理と計測 token の加算: `src/dsv41/ds4_model.cu:1380-1429`。
- prompt chunk profile の抑止と prompt 用レポート箇所: `src/dsv41/ds4_model.cu:9363-9364,9427-9485`。
- decode profile の stderr 出力: `src/dsv41/ds4_main.cpp:1623-1631`。
- 対象 engine と複数 backend の dispatch を示すソース記述: `src/dsv41/ds4_model.cu:3,15,34-36,41-45`。
