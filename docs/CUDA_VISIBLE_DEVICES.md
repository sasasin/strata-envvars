# `CUDA_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata 自身はこの変数を読み取って値を parse する通常の設定項目としては使いません。エンジン起動時に `--gpu` を指定すると、CUDA 初期化より前に Strata がこの変数を設定し、呼び出し元から継承した値を上書きします。サーバーは設定ファイルの GPU 選択を子エンジンと画像エンコーダーの環境に設定します。CUDA runtime が値をどう解釈してデバイスを列挙するかは外部依存側の動作なので、ここでは扱いません。

## 値と判定

エンジンが起動時に既存の `CUDA_VISIBLE_DEVICES` を読む箇所は、`--gpu` の上書き警告のためだけです。値の有効性、形式、空文字を Strata は検証しません。`--gpu` がなく、サーバー設定からも上書きされなければ、環境変数は子プロセスにそのまま継承されます。

| 経路 | Strata の処理 |
|---|---|
| `strata generate` に `--gpu LIST` がある | 最初に見つけた `--gpu` の次の引数を値として設定。CUDA の場合は `CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定する。環境変数の既存値が空でなく、引数と異なる場合は `warning: --gpu LIST overrides CUDA_VISIBLE_DEVICES=... from the environment` を stderr に出す。 |
| `strata serve` の設定に GPU 選択がない | 親環境をコピーするため、既存値を引き継ぐ。 |
| `strata serve` の設定に GPU 選択がある | サーバーが選んだ GPU 番号をカンマ区切りにして設定し、同時に `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定する。その後、設定の `env` マップに同名キーがあればその文字列で上書きされる。 |
| 画像エンコーダーに `vision.cuda_device` がある | エンジン環境を複製して、指定 GPU 1台の値に置き換える。CUDA 経路では `CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定する。キーがなければエンジン環境をそのまま使う。 |

サーバー設定の `gpu` は整数、整数リスト、またはカンマ区切り文字列から整数リストへ変換されます。値がない場合は空リストです。複数 GPU の順序は、自動配置条件ではカード速度に応じて並べ替える場合があります。設定の `gpu_order` が `as_given`、手動 layer split、または `--peer-device` 指定などでは並べ替えません。ここでの整数の解釈はサーバー設定の処理であり、環境変数文字列自体の parse ではありません。

## 有効になる条件

- CLI の上書きは `strata generate` の `--gpu` 引数がある場合に限ります。起動引数を先に走査し、CUDA/HIP 初期化より前に設定します。HIP ビルドでは同じ処理が `CUDA_VISIBLE_DEVICES` ではなく `HIP_VISIBLE_DEVICES` を設定するため、この変数は上書きしません。
- サーバーの CUDA 設定は `backend` が HIP でなく、設定に GPU が指定されている場合です。HIP backend では `HIP_VISIBLE_DEVICES` を設定します。
- `strata-vision` は `--gpu` がない場合、CUDA runtime に触れる前に `CUDA_VISIBLE_DEVICES=-1` を設定します。`--gpu` があればこの上書きは行いません。
- サーバーの NVIDIA GPU 速度測定用 Python 子プロセスは、親の環境を複製したうえで `CUDA_VISIBLE_DEVICES` を削除します。したがってこの測定処理は親プロセスで隠された GPU も含めて列挙を試みます。これはサーバーの補助測定プロセスに限った処理です。

## 実行時の詳細

エンジンの `main()` は引数を走査し、最初の `--gpu` の引数を環境変数へ設定してから `Options` の解析や後続の GPU 利用へ進みます。既存値が空文字なら上書き警告は出ませんが、設定自体は行われます。`--gpu` が重複した場合、この事前設定では最初のものを使います。実行中に環境変数を書き換える処理はなく、CUDA runtime が最初の呼び出しで環境を読むというコードコメントに従って初期化前に設定しています。

`strata serve` は `child_env()` で親環境を複製し、必要に応じて GPU 選択を書き込みます。その環境辞書は子エンジン起動時に `Popen` へ渡されます。画像エンコーダーは別の子プロセスで、既定では同じ環境を使いますが、`vision.cuda_device` が設定されると環境を複製してその GPU だけを指定します。

## 根拠

- `src/program/generate.cpp:1803-1825,1836-1838` — `--gpu` による起動前の設定、上書き警告、CUDA/HIP 分岐、引数解析。
- `serve/server.py:2308-2315,2587-2619,2622-2639` — サーバー GPU 設定の整数化・並べ替え・子エンジン環境の生成。`serve/server.py:697-698,6238,6379` — 環境を子エンジンへ渡す箇所。
- `serve/server.py:2518-2546` — 速度測定用子プロセスで `CUDA_VISIBLE_DEVICES` を削除する箇所。`serve/server.py:2683-2696,6393` — 画像エンコーダー環境の上書きと起動。
- `tools/vision/strata_vision.cpp:88-100` — GPU 指定がない場合に backend 初期化前に `-1` を設定。
- `src/core/peer_experts.cpp:81-90` — 指定した peer CUDA device が見えない場合のエラー文に、この変数を設定する案内がある。
- `docs/MULTI_GPU.md:35-61` — 利用者向けには `--gpu` / `--gpus` と設定ファイルの `gpu` で選択する手順を説明。コードが実際の値を環境へ渡す詳細は上記の実装に基づく。
