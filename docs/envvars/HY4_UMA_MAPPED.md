# `HY4_UMA_MAPPED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の GPU モデル読み込み時に、UMA GPU でモデルの trunk と、条件を満たす場合の expert arena を host-mapped allocation に置くよう選択する変数です。対象モデルの内容や推論計算を変える分岐ではなく、重みを読み込むメモリ配置を変えます。`load_gpu_model` は CLI と server のどちらからも呼ばれます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1283`、`engine/src/hy4flash/run/hy4_main.hip.cpp:659`、`engine/src/hy4flash/run/hy4_serve.hip.h:294`）。

判定は `gpu_is_uma() && getenv("HY4_UMA_MAPPED") && atoi(getenv("HY4_UMA_MAPPED")) != 0` です。UMA 判定を満たさない GPU では、設定値にかかわらずこの変数による配置変更はありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:42-49,1280`）。

## 値と判定

`getenv` は設定の有無を調べ、値は `atoi` で整数変換します。空文字は設定済みポインタですが `atoi("")` が 0 となるため無効です。数値全体の検証、範囲制限、エラー通知はありません。`atoi` が先頭の空白と符号の後から読む整数部分が 0 でなければ有効で、後続文字は値判定に使われません。したがって `1`、`2`、`-1`、`1anything` は有効、未設定、空文字、`0`、`0anything`、`true`、`false` は無効です。整数としての変換範囲外の文字列について、Strata 側に補正処理はありません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1280`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `gpu_is_uma()` が true | 無効（通常の配置選択） | `atoi` の結果が 0 以外。例: `1`, `-1`, `1anything` | `atoi` の結果が 0。例: 空文字, `0`, `0anything`, `true` |
| `gpu_is_uma()` が false | 無効 | なし。この条件式全体が false | すべて |

## 有効になる条件

- `gpu_is_uma()` が true であることが必要です。同関数は `hipGetDeviceProperties` で **device 0** の `integrated` を調べ、その結果を関数内 `static` に保存します。選択 GPU が device 0 以外でも、この判定は device 0 に基づきます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:42-49`）。
- ビルド macro `HY4_CUDA` により適用方法が異なります。HIP (`!HY4_CUDA`) では UMA allocation helper に `force_uma=true` を渡し、通常なら VRAM 空きに応じて `hipMalloc` も選ぶ helper の UMA host allocation を優先させます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1284-1293,1337-1348,1437-1448`; `engine/include/strata/hip_uma_guard.hpp:255-289`）。
- CUDA (`HY4_CUDA`) では trunk を pinned mapped host memory に読み込みます。expert arena は `with_experts` が true、peer GPU がない、かつ算出 budget が arena 全体以上のときに限り同様に配置します。それ以外は expert の tiered loading 経路です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1368-1394,1420-1434,1461-1483,1486-1503`）。
- `HY4_EMBED_VRAM` が未設定で manifest に `model.embed_tokens.weight` があり、メモリ取得処理が返した `tot0` が 48 GiB 未満なら、通常は embed tensor だけを pinned mapped host RAM に置く選択肢があります。この変数が有効だと `want_host_embed` が false になり、その分離配置を抑止します。`HY4_EMBED_VRAM` は値の内容ではなく設定有無で同じ選択肢を抑止します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:51-61,1281-1295`）。
- expert arena の全量配置可否は `HY4_RESERVE_GB` と `HY4_EXPERT_VRAM_GB` または `STRATA_HY4_VRAM_GB` による budget に左右されます。これらは `HY4_UMA_MAPPED` の値を上書きしませんが、expert を全量配置する分岐に入るかを変えます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1434`）。
- 分散ビルドで remote expert shard を読み込む場合は、trunk 読み込み後に shard ロードから戻るため、この変数による通常の expert arena 配置選択には進みません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1400-1409`）。

## 実行時の詳細

環境変数は `load_gpu_model` の呼び出し中、manifest 読み込み直後に評価されます。環境値そのものは `static` cache されず、同関数が再度呼ばれれば再読込します。一方、UMA 判定は `gpu_is_uma` の `static cached` に一度保存されます。server リクエストごとの再評価ではなく、CLI/server のモデルロード時の配置選択です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:42-49,1267-1283`）。

HIP では `uma_mapped` を trunk と expert arena の UMA allocation helper の `force_uma` 引数に渡します。CUDA では trunk 全体の host-mapped allocation を選び、expert arena は前節の条件を満たす場合に host-mapped allocation を試します。CUDA の expert allocation に失敗した場合は失敗を消費して tiered loading に進みます。HIP で trunk UMA allocation が失敗すると `trunk UMA alloc failed (...)` を stderr に出して loader は false を返します。CUDA の trunk allocation は `HCK` を通り、失敗時には `HIP error %d (%s) at %s:%d` を stderr に出して終了コード 3 で終了します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34,1337-1343,1368-1375,1437-1471`）。

mapped host buffer へのファイル読み込みで short read があれば `short read in %s chunk %llu (%zu < %zu)` を stderr に出して終了コード 1 になります。読み込みの進捗は chunk 数が 16 を超える場合に `[load %s] %llu%% %.1f s %.2f GB/s` の形式で出ます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:251-285`）。

## ログと測定値

この変数名や有効化を直接示す専用ログはありません。mapped 読み込み時の進捗ログは `%s` に `trunk(uma-coherent)` / `experts(uma-coherent)`（HIP）または `trunk(uma-mapped)` / `experts(uma-mapped)`（CUDA）が入ります。進捗ログは読み込み chunk が 16 個を超える場合だけです（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:251-285,1344-1348,1369-1375,1440-1447,1462-1468`）。

`docs/DETAILS.md` に `HY4_UMA_MAPPED` の説明や条件付き測定値は見つかりませんでした。ここでは性能や正確性の変化を推定しません。

## 根拠

- 読み取り、UMA 条件、embed 分離の抑止: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1277-1295`
- UMA 判定と cache: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:42-49`
- HIP/CUDA trunk 配置分岐: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1336-1394`
- expert 配置と budget、tiered fallback: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1505`
- UMA allocation の強制と fallback: `engine/include/strata/hip_uma_guard.hpp:255-319`
- CLI/server 呼び出し: `engine/src/hy4flash/run/hy4_main.hip.cpp:659`; `engine/src/hy4flash/run/hy4_serve.hip.h:294-297`
