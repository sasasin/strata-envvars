# `--pool-affinity`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | CMake 生成のネイティブ `strata` 推論エンジン |
| オプション | `--pool-affinity MODE` |
| 別名 | なし。値 `pcores` は `p-cores` と同じ意味 |
| 値 | `all`、`auto`、`p-cores`（または `pcores`）、`measure` |

## 役割

CPU expert pool の worker thread をどの CPU コア群に割り当てるかを選びます。通常の `all` は既定の配置、`auto` と `p-cores` は hybrid CPU 向けの配置、`measure` は起動時に `all` と `p-cores` を測って選択します。結果値や推論アルゴリズムを変える設定ではなく、worker の配置を変える設定です（`src/program/generate.cpp:1053-1057`、`src/kernels/cpu/pool.cpp:743-747,923-935`）。

## 使い方

```sh
strata --pack ./pack --tokens "1,2,3" --pool-affinity p-cores
```

エンジンは `--pool-affinity` の直後の引数を値として読みます。CMake の `strata` 実行ファイルは `src/program/generate.cpp` から生成されます（`CMakeLists.txt:759-762`）。

## 値と既定値

- 省略時は `all` です。worker pool の `PoolAffinity` も `All` で初期化されています（`src/program/generate.cpp:518-523`）。
- `all`: 従来の既定配置です。OS が認識する各物理コアから worker 用 CPU を選びます（`include/strata/kernels/cpu/pool.hpp:71-77`、`src/kernels/cpu/pool.cpp:347-360,527-541`）。
- `auto`: hybrid CPU では P-core の主 logical processor、P-core の SMT sibling、E-core の順に worker 用 CPU を並べます（`src/kernels/cpu/pool.cpp:363-398,544-569`）。既定 worker 数は P-core 数から host 用の 1 を引いた数です（最低 1、`src/kernels/cpu/pool.cpp:801-818`）。
- `p-cores` / `pcores`: hybrid CPU では P-core とその SMT sibling だけを worker 用にし、E-core を候補から外します。既定 worker 数は `auto` と同じ規則です（`include/strata/kernels/cpu/pool.hpp:73-76`、`src/kernels/cpu/pool.cpp:363-398,544-569,801-818`）。
- `measure`: hybrid CPU 上の native pack で `all` と `p-cores` を測定し、速い方を選びます。parser は大文字小文字を区別した文字列比較で値を判定します（`src/program/generate.cpp:2539-2548`）。

同じオプションを複数回指定した場合、`all` / `auto` / `p-cores` は後の指定が前の値を置き換えます。一度でも `measure` を指定すると計測フラグは後続の値指定では解除されず、起動時の計測結果が最終 affinity を決めます（`src/program/generate.cpp:2539-2548,5971-5974`）。

`auto` / `p-cores` を指定しても hybrid CPU と判定されない場合、topology 検出は `all` と同じ worker CPU 群に戻ります（`src/kernels/cpu/pool.cpp:347-360,527-541`）。この場合も明示した affinity enum 自体は保持されます。

## 実行時の動作

parser は `auto` を `PoolAffinity::Auto`、`p-cores` と `pcores` を `PCores`、`all` を `All` に設定します。`measure` は `pool_measure` を有効にし、native expert source の準備後に計測関数を呼びます（`src/program/generate.cpp:521-524,2539-2548,5810-5812,5953-5974`）。計測関数は各 layer の native expert blob を2個ずつ使い、4 token 分の処理を `all` と `p-cores` の pool で交互に実行します。各候補の中央値を比較し、`p-cores` が `all` より10%を超えて遅くなければ `p-cores` を採用し、それ以外は `all` を採用します（`src/program/generate.cpp:2073-2087,2088-2114,2125-2167`）。

測定に使う CPU が hybrid でなければ警告を出して `all` を選びます。native pack の RAM 上 expert を取得できない場合も説明を stderr に出して `all` に戻ります（`src/program/generate.cpp:2093-2114`）。通常の native source 以外の経路も `srcp` として渡されますが、測定関数の `lay.native` 条件を満たさない場合は上記 fallback になります。

