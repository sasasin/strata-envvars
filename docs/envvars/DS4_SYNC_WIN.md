# `DS4_SYNC_WIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 のシリアル forward で、各 window の層計算を始める前にデバイスを同期します。同期は `forward_serial()` 冒頭で一度行われます。Metal ビルドの診断用フックで、CUDA/HIP ビルドでは有効になりません。

## 値と判定

`ds4_dbg("DS4_SYNC_WIN")` は Metal ビルドでは `std::getenv(name) != nullptr` を返します。値の文字列や数値は parse しません。

| 環境変数の状態 | Metal ビルドでの判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |

空文字、`0`、`false` も「設定済み」なら有効です。CLI 引数、設定ファイル、他の環境変数による上書き・優先順位はありません。

## 有効になる条件

- `STRATA_METAL` を定義してビルドした場合に限ります。`src/dsv41/ds4_launch.h` では Metal の `ds4_dbg()` が環境を読み、その他のビルドでは常に `false` を返します。そのため CUDA/HIP では変数を設定しても同期分岐は実行されません。
- `forward()` が `par == false` の経路を選び、`forward_serial()` が呼ばれる必要があります。`par == true` の場合は `forward_par()` に進み、このチェックを通りません。

## 実行時の詳細

環境値はキャッシュされず、`forward_serial()` が呼ばれるたびに helper が `getenv()` を実行します。設定済みなら、`forward_serial()` の冒頭、最初の `cudaSetDevice()` と window の embedding upload / 計算より前に `cudaDeviceSynchronize()` を呼びます。したがって Metal の互換 runtime では `strata::gpu::device_synchronize()` に渡り、Metal dispatch の flush と現在の stream の完了待ちを行います。変数が無効な場合、この追加同期はありません。

この箇所は戻り値を確認せず、`CK(...)` にも渡していません。したがって、この同期呼び出しのエラーを `forward_serial()` の `err` に設定して失敗を返す経路はありません。ここから固有のログも出しません。同期の追加による性能・正確性の効果は、この調査では測定していません。

## 根拠

- 候補一覧には名前があります: `docs/envvars/000_envvers.md:308`。
- 全参照検索でコードの参照は `src/dsv41/ds4_model.cu:9777` のみです。環境変数名を受け取る helper は `src/dsv41/ds4_launch.h:30-36` にあり、Metal では `getenv(name) != nullptr`、それ以外では常に false を返します。
- 同期位置と直後の処理: `src/dsv41/ds4_model.cu:9774-9782`。シリアル／並列の分岐: `src/dsv41/ds4_model.cu:9736-9739`。
- Metal 互換 runtime の委譲と同期処理: `metal/include/metal_compat/cuda_runtime.h:118`, `metal/src/gpu/runtime.cpp:476-484`。
