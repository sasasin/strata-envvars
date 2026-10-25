# `--selftest`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-device` |
| コマンド | `strata-device`（root） |
| オプション | `--selftest` |
| 別名 | なし |
| 値 | 値なしのフラグ。省略時は無効 |

## 役割

GPU runtime の `DeviceArena` を実際に確保し、固定サイズ領域の確保、部分領域のアラインメント、容量超過時の拒否を確認します。モデルファイルは引数に取りません。`strata-device` は CUDA または HIP backend が有効な場合に CMake で作られる診断用実行ファイルです（`CMakeLists.txt:333-351`）。

## 使い方

```sh
./strata-device --selftest
```

実行には利用可能で、このビルドが実行可能な GPU が必要です。引数の解析後に device 0 の情報とメモリ計画を表示し、その後 self-test を行います（`src/core/device_main.cpp:26-41,65-92`）。

## 値と既定値

`--selftest` は値を取らず、指定すると真、未指定なら偽です。同じフラグを複数回指定しても真のままで、追加の動作はありません。短縮 alias はありません（`src/core/device_main.cpp:27-31`）。

## 実行時の動作

self-test 部分では 64 MiB の `DeviceArena` を device 0 用に作り、poison 初期化を有効にします。arena 作成時に GPU メモリを 64 MiB 確保し、この CUDA/HIP 経路では GPU kernel から領域全体に NaN パターンを書き込みます（`src/core/device_main.cpp:97-100`; `src/core/device.cu:327-355`）。続いて 1 MiB ずつの部分領域を 256 byte と 4096 byte 境界に配置し、返されたポインタのアラインメントを確認します。さらに容量の 2 倍を要求して `CudaError` が発生することを確認します（`src/core/device_main.cpp:99-115`; `src/core/device.cu:361-377`）。

この確認は device 0 の情報・計画表示の後にだけ実行されます。`device_info(0)` が GPU の不存在、ordinal、runtime 呼び出し、またはビルド対象外の GPU architecture を理由に失敗すると、self-test には到達しません（`src/core/device_main.cpp:65-66,118-120`; `src/core/device.cu:256-324`）。

`--list-devices` と併記した場合は、device 一覧を出してその場で正常終了するため、`--selftest` は実行されません（`src/core/device_main.cpp:49-63`）。その他の CLI option との設定競合はありません。固定の計画出力には `make_plan(20480, Geometry{}, Costs{})` が使われます（`src/core/device_main.cpp:85-91`; `include/strata/plan/plan.hpp:23-69,129-165`）。

## 適用条件と副作用

self-test は GPU メモリを一時的に 64 MiB 確保し、領域全体を poison 値で初期化します。スコープ終了時に arena の `cudaFree` が best-effort で呼ばれます（`src/core/device.cu:327-358`）。ソース上、この self-test は確保したデータを読み戻して poison 値を比較する処理を含まず、確認できるのは確保・部分領域の返却位置・容量超過拒否です（`src/core/device_main.cpp:93-115`）。

通常の処理では GPU runtime が認識する device 0 を検査します。GPU がない、ビルドがその GPU に対応しない、または runtime の初期化・問い合わせに失敗する環境では self-test は成功しません。CUDA/HIP のどの版・GPU 機種で実行確認できるかは、この調査では実機実行していないため確認していません。

## 出力とエラー

成功時は device 情報と固定メモリ計画を表示し、さらに `selftest: arena ...`、超過拒否確認後の `strata-device selftest OK` を stdout に出して終了コード 0 です（`src/core/device_main.cpp:65-91,105-117`）。アラインメント不一致、想定した超過拒否が起きない場合、または `std::exception` が発生した場合は stderr に診断を出して終了コード 1 です（`src/core/device_main.cpp:101-120`）。未知の引数は `unknown argument: ...` を stderr に出して終了コード 2 です（`src/core/device_main.cpp:37-40`）。

## 根拠

- parser、既定値、help、未知引数の扱い、self-test 分岐と出力: `src/core/device_main.cpp:26-41,93-120`
- GPU 情報・実行可能 architecture の検証: `src/core/device.cu:256-324`
- arena 確保、poison 初期化、解放、部分確保と超過エラー: `src/core/device.cu:327-377`
- GPU backend 条件と実行ファイル target: `CMakeLists.txt:333-351`
- 索引での command scope と対象リンク: `docs/cli/README.md:1417-1423`
