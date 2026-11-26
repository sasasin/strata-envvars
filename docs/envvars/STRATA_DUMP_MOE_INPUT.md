# `STRATA_DUMP_MOE_INPUT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

chunk-major の GPU prompt prefill で、選択した MoE layer の `m.mixed`（MoE 入力）と、その chunk の router expert ID をバイナリファイルへ書き出す診断用フックです。モデル計算の値や expert 選択を置き換える設定ではありません。書き出し前に入力を device から host へコピーして stream を同期するため、設定時は診断 I/O と同期が加わります（`engine/src/prefill/prefill.cpp:6180-6203`）。

## 値と判定

`std::getenv` の返り値を `run_impl` 内の関数 static ポインタに一度保存します。未設定なら `nullptr` となり出力しません。設定されていれば文字列を真偽値として parse せず、パスとして使います。空文字も設定ありですが、通常モードでは空のパスへの `fopen` が失敗します。数値変換、大小文字比較、値域検査はこの変数にはありません（`engine/src/prefill/prefill.cpp:6182-6197`）。

| 条件 | unset | 設定時に出力対象になる値 | 出力されない例 |
|---|---|---|---|
| 通常（`STRATA_DUMP_MOE_LAYER` が `all` でない） | 無効 | 任意の非 null パス文字列。例: `/tmp/moe.bin` | 未設定。空文字は設定ありだがファイルを開けず出力されない |
| `STRATA_DUMP_MOE_LAYER=all` | 無効 | 任意の非 null パス文字列。layer ごとに `<path>.L<layer>` | 未設定。空文字なら `.L<layer>` を開こうとするが、失敗時は無出力 |

出力対象 layer は `STRATA_DUMP_MOE_LAYER` が選びます。値が大文字小文字を区別して完全一致で `all` なら全 layer 用の分岐を static cache します。それ以外は各 layer で同変数を読み、未設定時は `0`、設定時は `atoi` で比較します。したがって空文字・数値で始まらない文字列は `0` 相当、`2tail` は `2` 相当、負数は一致する layer がなければ出力されません。全体 parse や layer 範囲の検証はありません（`engine/src/prefill/prefill.cpp:6184-6189`）。

## 有効になる条件

- `Prefill::run` が chunk-major の `run_impl` に進む必要があります。layer-major prefill が選ばれれば `run_layer_major` から戻るため、このフックを通りません。layer-major の判定は `STRATA_PREFILL_LAYER_MAJOR`、既定規則、実行条件に依存します（`engine/src/prefill/prefill.cpp:9657-9705`）。
- Metal は `Prefill::run` の Metal 経路から `metal_engine::prompt_run` を呼んで戻るため、この `run_impl` の読み取りには到達しません（`engine/src/prefill/prefill.cpp:9629-9651`）。
- 対象 layer が実際に `run_impl` の MoE 分岐を通る必要があります（`engine/src/prefill/prefill.cpp:5577-5587`）。通常モードの既定対象は layer `0` です。別 layer や全 layer を選ぶには `STRATA_DUMP_MOE_LAYER` が必要です。
- KVA が近似対象 layer の MoE 半分を省略する経路では、その layer の MoE 分岐に到達せず出力されません。`STRATA_KVA_SKIP=moe` の skip 経路と、state-only 経路が MoE より前に抜ける箇所があります（`engine/src/prefill/prefill.cpp:4997-5005, 5074-5083, 5343-5352`）。
- `<path>` の親ディレクトリが存在し、出力先を開ける必要があります。開けない場合に fallback やエラー通知はありません（`engine/src/prefill/prefill.cpp:6196-6203`）。
- `--chunk` や別の環境変数との値優先順位はありません。chunk サイズは出力条件を切り替えませんが、ファイル先頭の `T` と後続配列の行数は現在の chunk に従います（`engine/src/prefill/prefill.cpp:4295-4302, 4396`）。prompt が複数 chunk に分割される場合も、書き出し済みフラグは process 内で共有され、通常モードでは最初に選択 layer に到達した一度だけです。`all` は layer ごとに一度ずつで、後続 chunk では `dump_next` が進んだままなので通常は再出力しません（`engine/src/prefill/prefill.cpp:6183-6192`）。

## 実行時の詳細

読み取りは `run_impl` が MoE router を実行し、routed expert IDs を host に用意した後のコード位置で行われます（`engine/src/prefill/prefill.cpp:5585-5587`, `6180-6195`）。パスと `all` 判定は、そのコードへ初めて到達した時点で static 保存されるため、以後の環境変更はこれらに反映されません。通常モードの layer 指定は各 layer で `getenv` し直しますが、一度出力対象になると `dumped_moe` が立ち、その後は出力しません（`engine/src/prefill/prefill.cpp:6182-6192`）。

出力は `wb` で開くため既存ファイルを切り詰めます。内容は順に 3 個の `int64_t`（`T`, `N`, `K`）、`T*N` 個の `float`（`m.mixed`）、`T*K` 個の `int32_t`（`ids_h`）です。コードは値をホストのネイティブ表現のまま書き、書き込み戻り値や `fclose` の失敗を検査しません。ファイルを開けなかった場合も、フックのための host vector 確保・device-to-host copy・stream 同期は行われます（`engine/src/prefill/prefill.cpp:6190-6203`）。

## ログと測定値

このフック専用の stdout/stderr ログはありません。`fopen` 失敗、短い書き込み、copy/sync の戻り値をこの箇所では検査せず、`err` にも設定しません。そのため I/O 失敗をこのフックが明示的に通知したり、エラー扱いにしたりする経路はありません（`engine/src/prefill/prefill.cpp:6193-6203`）。対象変数について Strata の資料に条件つき測定値はありません。

## 根拠

- `engine/src/prefill/prefill.cpp:5577-5587` — chunk-major の MoE 分岐と router 実行。
- `engine/src/prefill/prefill.cpp:6180-6203` — 両変数の読み取り、対象選択、データ形式、ファイル出力。
- `engine/src/prefill/prefill.cpp:9629-9651, 9657-9705` — Metal 経路と layer-major 分岐、`run_impl` への到達条件。
