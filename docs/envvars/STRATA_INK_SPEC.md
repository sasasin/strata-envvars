# `STRATA_INK_SPEC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling2 の `--serve` 実行で、DSpark speculative decode の経路を切り替える実験用スイッチです。`block` は greedy の fused beam-tree 経路を抑止し、通常の DSpark draft と batch verify に進ませます。`adapt` は speculative step の実測効率が低いときに drafting を一時停止する governor を有効にします。変数自体は出力トークンやモデルを直接設定せず、serve loop の分岐を選びます。読み取りと両フラグの決定は `engine/src/inkling2/ink_serve.h:494-515`、greedy tree 経路と batch verify 経路は同 `:876-935` にあります。

## 値と判定

`run_serve_loop` が `std::getenv` で一度読み、値全体を大文字小文字を区別して文字列比較します。trim、数値変換、部分一致はありません。`spec_tree` は値が厳密に `block` の場合だけ false、それ以外は true です。`spec_adapt` は値が厳密に `adapt` の場合に true となり、CLI の `--draft-adapt` が指定されていれば値にかかわらず true です（`engine/src/inkling2/ink_serve.h:508-515`、CLI 設定は `engine/src/inkling2/ink_main.cpp:898-904`）。

| 環境変数値 | tree 経路 | adapt governor |
|---|---|---|
| 未設定 | 有効 | `--draft-adapt` がなければ無効 |
| 空文字 | 有効 | `--draft-adapt` がなければ無効 |
| `block` | 無効 | `--draft-adapt` がなければ無効 |
| `adapt` | 有効 | 有効 |
| その他（`0`、`1`、`true`、`false`、`BLOCK`、`adapt ` など） | 有効 | `--draft-adapt` がなければ無効 |

`block` と `adapt` は特別扱いの完全一致値です。たとえば `block` と `--draft-adapt` を併用すると tree 経路を無効にしつつ governor は有効になります（`engine/src/inkling2/ink_serve.h:510,514`）。

## 有効になる条件

- 変数の読み取りは `run_serve_loop` 内にあるため、`--serve` でこのループに入る場合に限り適用されます。直接生成や `--bench` などは同ループを通りません（`engine/src/inkling2/ink_main.cpp:858-860,1071-1072,1093-1095`）。
- `block` が tree 経路を切り替えるのは、DSpark が利用可能で、単独の active request が prefill を終え、生成上限と context headroom を満たす fast path に入った場合です。tree 経路はさらに greedy sampling、penalty なし、context headroom 12 以上が必要です。これらの条件を満たさない場合は通常の scheduler 経路になります（`engine/src/inkling2/ink_serve.h:507,876-935`）。
- DSpark fast path の条件は `--draft` が `off` でないこと、モデルに DSpark があること、backend の `dspark_ready()` が true であることです。CPU・CUDA・HIP・SYCL・Metal backend はそれぞれ readiness を返します（`engine/src/inkling2/ink_serve.h:507`、`engine/src/inkling2/ink_backend.h:116`、`engine/src/inkling2/ink_cpu_backend.cpp:128`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:92`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:516`、`engine/src/inkling2/sycl/ink_sycl_backend.cpp:38`、`engine/src/inkling2/metal/ink_metal_backend.mm:72`）。
- `adapt` の governor が実際に抑止・計測するのは上記 DSpark fast path から通常の単独 decode へ移る場合です。複数 request の同時処理や prefill 中は条件に合わず、この governor による制御は行われません（`engine/src/inkling2/ink_serve.h:876-880,1218-1228`）。CLI `--draft-adapt` も同じ適用条件です（`engine/src/inkling2/ink_main.cpp:902-903`）。

## 実行時の詳細

環境変数は serve loop の開始時にローカル変数 `spec_env` と `spec_tree` / `spec_adapt` に読み込まれ、ループ中に再読込されません。したがって loop が動いているプロセス内で環境値を変更しても反映されません（`engine/src/inkling2/ink_serve.h:494,508-515`）。

`block` のとき greedy tree fast path の条件が false になり、続く `dspark_draft`、`forward_batch` と draft verification による経路が候補になります。ここでも DSpark がない、または fast path の前提を満たさない場合は当該分岐を通りません（`engine/src/inkling2/ink_serve.h:882-935`）。

`adapt`（または `--draft-adapt`）では、新しい request の governor 状態を初期化します。plain decode の最初の校正ステップを設け、その後は plain step 時間を更新します。speculative step は指数平滑（直近 20%）、各 request の12 step窓ごとに生成 token 数・時間から gain を算出し、平滑 gain が `0.93` 未満なら次の40 plain step の間 fast path を止めて再試行します。値 `0.93` ちょうどでは cooldown になりません（`engine/src/inkling2/ink_serve.h:517-528,734-735,1218-1228`）。

## ログと測定値

この変数の値や選択した governor/tree 経路を知らせる専用ログはありません。serve loop は通常どおり `INFO` / `READY` を出し、生成した token を `T` または `BT` protocol 行で返します。backend の speculative step が負のエラーを返した場合は `ERR fatal GPU error: ...` を返して `1` で終了しますが、これはこの変数固有の検証・エラーではありません（`engine/src/inkling2/ink_serve.h:562-568,889-894`）。

## 根拠

- 候補一覧には `STRATA_INK_SPEC` が掲載されています（`docs/envvars/000_envvers.md:1276`）。ソース中の実際の環境読み取りは `engine/src/inkling2/ink_serve.h:509` の一か所で、他の同名参照はコメント・設定登録情報です。
- server mode から serve loop への呼び出しは `engine/src/inkling2/ink_main.cpp:858-860,1093-1095` です。設定値の読み取り、解釈、適用条件、結果経路は上記各節の参照箇所に示しました。
