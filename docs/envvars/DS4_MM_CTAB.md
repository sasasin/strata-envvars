# `DS4_MM_CTAB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal backend の DeepSeek expert gate/up・down GEMM で、pipeline の function constant 23（`QUANT_CTAB`）を有効にします。Strata はこの変数の値を読み取って真偽値へ変換するのではなく、環境変数が存在するかを判定します。設定されている場合は `pipeline_uncached` に `cs.b(23, true)` を渡します。

## 値と判定

| 環境変数の状態 | 判定 | 処理 |
|---|---|---|
| 未設定 | false | `g_cx->pipeline(g_lib_moe, fn)` を選ぶ |
| 空文字を含む任意の値が設定済み | true | function constant 23 を true にした `g_cx->pipeline_uncached(g_lib_moe, fn, cs)` を選ぶ |

文字列の内容、数値としての妥当性、大文字小文字は検査されません。`=0` や空文字も設定済みとして有効になります。値に境界や無効値の概念はありません。

判定は `mm_set()` 内の `static const bool` 初期化時に一度行われます。これは、有効な引数で処理を始め、pipeline 選択箇所まで実行が進んだ最初の呼び出し時です。その後の呼び出しやプロセス内での環境変更では再評価されません。

## 有効になる条件

- Metal の `strata_ds4` 実行ファイルに組み込まれた経路でのみ読み取られます。`metal/CMakeLists.txt` は `ds4_finish.cpp` を DeepSeek のソースへ含め、`strata_ds4` を作成して `STRATA_METAL=1` を定義します。
- DeepSeek の `set_gate_up()` / `set_down()` が Metal 用 host adapter を試すとき、`a.hbounds != nullptr` である必要があります。Metal adapter が成功を返すと通常の `set` kernel 経路を使いません。
- `mm_set()` では expert 数と行数が正、両方の IQ block size が有効、寸法と leading dimension の条件を満たし、`mm_prepare()` が成功する必要があります。条件を満たさない場合は環境変数の判定に到達する前に `false` を返します。
- `mm_set()` は `iq_set_gu()` と `iq_set_dn()` の双方から呼ばれます。したがって同じ process 内で最初にどちらが pipeline 選択まで到達したかにより static 値が確定し、その後の gate/up・down の両方で使われます。

## 実行時の詳細

`mm_set()` は `gate_up` と量子化 type から `ds4_mm_gu_<type>` または `ds4_mm_dn_<type>` という関数名を作ります。未設定時は既定 function constant の pipeline を取得し、設定時は function constant 23 を true に指定して uncached pipeline を取得します（`metal/src/engine/ds4_finish.cpp:2476-2484,2517-2527`）。

Metal kernel 側では `QUANT_CTAB` が true のとき、i-quant grid と IQ2-XXS の符号表の accessor が constant 配列を参照し、false のときは threadgroup table を参照します。これは Strata 同梱の Metal kernel 内の分岐です（`metal/kernels/quant.metal:76-87`）。GEMM kernel はこれらの accessor を使って重みを復号します（例: `metal/kernels/moe_mm.metal:633-645,647-660`）。

pipeline 作成中に例外が発生すると `mm_set()` は tile buffer を解放して `false` を返し、この環境変数固有のログは出しません（`metal/src/engine/ds4_finish.cpp:2518-2527`）。呼び出し元は adapter が `false` の場合に通常の set kernel 経路へ続きます（`src/dsv41/ds4_iq.cu:1585-1601,1604-1619`）。Metal kernel library の compile 自体に失敗した場合は `mm_prepare()` が stderr に `dsv41 metal: compiling ds4_mm.metal failed` と出して `false` を返します（`metal/src/engine/ds4_finish.cpp:2466-2473`）。

この変数を設定したことだけを知らせる専用ログ、終了、警告はありません。pipeline 作成例外もこの箇所では表示されません。コード上、CLI 引数や別の環境変数との優先順位はありません。

## 根拠

- 全参照の検索では、候補名は `metal/src/engine/ds4_finish.cpp:2514-2517` のコメントと `std::getenv` の一箇所だけにあります。
- pipeline 選択と失敗時の戻り: `metal/src/engine/ds4_finish.cpp:2517-2527`。
- Metal 用 adapter を呼ぶ条件と失敗時の通常経路: `src/dsv41/ds4_iq.cu:1585-1601,1604-1619`。
- Metal kernel の function constant と lookup 分岐: `metal/kernels/quant.metal:76-87`。
- Metal 専用 DeepSeek 実行ファイルへのソース組み込み: `metal/CMakeLists.txt:135-142,165-170`。
