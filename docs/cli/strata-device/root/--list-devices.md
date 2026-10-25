# `--list-devices`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-device` |
| コマンド | `strata-device` |
| オプション | `--list-devices` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

GPU runtime が列挙する各デバイスを、runtime の ordinal、名前、GPU architecture または compute capability、総 VRAM とともに表示します。HIP build では、そのデバイスがこの `strata-device` binary の対応 architecture で動作できるかも表示します。デバイスの選択や GPU 計算の self-test は行いません。

## 使い方

```sh
strata-device --list-devices
```

## 値と既定値

値を取らないフラグです。省略時の既定値は一覧表示なしです。引数走査中は同じフラグを複数回指定しても真偽値が true のままで、動作は変わりません。未知の引数は標準エラーに `unknown argument: <引数>` と出力し、終了コード `2` で終了します。

## 実行時の動作

指定すると `device_count()` で runtime のデバイス数を取得し、ordinal `0` から順に `device_summary()` を呼びます。各デバイスについて stdout に `device N: <名前>` と詳細行を出し、HIP では `arch <gfx...>, <GiB> GiB, wave<幅>`、CUDA では `compute capability <major>.<minor>, <GiB> GiB` の形式です。HIP は続けて `gpu_arch_problem()` の結果が空でなければ `cannot run: <理由>` も表示します。これは HIP ではコンパイル対象 architecture と wave32 条件を照合し、CUDA では常に空文字を返します。

デバイス数が 0（GPU がない場合のほか、runtime が利用できず列挙 API がエラーを返す場合を含む）なら `(no GPU device)` を表示します。個々のデバイスを runtime が説明できない場合は `device N: (the runtime cannot describe it)` を表示して次へ進みます。いずれのケースも一覧表示経路は終了コード `0` で終了します。

この option の分岐は `--selftest` の処理や通常の device/plan 診断より前に return します。そのため `strata-device --list-devices --selftest` と併用しても self-test は実行されません。CMake では GPU backend（CUDA または HIP）が有効な場合に `strata-device` target を作ります。

## 適用条件と副作用

実行には CUDA または HIP runtime にリンクされた `strata-device` binary が必要です。一覧処理はデバイス数・プロパティを照会し、Strata 側でファイルを書き出したり、ネットワーク通信や子プロセス起動、VRAM の明示的な確保をしたりするコードはありません。runtime/driver の初期化や照会が失敗した場合、`device_count()` は runtime error をクリアして 0 を返すため、呼び出し側では `(no GPU device)` と区別できません。

HIP の `cannot run` 判定は HIP build のときだけ行います。CUDA build ではデバイスごとの architecture 実行可否をこの一覧経路では報告しません。device ordinal は GPU runtime の列挙順であり、設定・環境による可視デバイス制限の影響を受けます。

この出力は `setup.py` と server の HIP GPU 検出でも消費されます。setup は Windows HIP engine の probe を実行して出力を解析し、server は自動 GPU 選択で明示的な GPU 指定や `HIP_VISIBLE_DEVICES` / `ROCR_VISIBLE_DEVICES` がない場合に probe を試みます。probe の不在・実行失敗・非ゼロ終了は各呼び出し側で fallback されるため、この option 自体の終了挙動とは区別してください。

## 出力とエラー

- GPU ごとの一覧、`(no GPU device)`、説明不能デバイス表示は stdout に出力されます。
- 一覧表示経路は正常終了時 `0` を返します。
- この経路ではデバイス照会の失敗を個別のエラーとして出力せず、デバイスなしまたは説明不能として扱います。
- 未知の引数は stderr に出力され、終了コード `2` です。

## 根拠

- `src/core/device_main.cpp:26-40` — 引数 parser、help/未知引数の処理。
- `src/core/device_main.cpp:43-63` — ordinal 順の一覧出力、0台・説明不能・HIP の実行可否表示、早期 return。
- `src/core/device.cu:78-85,94-111` — runtime のデバイス数取得と CUDA/HIP 別の詳細行生成。
- `src/core/device.cu:29-65,224-240` — HIP build architecture/wave32 判定と CUDA build の空判定。
- `include/strata/core/device.hpp:32-49` — device count、summary、実行可否 API の契約と ordinal の説明。
- `CMakeLists.txt:333-351` — GPU backend 条件下での `strata-device` target 定義。
- `setup.py:4139-4183` — Windows HIP setup が probe を実行し出力を解析する経路。
- `serve/server.py:3403-3422,3451-3479` — server の出力 parser と条件付き自動 GPU 選択。

同一 revision の既存 `strata-device --help` は実行していません。CLI 文書索引 [`docs/cli/README.md`](../../README.md) では `strata-device` の root option として掲載されています。Release binary の実行・Release artifact の照合は行っていません。
