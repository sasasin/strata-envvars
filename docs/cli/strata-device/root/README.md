# `strata-device`（GPU device 診断 CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-device` |
| コマンド | `strata-device`（サブコマンドなし） |
| 主な実装 | `src/core/device_main.cpp`、`src/core/device.cu` |
| ビルド条件 | CMake の CUDA または HIP backend が有効な場合 |

## 役割

GPU runtime が認識するデバイス、device 0 の情報と VRAM 計画を表示し、必要なら GPU arena の簡易 self-test を実行する診断用 CLI です。Strata Terminal CLI の `strata` サブコマンドではなく、CMake が生成するネイティブ実行ファイルです。`strata-device` ターゲットは `STRATA_ENABLE_CUDA` または `STRATA_ENABLE_HIP` が有効な場合に定義されます（`CMakeLists.txt:333-351`）。

AMD のセットアップ手順は、モデル取得前の GPU 検出にも `strata-device --list-devices` を使います。Windows では HIP runtime の列挙順を確認する用途が説明されています（`docs/AMD_HIP.md:159-162`）。

## 代表的な使い方

ビルド出力先または配布物にある実行ファイルから実行します。Windows の AMD engine 配布物では、ROCm runtime の DLL がある `engine\\rocm\\bin` を `PATH` に含めてから実行する例があります（`docs/AMD_HIP.md:187-193`）。

```sh
# runtime が列挙する GPU と、ビルドした engine が実行できるかを確認
strata-device --list-devices

# device 0 の情報と VRAM 計画を表示し、GPU arena の self-test も実行
strata-device --selftest

# usage を表示
strata-device --help
```

## 実行モード

| モード | 呼び出し例 | 主な動作 |
| --- | --- | --- |
| デバイス一覧 | `strata-device --list-devices` | runtime の全デバイスを列挙し、名前、CUDA compute capability または HIP arch・wave 幅、総 VRAM を表示します。バイナリが実行できない GPU は理由も表示します。 |
| device 0 の診断 | `strata-device` | device 0 の名前、backend 情報、multiprocessor 数、VRAM の total/free、driver/runtime version を表示し、計画上の VRAM と free VRAM の比較を表示します。 |
| arena self-test | `strata-device --selftest` | 通常の device 0 診断に続けて、64 MiB の GPU arena を確保し、1 MiB の sub-allocation を二つ行って alignment と容量超過の拒否を確認します。 |
| help | `strata-device --help` または `strata-device -h` | usage を表示して終了します。 |

## 主な動作と注意点

- `--list-devices` は runtime が列挙した device ordinal を使い、GPU ごとに実行可否を判定します。GPU がない、または runtime が利用できず device count が 0 なら `(no GPU device)` を出力して終了コード 0 です。デバイス情報の取得に失敗した個体は `(the runtime cannot describe it)` と表示し、次へ進みます（`src/core/device_main.cpp:43-62`、`src/core/device.cu:78-85,94-110`）。
- `--list-devices` を指定すると一覧処理後に終了するため、同時に `--selftest` を指定しても self-test は実行されません（`src/core/device_main.cpp:49-63`）。
- 一覧以外の実行では device 0 の `device_info` を取得します。CUDA build は compute capability の最低条件を確認し、HIP build はコンパイル対象 arch と wave32 条件を確認します。条件不一致、runtime 呼び出しの失敗、device がない場合は例外メッセージを stderr に出し、終了コード 1 になります（`src/core/device_main.cpp:65-76,118-121`、`src/core/device.cu:256-324`）。
- VRAM 計画表示は `make_plan(20480, Geometry{}, Costs{})` の結果と、取得時点の device 0 の free VRAM を比較します。モデルをロードせずに表示する診断値で、モデル固有の起動可否を保証するものではありません（`src/core/device_main.cpp:85-91`）。
- `--selftest` は GPU runtime を使い、64 MiB の `DeviceArena` を確保します。arena は GPU メモリーを一括確保し、poison 初期化を行います。GPU メモリーが足りない場合など確保・初期化に失敗すると self-test 成功にはなりません（`src/core/device_main.cpp:93-115`、`src/core/device.cu:327-355`）。
- 引数なしでは device 0 の診断を行うため、利用可能な互換 GPU runtime が必要です。未知の引数は `unknown argument: ...` を stderr に出し、終了コード 2 です（`src/core/device_main.cpp:26-40`）。

## 関連文書

- オプション個別文書と CLI 索引: [`docs/cli/README.md`](../../README.md) の `strata-device` 節。
- [`--help`](--help.md)、[`--list-devices`](--list-devices.md)、[`--selftest`](--selftest.md) の各リンク先は索引上の個別文書です。
- AMD HIP backend とデバイス列挙の利用例: Strata [`docs/AMD_HIP.md`](../../../../../../Niko1221/Strata/docs/AMD_HIP.md)（checkout の利用者向け説明）。

## 根拠

- Strata `src/core/device_main.cpp:26-40,43-63,65-121` — 引数処理、一覧・通常診断・self-test の分岐と出力、終了コード。
- Strata `src/core/device.cu:78-110,256-324,327-379` — runtime 列挙、device summary、互換性検証、arena の確保・初期化・sub-allocation。
- Strata `include/strata/core/device.hpp:32-49,59-63,77-101` — device 列挙・互換性判定・arena API の説明。
- Strata `CMakeLists.txt:333-351` — CUDA/HIP build 条件と実行 target。
- Strata `docs/AMD_HIP.md:159-162,187-193` — セットアップ時の一覧利用と Windows の例。

調査範囲: 指定 checkout のソースと同梱ドキュメントを確認しました。生成済みバイナリの `--help` は実行しておらず、GPU 実行・build・テストも行っていません。出力される device 情報や実行可否は GPU、runtime、build backend に依存します。
