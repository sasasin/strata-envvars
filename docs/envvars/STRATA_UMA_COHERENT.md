# `STRATA_UMA_COHERENT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の UMA GPU buffer 割り当てで、通常の `hipMalloc` を試す前に mapped host allocation を選ぶ指定です。対象は HIP/AMD でコンパイルされる `strata::hip_uma::alloc_gpu_buffer` のうち `is_uma` が真で、呼び出し側が `prefer_uma_coherent` を指定していない割り当てです。これは UMA allocation を強制する指定であり、メモリ確保そのものの成功を保証しません。また、通常の離散 GPU 割り当てやすでに強制指定された割り当ては切り替えません（`engine/include/strata/hip_uma_guard.hpp:242-265`）。

## 値と判定

値全体の検証ではなく `std::atoi(e) != 0` で判定します。`atoi` が数値変換できないときの 0 も含め、変換結果が 0 ならこの指定による切り替えはありません。先頭の空白と符号付き整数の変換規則に従い、後続文字列は検証されません（`engine/include/strata/hip_uma_guard.hpp:260-265`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP/AMD、`is_uma == true`、`prefer_uma_coherent == false` | この指定による強制なし。空き容量判定へ進む | `1`, `-1`, `1abc`（変換結果が非 0） | `0`, `0abc`, 空文字, `true`, `abc`（変換結果が 0） |
| 上記以外 | 参照されない | 該当なし | 該当なし |

大文字小文字の比較はありません。数値の後ろ・文字列全体の妥当性も検査せず、範囲 clamp もありません。値の変換は allocation ごとに行われ、環境変数値を保存する static cache はありません（同:255-265）。

## 有効になる条件

- 呼び出し元が HIP/AMD 用コードを使い、`is_uma` を真として割り当てる必要があります。Inkling HIP backend は HIP device の `integrated` 属性または既知の AMD iGPU arch から UMA と判定します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:61-70`）。
- `prefer_uma_coherent` が真なら、その指定で `use_uma_host` がすでに真になるため、この環境変数は読まれません（`engine/include/strata/hip_uma_guard.hpp:255-265`）。Inkling の KV pool は `use_host_mapped` をこの引数にも渡します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:284-299`）。
- Hy4-Flash の trunk / expert allocation では `HY4_UMA_MAPPED` が非 0 なら `force_uma` として渡され、この変数より優先されます。`HY4_UMA_MAPPED` が未設定か `atoi` の変換結果が 0 の場合、UMA device 上で本変数が判定されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1280-1293,1336-1347,1437-1448`）。
- 既定経路では、丸め後のサイズに 256 MiB の headroom を足した値が `hipMemGetInfo` の空き量を超える場合も mapped host allocation を選びます。さらに UMA 上で `hipMalloc` が失敗した場合は同 allocation に fallback します。したがって `STRATA_UMA_COHERENT=0` はこれらの自動経路を無効化しません（`engine/include/strata/hip_uma_guard.hpp:266-290`）。

## 実行時の詳細

`alloc_gpu_buffer` 呼び出しごとに `bytes == 0` を先に処理し、その後 `prefer_uma_coherent`、本環境変数、空き容量の headroom 判定の順に `use_uma_host` を決めます。環境変数が非 0 なら `hipMalloc` を試さず mapped host allocation に進みます。環境変数が unset または変換結果 0 なら、容量不足でない限り `hipMalloc` を試します。UMA 上の `hipMalloc` が失敗するとエラーを消費して host allocation に進みます（`engine/include/strata/hip_uma_guard.hpp:255-290`）。

host allocation では `hipHostMallocMapped` を指定し、コンパイル時に `hipHostMallocCoherent` が定義されていれば併せて指定します。その指定での確保が失敗した場合はエラーを消費して mapped のみで再試行します。確保成功後は Linux の THP advice を呼び、`hipHostGetDevicePointer` を行います。後者が失敗すると host allocation を解放してエラーを返します（同:292-319）。環境変数は各 allocation で読み直すため、実行中に環境値を変更すれば後続の allocation 判定には反映されますが、すでに確保済みの buffer はこのコードでは変更されません。

Inkling の通常 buffer 割り当てでは `is_uma` がこの分岐条件となり、allocation 失敗は `hip_ok` が `[ink-hip] <context>: <HIP error>` の形式でエラー文字列にし、呼び出し元へ失敗を返します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:217-221,258-270`）。Hy4-Flash では UMA trunk 確保が失敗すると `trunk UMA alloc failed (%.2f GB)` を stderr に出してモデル読み込みを失敗させます。expert allocation が失敗した場合はこの分岐で全領域読み込みを成立させず、後続の tiered loading 経路へ進みます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1336-1343,1437-1459`）。allocator 自体は成功時に環境変数や選択経路をログ出力しません。

## ログと測定値

この変数に関する専用ログや測定値はありません。観測できる失敗経路は「実行時の詳細」に記した呼び出し元のエラー処理です。成功時に実際の host allocation の性質がどう扱われるかなど、HIP runtime / driver 内部の挙動は Strata のソースだけからは記述しません。

## 根拠

- `engine/include/strata/hip_uma_guard.hpp:242-265` — HIP/AMD guard、値の読取と変換、優先引数。
- `engine/include/strata/hip_uma_guard.hpp:266-319` — 空き容量・OOM fallback、mapped allocation、失敗処理。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:61-70,217-221,258-270,284-299` — UMA 判定、呼び出しとエラー伝播。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1280-1293,1336-1347,1437-1459` — `HY4_UMA_MAPPED`、trunk / expert の呼び出しと読み込み失敗経路。
