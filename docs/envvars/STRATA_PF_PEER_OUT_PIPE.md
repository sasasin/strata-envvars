# `STRATA_PF_PEER_OUT_PIPE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

peer GPU が計算した prompt expert の結果行を、expert group ごとに primary GPU へ戻す出力経路を選ぶための環境変数です。`set_peer()` はこの値から `PeerPrefill::out_pipe` を決め、真なら出力用 stream と group event を作り、各 group の計算中に結果をコピーします（CUDA/HIP: `engine/src/prefill/prefill.cpp:1332-1337,3393-3402,6963-6986`、SYCL: `engine/sycl/src/prefill/prefill.cpp:666-671,2270-2286,4533-4570`）。

ただし、どちらの実装でも `out_pipe` の判定時点では `PeerPrefill::compact` の初期値が `true` で、その後に `STRATA_PF_PEER_COMPACT` を読み `compact` を更新します。そのため式の `|| pp->compact` が常に真となり、この変数は実際の `out_pipe` 選択に影響しません。`STRATA_PF_PEER_OUT_PIPE=0` でも pipe は無効にならず、コメントにある「最後の group の後に一度だけコピー」経路へ切り替わりません（CUDA/HIP: `engine/src/prefill/prefill.cpp:1337,3396-3413`、SYCL: `engine/sycl/src/prefill/prefill.cpp:671,2274-2308`）。

## 値と判定

値は `std::getenv` で取得し、設定されている場合は `std::atoi` に渡します。文字列全体の検証はありません。`atoi` が返す値が 0 かどうかにかかわらず、初期値 `compact=true` との OR が真になるため、`atoi` の範囲内で判定できる値では `out_pipe=true` です。`atoi` の変換範囲を超える入力の戻り値は保証されません。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP (`engine/src/prefill/prefill.cpp`) | `v == nullptr` により真。pipe 有効 | なし（設定値は最終判定を変えない） | なし（`0` も pipe を無効化しない） |
| SYCL (`engine/sycl/src/prefill/prefill.cpp`) | `v == nullptr` により真。pipe 有効 | なし（設定値は最終判定を変えない） | なし（`0` も pipe を無効化しない） |

式の左辺だけを見ると、未設定または `atoi(v) != 0` で真、空文字・`0`・`0anything`・数値でない文字列など `atoi` が 0 を返す値では偽です。`-1` は非ゼロ、`-0` は 0 と判定されます。`atoi` は先頭の空白と符号を許し、数値部分の後ろは検査しません（例: `" 1tail"` は 1、`"0tail"` は 0）。大文字小文字の比較はありません。いずれの場合も、範囲内の入力なら右辺の `pp->compact` が判定を真にします（CUDA/HIP: `engine/src/prefill/prefill.cpp:1337,3396-3398`、SYCL: `engine/sycl/src/prefill/prefill.cpp:671,2274-2276`）。

## 有効になる条件

- この値の読み取りには peer prefill の初期化まで到達する必要があります。両 generate 実装では peer が有効で、`--peer-prefill-rows` が 0 以外のとき `set_peer()` を呼びます。既定値は `-1` で、peer に渡す行数は `--prefill` の chunk サイズと top-k から計算されます（CUDA/HIP: `engine/src/program/generate.cpp:13143-13153`、SYCL: `engine/sycl/src/program/generate.cpp:7608-7613`。CLI 解析・既定値: `engine/src/program/generate.cpp:924,1432,4209`、SYCL: `engine/sycl/src/program/generate.cpp:989,2173`）。
- CUDA/HIP は peer が有効であること、peer prompt 用の MMQ または int8 layer があること、NVFP4 expert ではないこと、Hadamard-folded pack ではないことなどを `set_peer()` で確認します。P2P がない場合は `STRATA_PF_PEER_HOST` が未設定または `atoi` 非ゼロなら mapped host 経路を許し、`0` なら初期化を拒否します（`engine/src/prefill/prefill.cpp:3333-3371`）。HIP も同じ `engine/src/prefill/prefill.cpp` 実装を GPU prefill target に含めます（`engine/cmake/strata_gpu_engine.cmake:482-488`）。
- SYCL は peer の P2P と MMQ prompt path が必要です。満たさない場合は `set_peer()` が `out_pipe` を読む前に失敗します（`engine/sycl/src/prefill/prefill.cpp:2243-2249`）。
- `STRATA_PF_PEER_COMPACT` の値は後段で compact buffer の設定に使われますが、`out_pipe` を設定した後に読み取られます。したがって `STRATA_PF_PEER_COMPACT=0` の場合も、すでに真になった `out_pipe` は更新されません（CUDA/HIP: `engine/src/prefill/prefill.cpp:3396-3415`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2274-2310`）。

## 実行時の詳細

`std::getenv` は `set_peer()` が `PeerPrefill` を作り、peer device 上の stream/event 作成を始めた後に呼ばれます。関数呼び出しごとに読み直し、関数内 static cache はありません。したがって初期化前に設定した環境値が読まれ、すでに作られた `PeerPrefill` の実行中に環境を変えてもその instance の設定は変わりません。再度 `set_peer()` が呼ばれた場合はその時点の環境を読みます（CUDA/HIP: `engine/src/prefill/prefill.cpp:3373-3402`、SYCL: `engine/sycl/src/prefill/prefill.cpp:2249-2286`）。

現行コードでは `out_pipe` が常に真となり、出力用 stream/event を用意します。group ごとの expert 結果行は、group 計算後に event で出力 stream を同期して primary の結果行領域へコピーされ、次の group の計算と並行する経路になります（CUDA/HIP: `engine/src/prefill/prefill.cpp:6963-6968,6981-6986`、SYCL: `engine/sycl/src/prefill/prefill.cpp:4533-4557`）。この変数による生成結果や expert 選択の変更はコード上ありません。

## ログと測定値

この変数の値に応じたログはありません。peer prefill 初期化に成功すると、CUDA/HIP は `strata prefill: peer GPU ... computes its experts' rows ...` を stderr に出します（`engine/src/prefill/prefill.cpp:3537-3545`）。初期化に失敗した場合、CUDA/HIP の呼び出し元は `strata serve: <理由> - the prompt path stays on the primary GPU` と出し、peer prompt path を使わず継続します（`engine/src/program/generate.cpp:13147-13153`）。SYCL の呼び出し元も同じ fallback 文言を出します（`engine/sycl/src/program/generate.cpp:7608-7613`）。この環境変数の効果を測定した Strata 資料は確認できません。

## 根拠

- `engine/src/prefill/prefill.cpp:1332-1342,3393-3415,6963-6986`
- `engine/sycl/src/prefill/prefill.cpp:666-676,2270-2308,4533-4570`
- `engine/src/program/generate.cpp:924,1432,4209,13143-13153`
- `engine/sycl/src/program/generate.cpp:989,2173,7608-7613`
- `engine/cmake/strata_gpu_engine.cmake:482-488`
