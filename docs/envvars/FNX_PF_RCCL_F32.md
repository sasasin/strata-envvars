# `FNX_PF_RCCL_F32`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

AMD/HIP の split engine で、RCCL がプロンプト chunk のカード間和を担当するとき、その in-place AllReduce の要素型を既定の FP16 から FP32 に切り替える。値が非 0 なら各カードの和対象 `x` を FP32 のまま AllReduce し、0 なら FP32 の部分和を FP16 に詰めてから AllReduce し、戻り値を FP32 に展開する。従って FP32 は FP16 への丸めを避ける一方、コメント上は転送バイト数が 2 倍になる。生成結果の同一性や速度はこのソースからは保証できない（`engine/src/split/src/prefill.cu:721-756`）。

この変数が通常のプロンプト経路を単独で有効にするわけではない。RCCL 経路が選ばれた場合だけ参照される（`engine/src/split/src/prefill.cu:1013-1020`）。

## 値と判定

`env_int("FNX_PF_RCCL_F32", 0)` は値全体を符号付き base-10 の `long long` として厳密に parse し、結果が非 0 かで判定する。未設定時は 0。符号付き整数の範囲内なら負数も受理され、`-1` も有効になる。空文字、`true` / `false`、`0anything`、前後に空白を含む値、小数、範囲外整数は whole number として受理されず、RCCL 有効時には `FNX_PF_RCCL_F32: '<値>' is not a whole number` の例外になる。`0` と `+0` は無効、`1` や `-1` は有効。判定は文字列比較でなく parse 後のゼロ判定である（`engine/src/split/src/env.hpp:15-21,33-39`; 呼び出し `engine/src/split/src/prefill.cu:1015-1018`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP (`FNX_HIP`) で RCCL が有効 | 0（FP16 和） | parse 可能な非 0 整数（例: `1`, `-1`） | `0`, `+0`。整数として parse できない値は無効扱いではなく例外 |
| 非 HIP build、または RCCL 無効 | `FNX_PF_RCCL_F32` を読まない | 該当なし | 該当なし |

## 有効になる条件

- `FNX_HIP` でコンパイルされた split engine のプロンプト経路であること。`pf_ring` 内の RCCL 分岐と環境変数の読み取りはいずれも HIP compile guard 内にある（`engine/src/split/src/prefill.cu:726-743,1013-1021`）。
- engine 起動時に peer push 判定が成功していること。既定では `FNX_PEER` が未設定でも peer push を試みる。`FNX_PEER=0`、または peer probe の失敗では RCCL は使われない（`engine/src/split/src/hip/peer_policy.hpp:17-40`; 呼び出し `engine/src/split/src/engine.cu:120-132`）。
- RCCL 判定で RCCL が選ばれること。`FNX_PF_RCCL=0` は無効化するが、それ以外の設定値（空文字を含む）は「要求あり」と判定する。現行 `rccl_decide` の `RCCL_DEFAULT_ON` は `true` なので、この値が未設定でも peer push が有効なら RCCL のロードと自己テストを試みる。ロード・初期化・自己テストが失敗すると prompt sums は host exchange に戻る（`engine/src/split/src/hip/rccl_dl.hpp:21,70-91`; 呼び出し `engine/src/split/src/engine.cu:134-146`）。
- `FNX_RCCL_LIB` が空でない場合は Strata の RCCL loader がそのパスをロード先に使い、空または未設定なら `librccl.so.1` を使う。これは RCCL の選択条件ではなくロード先の指定である（`engine/src/split/src/hip/rccl_dl.hpp:34-48`）。

## 実行時の詳細

`Engine` 構築中に `prefill_alloc()` が呼ばれ、カードごとの prompt buffer を割り当てる際、`rccl_on_` が真のときだけこの変数を読み `Pf::rc_f32` に保存する（`engine/src/split/src/engine.cu:317-318`; `engine/src/split/src/prefill.cu:854-865,1013-1020`）。その後の各 chunk 和は `pf_ring` に入り、RCCL 有効かつ `rc_f32` が真なら FP32 の `x` を in-place の `RCCL_FLOAT32` / `RCCL_SUM` に渡す。偽なら FP16 buffer に pack して `RCCL_FLOAT16` / `RCCL_SUM` を行い、group 終了後の post 処理で結果を FP32 に戻す（`engine/src/split/src/prefill.cu:721-755,1413-1431`）。

この値は各カードの `Pf` に割り当て時に保持されるので、engine 構築後に環境を変更しても既存 engine の設定は変わらない。RCCL 無効時は値を parse しないため、たとえば同じ不正文字列でもこの変数による例外は発生しない（`engine/src/split/src/prefill.cu:1013-1020`）。CLI 引数による上書きは見つからなかった。

## ログと測定値

この変数自体が FP32 選択を知らせるログはない。RCCL の選択時には `The prompt sums use RCCL (<理由>).`、peer push がない場合に明示的に要求していれば `RCCL is not used for the prompt sums: the peer push between the cards is off, so the host exchange stays.`、利用不可なら `RCCL is not available here (<理由>): the prompt sums use the host exchange.` を stderr に出す（`engine/src/split/src/hip/rccl_dl.hpp:76-91`; 出力箇所 `engine/src/split/src/engine.cu:129-142`）。AllReduce 呼び出しエラーは `prefill: ncclAllReduce: <RCCL のエラー文字列>`、group 終了エラーは `prefill: ncclGroupEnd: <RCCL のエラー文字列>` の `runtime_error` になる（`engine/src/split/src/prefill.cu:730-739,1422-1429`）。

`docs/SPLIT_ENGINE.md:80-81` は `FNX_PF_RCCL=1` を「off by default」と記すが、調査対象 commit の `RCCL_DEFAULT_ON` は `true` であり、ソースと文書が一致しない。ここでは実装を根拠にした。FP32 選択モード自体の測定値は確認できなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-39` — 整数の厳密な parse と未設定時既定値。
- `engine/src/split/src/engine.cu:120-146,317-318` — peer / RCCL 選択、fallback、buffer 初期化時期。
- `engine/src/split/src/hip/peer_policy.hpp:17-40` — peer push の既定と probe fallback。
- `engine/src/split/src/hip/rccl_dl.hpp:21,34-48,70-91` — RCCL の現行既定、loader、選択ログと fallback。
- `engine/src/split/src/prefill.cu:721-756,854-865,1013-1020,1413-1431` — FP32/FP16 の和、変数読み取りと適用箇所、group 処理。