選択後、engine は `ExpertPool` を生成します。worker thread は割り当てられた logical processor への pin を試み、起動時に pool worker 数・CPU 配置を stderr に表示します（`src/program/generate.cpp:5971-6005`、`src/kernels/cpu/pool.cpp:923-945`）。通常の pool では pool worker が CPU expert 処理を行い、`--no-host-worker` が無効なら host thread も処理に参加します（`src/program/generate.cpp:5971-5978`）。

## 適用条件と相互作用

- `--pool-workers N` を正数で指定すると、affinity による既定 worker 数の選択を上書きします。`measure` の両候補にも同じ値が渡されます（`src/kernels/cpu/pool.cpp:801-818`、`src/program/generate.cpp:5971-5974`）。
- `--no-host-worker` は測定 pool と最終 pool の両方で host thread の pool 参加を止めます（`src/program/generate.cpp:5971-5978`）。
- `--pool-tasks N` は測定 pool と最終 pool の両方に渡されます（`src/program/generate.cpp:5971-5974`）。
- `--pool-cores` または `STRATA_POOL_CORES` で利用可能な worker CPU のリストを設定すると、pool constructor が affinity から検出した worker CPU 群をそのリストで置き換えます。そのため、明示 list が有効な場合は `--pool-affinity` による配置候補の選択が反映されないことがあります（`src/program/generate.cpp:2529,2902-2908`、`src/kernels/cpu/pool.cpp:763-780`）。
- worker の pin が OS に拒否された場合、通常は worker は pin できず、OS の配置に委ねられます。NUMA split が有効な場合は pin 失敗の警告を出します（`src/kernels/cpu/pool.cpp:923-935`）。
- `measure` は起動時に追加の expert 処理と pool thread の生成を行います。計測関数内で native pack の expert blob を参照し、結果を出さずに候補配置だけを比較します（`src/program/generate.cpp:2100-2114,2125-2167`）。

この文書の対象となる標準 parser は `src/program/generate.cpp` です。SYCL 側の別 parser (`sycl/src/program/generate.cpp:1860-1867`) は `all`、`auto`、`p-cores` / `pcores` のみを受理し、`measure` は受理しません。ビルド済みバイナリや各 OS/backend での実行確認は行っていません。

## 出力とエラー

- 値の指定がない場合は `--pool-affinity needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。
- 未知の値は `unknown --pool-affinity value '<値>' (expected auto, p-cores, all or measure)` を stderr に出して終了コード `2` になります（`src/program/generate.cpp:2539-2548`）。
- unknown argument の場合はエラーと usage を stderr に出して終了コード `2` になります（`src/program/generate.cpp:2787-2793,806-808`）。
- `measure` の CPU 非対応・pack 条件不成立はエラー終了ではなく、stderr に理由を出して `all` に戻ります。正常に計測できた場合は両候補の worker 数、時間、選択結果を stderr に表示します（`src/program/generate.cpp:2093-2114,2164-2167`）。

## 根拠

- 索引上のスコープ: [`docs/cli/README.md`](../../README.md) は `strata-engine` を `src/program/generate.cpp` の parser と定義し、本オプションを同じ root scope に掲載しています（同文書: 1128-1134, 1251-1258）。
- parser、usage、既定値、計測呼び出し: `src/program/generate.cpp:518-524,1053-1057,2418-2423,2539-2548,5971-5978`。
- 計測処理と fallback: `src/program/generate.cpp:2073-2167`。
- enum、CPU topology、worker pin と配置上書き: `include/strata/kernels/cpu/pool.hpp:71-96`、`src/kernels/cpu/pool.cpp:347-398,527-569,743-780,801-818,923-945`。
- SYCL parser の値差: `sycl/src/program/generate.cpp:1860-1867`。
