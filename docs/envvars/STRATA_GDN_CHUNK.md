# `STRATA_GDN_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

実験的 CUDA build の GDN（gated DeltaNet）再帰を、通常の token 単位 recurrence から 64-token 単位の chunk recurrence に切り替える。`STRATA_GDN_CHUNK` を正の整数として読める値にすると、再帰の state 更新と中間出力 `y` を `gdn_chunk_recurrence` に渡す。64-token に満たない末尾は通常の pipelined recurrence に残し、通常出力経路ではその後に出力 norm を行う。chunk recurrence は同じ recurrence の別の演算順序であり、ソースは通常経路との bit-exact 性を保証していない（`engine/src/prefill/kernels.cu:3145-3172`、`engine/include/strata/prefill/gdn_chunk.hpp:8-12,64-76`）。

通常 build、HIP、Metal、SYCL ではこの変数による分岐はコンパイルされない。CUDA では `STRATA_EXPERIMENTAL_SM60` が定義された build に分岐があり、この CMake option は既定で OFF（`engine/cmake/backends/cuda.cmake:28,76-80`、`engine/src/prefill/kernels.cu:3145`）。通常の GDN prompt 処理は `prefill.cpp` から `gdn_recurrence` を呼び、KVA state-only 処理は `gdn_recurrence_state_only` を通る。どちらも同じ dispatch 実装を使う（`engine/src/prefill/prefill.cpp:5203-5210`、`engine/src/prefill/kernels.cu:3286-3293,3309-3314`）。

## 値と判定

dispatch は `getenv` の結果が未設定または空文字なら `-1`、それ以外は `atoi` で整数化する。文字列全体の妥当性検査はなく、`atoi` が読む先頭の数値部分で判定される（`engine/src/prefill/kernels.cu:3150-3153`）。

| 条件 | 未設定 | chunk dispatch になる値の例 | chunk dispatch にならない値の例 |
|---|---|---|---|
| `STRATA_EXPERIMENTAL_SM60` を定義した CUDA build、`STRATA_GDN_REC_HEADS` 未設定、`T > 0` | 無効（`chunk_env = -1`） | `1`, `2`, `3`, `1tail`, ` 1` | 空文字、`0`, `0tail`, `true`, `-1`, `-2` |
| 上記以外の build | この環境変数を読む chunk 分岐なし | 該当なし | 該当なし |

この表の値判定は `atoi` の結果が 0 でない非負数かどうかによる。したがって `1tail` は 1、`0tail` と `true` は 0、負数は非負条件を満たさない。明示的な空文字は未設定と同じく chunk を選ばない。整数範囲を超える文字列の `atoi` 結果は規定できない。CLI 引数や設定ファイルからこの環境変数を上書きする処理は見つからなかった。

chunk recurrence 内でも同名変数を再度 `getenv` / `atoi` で読む。値が `2` のときは FP32 FMA scan を選び、`2` 以外ではデバイスが cc 7.0 で共有メモリ属性設定に成功した場合に WMMA scan、それ以外は FMA scan を選ぶ（`engine/src/prefill/gdn_chunk.cu:544-548,555-581,603-621`）。この内部判定は外側の dispatch が chunk recurrence を選んだ場合だけ実行される。

## 有効になる条件

- CUDA と `STRATA_EXPERIMENTAL_SM60` を有効にした build であること。既定 build ではこの分岐は含まれない（`engine/cmake/backends/cuda.cmake:28,76-80`、`engine/src/prefill/kernels.cu:3145`）。
- 初回 dispatch 時点で `STRATA_GDN_REC_HEADS` が未設定であること。同変数は空文字でも「設定あり」として関数内 static に cache され、設定ありなら chunk dispatch を抑止する（`engine/src/prefill/kernels.cu:3083-3088,3153-3154`）。
- GDN recurrence の token 数 `T` が 64 以上であること。`T < 64` では通常経路に進む（`engine/src/prefill/kernels.cu:3153-3169`）。
- `STRATA_GDN_CHUNK` の dispatch 判定は runtime compute capability を条件にしていない。`gdn_chunk_available()` の cc 7.0 判定は隣接する `STRATA_GDN_REC_WARP` 経路には使われるが、chunk dispatch の式には含まれない（`engine/src/prefill/kernels.cu:3152-3164`）。非 cc 7.0 ではチャンク関数内の WMMA 条件が false となり FMA scan 側に進む（`engine/src/prefill/gdn_chunk.cu:554-581`）。その build/device で kernel launch が成立しない場合は通常 recurrence への自動 fallback ではなく、エラー経路になる。
- 正の値で chunk dispatch されると `STRATA_GDN_REC_WARP` の recurrence 選択には進まない。値が 0、負数、無効文字列の場合は通常 recurrence に戻り、Volta で `STRATA_GDN_REC_WARP` が有効ならその経路が選ばれる（`engine/src/prefill/kernels.cu:3161-3184`）。

