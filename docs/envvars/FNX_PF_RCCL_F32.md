# `FNX_PF_RCCL_F32`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

AMD HIP 版の `strata-split` が prompt の chunk sum に RCCL を使うとき、その all-reduce のデータ型を float32 にします。既定は無効で、無効時は float32 の加数を float16 バッファへ pack してから RCCL に渡し、戻り値を float32 に展開します。有効時は float32 の `x` を送受信バッファとしてそのまま all-reduce に渡します。この選択は RCCL 自体を有効にする設定ではありません。RCCL が無効ならこの値は読まれず、通常の host exchange が使われます。

## 値と判定

値は共通 helper `env_int()` で符号付き base-10 整数として全体を parse し、結果が `0` かどうかで判定します（`src/split/src/env.hpp:15-21,33-40`; 呼び出し箇所 `src/split/src/prefill.cu:760-766`）。

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | `0`（無効） |
| `0`、`+0`、`-0` | `0`（無効） |
| `1`、`-1`、その他の parse 可能な非ゼロ整数 | 非ゼロ（有効） |
| 空文字、空白を含む値、整数以外の文字列、整数の後ろに文字がある値、`long long` 範囲外 | `env_int()` が例外を送出 |

空白は許可されず、文字列全体が整数である必要があります。小数、`1x`、`0x1` も無効値です。値域の clamp はありません。無効値の例外文言は `FNX_PF_RCCL_F32: '<値>' is not a whole number` です。

## 有効になる条件

- `strata-split` の HIP ビルドであること。split engine 自体は Linux CUDA または Linux HIP 向けの opt-in ビルドですが、この変数の読み取りと `rc_f32` 分岐は `#if FNX_HIP` の範囲にあります（`src/split/CMakeLists.txt:1-7,20-25`; `src/split/src/prefill.cu:760-767`; `src/split/src/prefill.cu:515-532`）。CUDA 版ではこの設定による経路はありません。
- `Engine` 初期化時に RCCL が有効と判定されること。AMD 経路では `FNX_PF_RCCL`（未設定時の既定は `RCCL_DEFAULT_ON`）と peer push の判定結果で RCCL 利用を決めます。RCCL を使わない場合、この変数の読み取りを含む `if (rccl_on_)` に入らず、値は無視されます（`src/split/src/engine.cu:81-104`; `src/split/src/hip/rccl_dl.hpp:19-20,67-82`; `src/split/src/prefill.cu:760-767`）。
- `FNX_PF_RCCL` が有効でも peer push が無効なら RCCL は使われません。明示的に `FNX_PF_RCCL` が設定されていると stderr に `fnx: RCCL is not used for the prompt sums: the peer push between the cards is off, so the host exchange stays.` と出ます。RCCL のロードまたは初期化・self-test に失敗した場合も host exchange に fallback し、理由を含む `fnx: RCCL is not available here (...)` の行が出ます（`src/split/src/hip/rccl_dl.hpp:67-81`; `src/split/src/engine.cu:90-103`; self-test の判定 `src/split/src/hip/rccl.h:40-55,81-124`）。

## 実行時の詳細

`Engine` の初期化中に `prefill_alloc()` が呼ばれ、各カードの prefill バッファを作る際、RCCL が有効なら各カードの `Pf` について `FNX_PF_RCCL_F32` を読み `rc_f32` に保存します（`src/split/src/engine.cu:275`; `src/split/src/prefill.cu:625-637,760-766`）。同じ `Pf` の prompt 処理では再読み取りされません。実行中の環境変更が初期化済み `Pf` の動作へ反映される処理はありません。

chunk sum の RCCL 経路では、`rc_f32` が真なら `api.AllReduce(x, x, n, RCCL_FLOAT32, RCCL_SUM, ...)` を呼びます。RCCL API 呼び出しが失敗コードを返すと `prefill: ncclAllReduce: <エラー文字列>` の例外になります。偽なら `x` を float16 の `ring_ce.dag` に pack して float16 all-reduce を呼び、group 終了後に結果を float32 へ戻す処理をキューに積みます（`src/split/src/prefill.cu:512-534,1060-1078,1155-1161`）。`fnx_run` の main は捕捉された例外を stderr の `fnx_run: <内容>` として出力し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。

値が有効でも、HIP 以外、RCCL 無効、peer push 不成立の経路では float32 RCCL sum になりません。CLI 引数によるこの変数の上書きは確認できません。Strata の `docs/SPLIT_ENGINE.md:68-72` は `FNX_PF_RCCL` を off by default と説明しますが、同 commit のコードでは `RCCL_DEFAULT_ON` が `true` で、`rccl_decide()` は `FNX_PF_RCCL` 未設定時にその値を使います。ここでは実装コードに基づいて条件を記載しました。この資料には `FNX_PF_RCCL_F32` の測定結果や正確性比較はなく、この文書でも数値性能や出力同一性は断定しません。

## 根拠

- helper の整数変換、未設定時 default、無効値例外: `src/split/src/env.hpp:15-21,33-40`。
- RCCL の有効条件、既定値、明示設定時の fallback ログ: `src/split/src/engine.cu:81-104`; `src/split/src/hip/rccl_dl.hpp:19-20,67-82`。
- RCCL 時の値読み取り、float32 / float16 分岐: `src/split/src/prefill.cu:512-534,625-637,760-766`。
- grouped collective と後処理の順序: `src/split/src/prefill.cu:1060-1078,1155-1161`。
- CLI の例外表示と終了コード: `src/split/tools/fnx_run.cpp:1364-1373`。
- split build 条件と資料照合: `src/split/CMakeLists.txt:1-7,20-25`; `docs/SPLIT_ENGINE.md:68-72`。
