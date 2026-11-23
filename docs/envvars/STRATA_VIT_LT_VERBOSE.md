# `STRATA_VIT_LT_VERBOSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 版 own vision GPU reader の hipBLASLt 経路で、shape ごとの solution 選択ログと終了時の実行集計を `stderr` に出す診断スイッチ。環境変数単独では hipBLASLt を有効にせず、アルゴリズムや vision encoder の計算結果を切り替えない。読み取りと出力は `VitGpuImpl::lt_setup`、`lt_plan`、`lt_close` にある（`terminal/tools/vision/own/vit_gpu.cu:500-504,589-592,611-627,629-635`）。

## 値と判定

`lt_setup` 内の `on(name)` が `std::getenv(name)` を呼び、値が存在し、かつ `std::atoi(e) != 0` なら有効とする。値全体の検証や trim はしない。`atoi` が読む先頭の整数部分で判定されるため、未設定・空文字・`0`・`0anything`・`true`・`abc1` は無効、`1`・`-1`・`2tail`・` 1x` は有効となる。先頭の空白と符号は `atoi` の変換規則に従う。数値範囲の検査や fallback はなく、整数型で表せない値の結果は保証されない（`terminal/tools/vision/own/vit_gpu.cu:611-616`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_VIT_HIPBLASLT` 定義あり | false | `1`, `-1`, `2tail` | 空文字, `0`, `0anything`, `true` |
| `STRATA_VIT_HIPBLASLT` 定義なし | この名前を読むコードなし | 該当なし | 該当なし |

## 有効になる条件

- own vision reader を HIP GPU 付きでビルドすること。CMake は HIP のとき `vit_gpu.cu` を HIP 言語として追加し、`roc::hipblaslt` target が見つかった場合に限り `STRATA_VIT_HIPBLASLT` を定義してリンクする（`terminal/tools/vision/own/CMakeLists.txt:127-137`）。
- 実行時に `VitGpu::load` まで到達すること。環境変数は BLAS handle 作成後に `lt_setup` から読み取られる（`terminal/tools/vision/own/vit_gpu.cu:917-920,956-962`）。
- 実際に hipBLASLt の shape 解決・集計ログを得るには、別の `STRATA_VIT_LT`（weight products）または `STRATA_VIT_LT_ATT`（batched attention products）が `atoi` で非ゼロになること。両方が無効なら `lt_setup` は hipBLASLt の初期化前に戻り、verbose を有効にしてもこの変数によるログは出ない（`terminal/tools/vision/own/vit_gpu.cu:611-627`）。
- hipBLASLt handle と 32 MiB workspace の初期化に失敗した場合は、診断設定に関わらず `vit-lt: hipBLASLt is not usable here; hipBLAS for every product` を出し、weight / attention の両方を無効化する。その場合、shape 解決・集計ログは発生しない（`terminal/tools/vision/own/vit_gpu.cu:515,618-624`）。

## 実行時の詳細

読み取りは `VitGpu::load` から呼ばれる `lt_setup` ごとに行い、結果を `lt_verbose` に保存する。各 plan 作成時に環境を再読込せず、`lt_plans` に同じ shape の plan があれば再利用されるため、shape ごとの verbose 行は plan の初回作成時だけ出る（`terminal/tools/vision/own/vit_gpu.cu:516-519,543-548,611-616`）。この値を保存した後にプロセス環境を変更しても、その reader の `lt_verbose` には反映されない。

`lt_plan` は選ばれた solution ID、または候補がないときの `hipBLAS, no solution` と shape / dtype / batch / workspace を `stderr` に出す。reader の破棄時は verbose が有効で、かつ hipBLASLt launch または fallback の件数が 1 件以上ある場合に、合計件数を出す。hipBLASLt の matmul 自体が失敗した場合の失敗・同 shape の hipBLAS fallback ログは verbose の値によらず出る（`terminal/tools/vision/own/vit_gpu.cu:589-592,599-609,629-635`）。

verbose はログ条件だけを変える。weight products と attention products の hipBLASLt 使用可否はそれぞれ `lt_weights` / `lt_att` が決め、shape ごとの solution 選択と fallback は別の処理で行われる（`terminal/tools/vision/own/vit_gpu.cu:613-627,662-664,788-805`）。この変数による CLI 引数・設定ファイル上書きの経路はない。

## ログと測定値

- shape の初回 plan 作成時（`lt_verbose` が true）: `vit-lt: %s%s m=%d n=%d k=%d types=%d/%d/%d batch=%d -> %s %d (workspace %zu)`。選択失敗時の `%s` は `hipBLAS, no solution`（`terminal/tools/vision/own/vit_gpu.cu:589-592`）。
- reader 破棄時、launch / fallback があった場合: `vit-lt: %llu hipBLASLt products, %llu by hipBLAS`（`terminal/tools/vision/own/vit_gpu.cu:634-635`）。
- launch 失敗時は verbose に関係なく `vit-lt: the hipBLASLt product failed (m=%d n=%d k=%d batch=%d); hipBLAS from now on for this shape` を出し、その shape は以降 hipBLAS 側へ fallback する（`terminal/tools/vision/own/vit_gpu.cu:601-606`）。

`docs/DETAILS.md` にこの変数固有の挙動や測定値の記載は見当たらない。性能値は本調査では測定していない。

## 根拠

- `terminal/tools/vision/own/vit_gpu.cu:500-519` — HIPBLASLT 条件と reader 内の状態。
- `terminal/tools/vision/own/vit_gpu.cu:543-592` — shape plan の cache と verbose 行。
- `terminal/tools/vision/own/vit_gpu.cu:596-635` — launch failure、初期化、終了時集計。
- `terminal/tools/vision/own/vit_gpu.cu:917-962` — GPU reader の load と setup 呼び出し。
- `terminal/tools/vision/own/CMakeLists.txt:127-137` — HIP source と hipBLASLt の build 条件。