## 実行時の詳細

`STRATA_GDN_CHUNK` は GDN recurrence の呼び出しごとに読み直され、static cache されない。プロセス起動後に同一プロセス内で環境値を変更した場合も、次の recurrence 呼び出しの dispatch 判定に反映される。対して `STRATA_GDN_REC_HEADS` の有無は初回 recurrence で static cache される（`engine/src/prefill/kernels.cu:3087,3150-3153`）。chunk 関数内でも対象変数を再読し、`=2` なら FMA scan を強制する。`=1` など他の非ゼロ値は、WMMA が利用可能なら WMMA、そうでなければ FMA scan となる（`engine/src/prefill/gdn_chunk.cu:547-548,581,603-621`）。

dispatch された場合、`T` から 64 の倍数部分 `T64` を取り出して chunk recurrence に渡し、残り 63 token 以下を `gdn_rec_cols_pipe_kernel` で処理する。通常出力経路では全 `T` token 分の norm kernel を実行する。state-only KVA 経路では `with_out` が false のため norm は実行しない（`engine/src/prefill/kernels.cu:3164-3172,3286-3293,3309-3314`）。chunk 関数は `T64` を 64-token chunk の segment に分け、各 segment で cumsum と WMMA または FMA scan を実行する（`engine/src/prefill/gdn_chunk.cu:31,540-548,590-621`）。

chunk recurrence の kernel error は `gdn_chunk` の段階名と CUDA error を stderr に出して `exit(1)` する。属性設定の失敗自体はその場で終了せず、後続 launch の `check` で失敗が検出される場合にこの経路へ進む（`engine/src/prefill/gdn_chunk.cu:41-46,559-581,594-621`）。`STRATA_GDN_CHUNK` の値を示すログはない。別変数 `STRATA_GDN_CHUNK_PROF` が設定されていれば `gdn_chunk prof T=...` の各段階計時を stdout に出すが、これは当該変数の制御ではない（`engine/src/prefill/gdn_chunk.cu:585-589,629-633`）。

## ログと測定値

この変数自身による選択ログはない。リポジトリ内の `docs/GDN_CONTRACT.md` は `STRATA_GDN_CHUNK` が cc 7.0 の実機でのみ作用すると記載するが、現行 `gdn_recurrence_impl` の chunk 条件は cc 判定を含まず、`gdn_chunk_available()` の結果は `STRATA_GDN_REC_WARP` の判定にのみ使われる。ここでは現行分岐を根拠として記録した（`docs/GDN_CONTRACT.md:71-72`、`engine/src/prefill/kernels.cu:3152-3164`）。性能値は今回のソース読み取りで再測定していない。

## 根拠

- `engine/src/prefill/kernels.cu:3083-3088,3145-3172,3286-3293,3309-3314` — dispatch 条件、値の変換、通常／state-only の呼び出し。
- `engine/src/prefill/gdn_chunk.cu:525-548,554-581,590-633` — GPU capability helper、再読み取り、WMMA/FMA 選択、エラーと計時ログ。
- `engine/cmake/backends/cuda.cmake:28,76-80` — `STRATA_EXPERIMENTAL_SM60` の既定値と compile definition。
- `engine/src/prefill/prefill.cpp:5203-5210` — 通常 GDN prefill の呼び出し。
- `docs/GDN_CONTRACT.md:71-72` — 現行 dispatch と記載が食い違う既存資料。
