# `DS4_CHUNK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象リポジトリは `main` で、調査開始時の作業ツリーは clean。外部ライブラリの環境変数の動作は対象外。

## 役割

DSV4.1 engine の prompt chunk サイズを上書きする開発・診断用の環境変数です。ソースコメントには「tests: down to 16」とあります。chunk が有効なら長い prompt をその token 数ごとの chunk に分けて処理します。DSV4.1 の CUDA/HIP 共通モデル実装にあるため、別 backend の同名変数や別エンジンの動作は確認できません。

環境変数が未設定なら `--prefill-chunk` または `prefill_chunk_default(...)` が決めた値を使います。設定されていれば `--prefill-chunk` より優先して値を置き換えますが、prompt chunk 経路そのものが有効でなければ chunk は 0 のままです。

## 値と判定

`std::getenv("DS4_CHUNK")` で値の設定有無を調べ、設定されていれば `std::atoi` で整数に変換します。文字列全体の妥当性検査はありません。`atoi` の規則により先頭の空白と符号を受け付け、数値で始まらない文字列（空文字を含む）は 0 になります。数値の後ろに文字があっても、その部分は変換値に入りません。整数として表せない範囲の入力の結果はこのコードでは検査・規定されていません。

設定値は次のように正規化されます（`kMaxChunk = 4 * kVlRows`、`kVlRows = 8192`）。

| 条件 | load 時の chunk |
|---|---:|
| 未設定 | CLI 指定値（`--prefill-chunk`）または `prefill_chunk_default(...)` の値。prompt chunk 経路が無効なら 0 |
| `atoi` 結果が 0 | 0。chunk 処理を無効にする |
| `atoi` 結果が負数 | 負数のまま保持される。`chunk > 0` の条件を満たさないため chunk 処理は無効 |
| 設定値が正 | `atoi` 結果を 16 の倍数に切り下げ、最低 16、最高 32768 に制限 |

たとえば `DS4_CHUNK=1` は 16、`DS4_CHUNK=31` は 16、`DS4_CHUNK=32` は 32 になります。負数は正規化されず負数のまま保持されますが、`chunk > 0` の各判定を満たさないため chunk path は使われません。なお、env 値を処理した後の GPU buffer 確保に失敗すると、load 中に chunk を半分ずつ減らします。512 より大きい値から縮小し、次の値が 0 になった場合は prompt chunk 経路を止めます。

## 有効になる条件

- `DS4_CHUNK` は chunk サイズを指定しますが、それ自体では prompt chunk 経路を有効にしません。経路は `--threads`、有効な tensor parallelism、`--prefill-chunk`、既定の `kChunkedPromptDefault`、および `DS4_WINDOWS` の設定有無から決まります。単一 GPU で `--threads` がなく、`DS4_WINDOWS` が設定されている場合は、`--prefill-chunk` に正値を指定していても経路が無効になります。`--threads` または tensor parallelism が有効ならこの条件を通らず経路は残ります。
- 経路が有効でない場合、`DS4_CHUNK` を設定しても `chunk = 0` とされます。
- 経路が有効で、`DS4_CHUNK` が設定されている場合は、`--prefill-chunk N` や自動既定値より env 値が優先されます。CLI の `--prefill-chunk` は解析時に `max(0, atoi(...))` されますが、env 値にはこの同じ clamp は適用されず、後段の共通 chunk 処理が適用されます。
- `DS4_CHUNK_MIN` が設定されている場合、別変数が prompt の最小処理長を決めます。chunk が正でも、入力 token 数がこの閾値より小さければ `feed()` は windows 経路を使います。未設定時の閾値は通常 512 ですが、全デバイスが flow 条件を満たす場合は 2 に変わります。
- chunk buffer が確保できなければサイズを縮小し、最終的に経路を無効化することがあります。

## 実行時の詳細

環境変数は `Model::Impl::load()` 中、モデルごとの chunk サイズを決める際に読み取られます。static cache ではありませんが、各モデルの load 時に一度だけ読むため、load 後にプロセス環境を変更してもそのモデルには反映されません。モデルを再 load すると再評価されます。子プロセスへの転送や環境変数の書き換えはこの実装では行いません。

`chunk > 0` なら `eg_cap` など prompt path 用 buffer の容量にも反映されます。入力が `chunk_min` 以上のとき `Model::feed()` は chunk 経路を候補にし、logits 行数や `pick_path()` に応じて `forward_chunks()` または `feed_windows()` を実行します。`feed_mark()` ではさらに入力が 2 token 以上で、`pick_path()` が chunk path を選ぶ必要があります。したがって、正の `DS4_CHUNK` は常にすべての prompt が chunked pass になることを意味しません。

この変数専用のログはありません。chunk が 0 のときは windows 処理について `ds4: prompts run in windows of ...` を stderr に出します。buffer 確保失敗時は縮小を試みる旨、最終的に失敗した場合は windows に戻す旨を stderr に出します。

## 根拠

- `src/dsv41/ds4_model.cu:810-819`: prompt path、初期 `chunk_min`、上限 `kMaxChunk`。
- `src/dsv41/ds4_model.cu:1924-1931`: prompt chunk 経路 (`prompt_par`) の条件と `DS4_WINDOWS` 判定。
- `src/dsv41/ds4_model.cu:1990-2009`: 自動既定値、`DS4_CHUNK` の読み取り、`atoi`、clamp、windows 時のログ。
- `src/dsv41/ds4_kernels.cuh:98`: `kVlRows = 8192`。したがって `kMaxChunk` は 32768。
- `src/dsv41/ds4_model.cu:2593-2637`: buffer 確保失敗時の縮小と fallback。
- `src/dsv41/ds4_model.cu:2752-2757`: `DS4_CHUNK_MIN` 未設定時、all-flow 経路で閾値を 2 に変更。
- `src/dsv41/ds4_model.cu:9356-9382`: feed / feed_mark で chunk path を選ぶ条件。
- `src/dsv41/ds4_main.cpp:1236`: CLI `--prefill-chunk` の解析。`src/dsv41/ds4_experts_rule.hpp:28-50`: `prefill_chunk_default(...)` の既定規則。

`docs/DETAILS.md` に `DS4_CHUNK` 自体の説明は見つかりませんでした。そこで性能値や token 同一性は記載していません。
