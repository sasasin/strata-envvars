# `STRATA_DUMP_MOE_LAYER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`engine/src/prefill/prefill.cpp` の `Prefill::run_impl` にある GPU prefill の MoE 診断ダンプで、対象 layer を選ぶ。この共通ソースは CUDA/HIP 系と Metal host target に含まれる（`engine/metal/CMakeLists.txt:135-156`）。単一 layer 指定では、最初に一致した chunk の `m.mixed`（MoE 入力）と `ids_h`（routing expert ID）を `STRATA_DUMP_MOE_INPUT` が指すファイルへ書く。`all` 指定では、最初の chunk の各対象 layer について `<STRATA_DUMP_MOE_INPUT>.L<layer>` を作る。通常の MoE の選択・計算結果を切り替える設定ではなく、読み戻しとファイル出力を追加する診断用フックである。読み取りと書き込みは `engine/src/prefill/prefill.cpp:6180-6203`。

## 値と判定

`STRATA_DUMP_MOE_LAYER` を `all` と比較する `dump_all` は、この処理に初めて到達したときに一度だけ評価される。大文字小文字を区別した完全一致なので、`all` だけが複数 layer 指定になる。その他の値は単一 layer 指定として、layer ごとに `std::atoi` へ渡される。`atoi` の変換結果と `l` が一致するかだけを見ており、文字列全体の数値検証、範囲検査、clamp はない（`engine/src/prefill/prefill.cpp:6186-6189`）。

| 条件 | unset | 有効になる値 | 単一 layer 指定として扱われる値・結果 |
|---|---|---|---|
| `Prefill::run_impl` の MoE 診断箇所 | `dump_all=false`、単一指定の layer 番号は `atoi("0")` 相当で `0` | `all`（完全一致）で各連続 layer を順に選択。数値変換結果が実際の `l` と一致する値でその layer を選択 | 空文字、`0`、`+0`、` 0`、`0abc` は `atoi` 結果が `0`。`2x` は `2`。`ALL` や `all ` は `all` ではなく、`atoi` 結果は `0`。`-1` は通常の非負 layer 番号に一致しない。範囲外の番号も一致先がない |

どの値でも `STRATA_DUMP_MOE_INPUT` が未設定ならダンプ条件が成立しない。これは別の関数内 static 値で、最初の到達時に取得される。設定済みの空文字は null ではないためダンプ条件には進むが、空のパスを開こうとして失敗する（`engine/src/prefill/prefill.cpp:6182-6189`, `6196-6198`）。

## 有効になる条件

- GPU prefill の `Prefill::run_impl` が該当 MoE routing 処理まで進むこと。この共通ソースは Metal host target にも含まれるが、SYCL には別の prefill ソースがある（`engine/metal/CMakeLists.txt:135-156`, `engine/sycl/CMakeLists.txt:38`, `engine/sycl/CMakeLists.txt:297-305`）。
- `STRATA_DUMP_MOE_INPUT` が null でないこと。出力先のパスはこの変数であり、layer 変数だけでは出力されない（`engine/src/prefill/prefill.cpp:6182`, `6188-6189`）。
- 指定 layer がそのプロセスの `run_impl` の layer 走査で MoE 診断箇所まで到達すること。走査範囲は `LB` 以上 `LE` 未満であり、layer split や MoE を飛ばす経路などで対象箇所を通らなければ書かれない（`engine/src/prefill/prefill.cpp:4977-4996`, `5343-5353`, `6180-6189`）。
- `all` は `dump_next` が `0` から始まり、選択のたびに1増える。したがって `l=0` から順に対象箇所を通ることが前提で、先頭 layer が走査範囲外または MoE 箇所を通らない場合、後続 layer は `dump_next` と一致せず選択されない（`engine/src/prefill/prefill.cpp:6184-6192`）。
- 単一 layer モードではプロセス内の `dumped_moe` が未設定であること。一度一致するとファイルを開けたかどうかにかかわらずフラグが立ち、そのプロセスの後続 chunk/request では再試行しない（`engine/src/prefill/prefill.cpp:6183`, `6190-6192`）。

この処理に関与する別の変数は `STRATA_DUMP_MOE_INPUT` である。CLI 引数やサーバーモードによる優先順位の分岐はこの読み取り箇所にはない。

## 実行時の詳細

`Prefill::run_impl` は prompt を chunk 単位に処理し、各 chunk で layer を `LB` から `LE` まで走査する（`engine/src/prefill/prefill.cpp:4214`, `4379-4385`, `4977`）。MoE の expert 数を数え、routing 表を準備した後の地点でダンプ条件を判定するため、出力される `ids_h` は当該 layer の routing 後の expert ID である。`m.mixed` を host vector に `cudaMemcpyAsync` し、stream を同期してから、3個の int64 header `{T, N, K}`、`T*N` 個の float、`T*K` 個の int32 expert ID の順にバイナリ書き込みする（`engine/src/prefill/prefill.cpp:6002-6007`, `6170-6203`）。

`STRATA_DUMP_MOE_INPUT` のパス、`dump_all` 判定、`dumped_moe`、`dump_next` は関数内 static でプロセスに共有される。パスと `all` 判定は最初の到達時にキャッシュされる。単一 layer モードの数値文字列は各 layer の判定時に `getenv` し直すため、プロセス内で環境を変更すれば番号判定には反映され得るが、既に立った `dumped_moe` は解除されず、`all` としての判定も再評価されない（`engine/src/prefill/prefill.cpp:6182-6189`）。

ファイルを開けない場合は書き込みを行わず、その結果を確認するログやエラー設定もない。`fwrite` / `fclose` の結果も検査されない。CUDA copy と stream 同期の戻り値もこの箇所では検査されない（`engine/src/prefill/prefill.cpp:6193-6203`）。

## ログと測定値

この診断ダンプ固有のログ出力はない。ファイル open / write の失敗を示す Strata の警告、終了、fallback もこの箇所にはない（`engine/src/prefill/prefill.cpp:6193-6203`）。関連資料にこの変数の性能測定値は見つからなかった。

## 根拠

- `engine/src/prefill/prefill.cpp:4214-4223`, `4379-4385`, `4977-4996` — prefill の実行経路、chunk と layer の走査。
- `engine/src/prefill/prefill.cpp:6002-6007`, `6170-6203` — routing 後の判定、環境変数の読み取り、値変換、データ形式、ファイル書き込み。
- `engine/src/prefill/prefill.cpp:6182-6192` — path / `all` の cache と first-dump 状態。
