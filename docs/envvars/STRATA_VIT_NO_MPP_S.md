# `STRATA_VIT_NO_MPP_S`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Mac の GPU で Strata 自前の Vision tower を動かすとき、attention score（`S = q k^T`）の積に使う Metal tensor-op カーネルだけを無効化し、通常の Metal カーネルへ切り替える診断用スイッチです。設定すると `m.mpp_s` を `false` にし、attention score の積で `vm_gemm_s` を選ばず `vk_gemm_s` を選びます。BF16/F16 weight の積や P*V の積はこの変数では変更しません。`tools/vision/own/vit_metal.mm:425-431, 548-550`。

## 値と判定

`std::getenv("STRATA_VIT_NO_MPP_S")` のポインタが null かどうかだけを調べます。文字列の内容、数値としての妥当性、大文字小文字、空白は検査しません。したがって環境変数が未設定ならこのスイッチによる切替はなく、空文字・`0`・`false`・任意の文字列を設定しても切替が有効です。範囲や境界値はありません。`tools/vision/own/vit_metal.mm:427`。

| 条件 | unset | 設定ありの例 | 判定 |
|---|---|---|---|
| Metal の自前 GPU tower が `VitGpu::load` を実行 | この変数では `mpp_s` を変更しない。Metal 4 の有無、MPP shader のコンパイル、積の自己検査の結果に従う | `STRATA_VIT_NO_MPP_S=`、`=0`、`=false`、`=1` | 値にかかわらず `mpp_s=false` とし、理由をこの変数名にする |
| CPU tower、`--tower mtmd`、またはこの Metal 実装を含まない build | 読み取り箇所に到達しない | 同左 | 効果なし |

比較の前提として、Metal 4 が利用でき、MPP shader がコンパイルできた場合に限り4種類の積を自己検査し、結果を各 `mpp_*` に保存します。その後この変数が設定されていれば、自己検査結果にかかわらず score 用 `mpp_s` だけを false に上書きします。`tools/vision/own/vit_metal.mm:404-428`。

## 有効になる条件

- `strata-vision` が `STRATA_VIT_METAL` 付きでビルドされ、Metal GPU reader として起動する必要があります。Metal の自前 tower ソースは Apple build で `STRATA_VIT_OWN_METAL` または `STRATA_VISION_METAL` が有効な場合に含まれます。`tools/vision/own/CMakeLists.txt:56-68, 157-164`。
- 自前 tower が選ばれ、GPU reader のロードに進む必要があります。`strata-vision` の `--tower` は `mtmd` / `own` / `auto` を受け付け、`auto` はモデルファイル等が自前 reader に対応するかで選びます。明示的な `--tower mtmd` ではこの変数の読取経路を通りません。`tools/vision/strata_vision.cpp:94-99, 110-113, 137-170`。
- 自前 tower の CPU 実行では `VitGpu::load` を呼びません。Metal の GPU 対応がない build でも対象の切替は起きません。`tools/vision/own/own_reader.cpp:103-127`。
- tensor-op 経路自体には macOS 26 以降かつ GPU が Metal 4 family をサポートすること、MPP shader のコンパイル成功、score 積の自己検査成功が必要です。これらの条件が満たされない場合も score は plain カーネルで実行され、この変数が設定されていれば診断理由欄は `STRATA_VIT_NO_MPP_S` になります。`tools/vision/own/vit_metal.mm:404-423, 427-431`。
- CLI 引数や他の環境変数によるこの変数の値の上書きはありません。別の `STRATA_VIT_NO_MPP` は全積の MPP library 使用を止める独立したスイッチです。この変数は設定有無だけで score 積を個別に無効化します。`tools/vision/own/vit_metal.mm:405-416, 425-428`。

## 実行時の詳細

読み取りは `VitGpu::load` のロード時に1回行われ、その結果は `VitGpuImpl::mpp_s` に保持されます。同一ロード済み tower の生成処理中に環境を変えても選択は変わりません。新しいプロセスで reader を起動する場合は、そのプロセスの環境で再評価されます。サーバーの `Vision` は `env` を子プロセス起動に渡し、`vision_env` は特定 GPU を指定する CUDA/HIP 経路以外では受け取った環境をそのまま返します。`tools/vision/own/vit_metal.mm:368-371, 425-428`; `serve/server.py:4608-4623, 3195-3205, 3341-3348`。

score 積の実行時には `m.mpp_s` が true のとき `vm_gemm_s`、false のとき `vk_gemm_s` を `gemm` に渡します。変数自体は `strata-vision` を失敗させず、この積のカーネル選択だけを切り替えます。生成 token や出力の同一性について、この分岐から保証できる記述はありません。`tools/vision/own/vit_metal.mm:230-236, 548-550`。

## ログと測定値

Metal tower のロード時に stderr へ1行出力されます。設定時の該当部分は `attention S plain (STRATA_VIT_NO_MPP_S)` です（他の積と GPU 名を含む行全体は下記実装参照）。通常カーネルの実行失敗ではなく、変数による切替を知らせる理由表示です。`tools/vision/own/vit_metal.mm:427, 429-431`。

`docs/DETAILS.md` は確認しましたが、この変数または score tensor-op の切替を説明する記述は見つかりませんでした。対象変数の効果について、同資料由来の測定値は記載しません。

## 根拠

- `tools/vision/own/vit_metal.mm:368-377, 404-431` — Metal tower のロード、MPP 条件と自己検査、対象環境変数の判定、診断ログ。
- `tools/vision/own/vit_metal.mm:230-236, 548-550` — MPP / plain カーネルの選択と attention score 積への適用。
- `tools/vision/own/CMakeLists.txt:56-68, 157-164` — Metal 実装の build 条件。
- `tools/vision/strata_vision.cpp:94-99, 110-113, 137-173`; `tools/vision/own/own_reader.cpp:103-127` — tower 選択と GPU load 呼び出し。
- `serve/server.py:3195-3205, 3341-3348, 4608-4623` — サーバー経由で vision reader に環境を渡す経路。
