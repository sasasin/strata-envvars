# `CUDA_DEVICE_ORDER`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

この名前は `000_envvers.md` の候補に含まれていますが、Strata は利用者が設定した値を読み取ってエンジン動作を選ぶ設定としては使っていません。GPU を指定して CUDA エンジンや画像エンコーダーを起動するとき、Strata は子プロセス環境へ `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定します。また、サーバーは `CUDA_DEVICE_ORDER` が厳密に `PCI_BUS_ID` かを確認し、エンジン内 ordinal と OS GPU 番号の対応が確実な場合だけ、監視・topology 情報にその対応を反映します。

## 値と判定

Strata が生成する設定値は文字列 `PCI_BUS_ID` です。大文字小文字を変えたり、前後に空白を付けたりした値を Strata が正規化することはありません。サーバーの `visible_device_order()` は CUDA 経路で値がこの文字列と完全一致しなければ空リストを返します（`serve/server.py:900-911`）。

この変数自体を `getenv()` 等で読む箇所はありません。サーバー側では環境辞書のキーとして確認・設定し、ネイティブエンジン側では `--gpu` の起動処理が値を設定します。したがって、変数値の未設定・空文字・無効文字列によってネイティブ演算の設定分岐を切り替える実装はありません。

## 有効になる条件

- `strata` のネイティブエンジンに `--gpu LIST` を渡すと、CUDA ビルドでは `CUDA_VISIBLE_DEVICES`、HIP ビルドでは `HIP_VISIBLE_DEVICES` を指定値に設定し、どちらのビルドでも `CUDA_DEVICE_ORDER` を `PCI_BUS_ID` に設定します。Windows では `_putenv_s`、その他では上書きを許す `setenv(..., 1)` を使います（`src/program/generate.cpp:2375-2396`）。
- サーバーの `child_env()` は、GPU 全台を Off にした場合には可視 GPU 変数を空にしますが、ここでは `CUDA_DEVICE_ORDER` を変更しません。HIP backend では `HIP_VISIBLE_DEVICES` を設定し、CUDA backend の GPU が選ばれた場合に `CUDA_DEVICE_ORDER=PCI_BUS_ID` と `CUDA_VISIBLE_DEVICES` を設定します。その後、config の `env` 項目を文字列化して環境辞書へ適用するため、同名の config 値があれば先に設定した値を上書きします（`serve/server.py:3499-3512`）。
- 画像エンコーダー用 `image_env()` は、CUDA backend で config に `gpu` があると `CUDA_VISIBLE_DEVICES` と共にこの変数を `PCI_BUS_ID` に設定します。HIP/Vulkan backend ではこの箇所からは設定せず、その後 config の `env` 値が適用されます（`serve/images.py:131-150`）。
- `vision_env()` は vision 用の `cuda_device` が指定された場合（または HIP の iGPU 自動選択が成立した場合）に環境辞書を複製します。CUDA backend の場合は `CUDA_DEVICE_ORDER=PCI_BUS_ID` と `CUDA_VISIBLE_DEVICES` を設定し、HIP backend では `HIP_VISIBLE_DEVICES` のみを設定します（`serve/server.py:3633-3648`）。

## 実行時の詳細

ネイティブエンジンの `--gpu` 処理は通常の引数パースと CUDA 初期化より前に `argv` を走査します。`--gpu` の値はその場で `CUDA_DEVICE_ORDER` と可視 GPU 変数へ設定され、後続のオプションループでは `--gpu` とその値を消費します。既存の可視 GPU 変数が空でなく、指定値と異なる場合は `warning: --gpu %s overrides %s=%s from the environment\n` を stderr に出します。`CUDA_DEVICE_ORDER` の旧値については警告・比較を行わず、常に `PCI_BUS_ID` へ置き換えます（`src/program/generate.cpp:2375-2396,2421-2429`）。

サーバーは生成した環境辞書をエンジンの起動に渡します。CUDA backend で値が `PCI_BUS_ID` と完全一致し、可視 GPU リストも `0` から `65535` の範囲の重複しない十進整数列（1〜16 個）なら、そのリストをエンジン ordinal から OS GPU 番号への対応表として使います。それ以外の場合は対応を不明として空リストにし、端末 topology の stage `device_index` を `null` にします。HIP backend は `CUDA_DEVICE_ORDER` を条件にせず、`HIP_VISIBLE_DEVICES` の妥当性で対応を作ります（`serve/server.py:900-911,6560-6569,8591-8597`）。

別の用途として、サーバーと `strata_control.gpu_roles` は NVIDIA カード速度の列挙用 Python 子プロセスに `CUDA_DEVICE_ORDER=PCI_BUS_ID` を渡し、同時に `CUDA_VISIBLE_DEVICES` を除去します。これにより Strata 側の ordinal として全カードを列挙・採点する入力環境を作ります。サーバー側は子プロセス実行失敗や出力解析失敗時に速度情報なしへ fallback します（`serve/server.py:3236-3264`、`strata_control/gpu_roles.py:432-462`）。

## 根拠

- `src/program/generate.cpp:2375-2396,2421-2429` — `--gpu` の早期走査、値設定、警告、および通常 parser での値の消費。
- `serve/server.py:900-911,3499-3512,3633-3648` — 環境のコピー・GPU 条件別設定・config 上書き、vision 環境、および GPU ordinal 対応の判定。
- `serve/server.py:6560-6569,8591-8597` — 対応表を terminal topology に反映する処理。
- `serve/server.py:3236-3264`、`strata_control/gpu_roles.py:432-462` — NVIDIA カード速度の子プロセスでの設定。
- `serve/images.py:131-150,221-237` — CUDA 画像子プロセス用の環境生成と起動。
