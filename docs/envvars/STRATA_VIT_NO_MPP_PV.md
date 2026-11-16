# `STRATA_VIT_NO_MPP_PV`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Metal 版の own vision tower が attention の context 積 `P*V` を計算するとき、Metal 4 tensor-op kernel (`vm_gemm_pv`) を使わず通常の Metal kernel (`vk_gemm_pv`) を使わせる診断用スイッチです。重み行列の積 (`BF16` / `F16 weights`) と attention score `S` の選択はこの変数では変わりません。制御しているのは `m.mpp_pv` だけです（`tools/vision/own/vit_metal.mm:418-431`）。

この読み取りは Metal GPU 実装に限られます。`vit_metal.mm` は Apple で Metal を有効にした own vision tower のビルドにだけ追加されます（`tools/vision/own/CMakeLists.txt:56-69,157-163`）。実行時には own reader が GPU を使う場合に限って `VitGpu::load` を呼びます（`tools/vision/own/own_reader.cpp:114-125`）。CPU reader、CUDA、HIP、SYCL の実装にこの名前の読み取りはありません。

## 値と判定

`VitGpu::load` 内で `std::getenv("STRATA_VIT_NO_MPP_PV")` の戻り値を真偽値として使い、非 null なら `m.mpp_pv = false` とします。文字列の変換・比較はありません（`tools/vision/own/vit_metal.mm:428`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Metal GPU の own tower | P*V は MPP kernel の自己検査が通った場合に MPP を使い、それ以外は通常 kernel | 空文字、`0`、`1`、`true`、`false`、その他どの文字列でも、環境変数が存在すれば P*V の MPP を無効化 | 該当なし。値の内容による無効値・境界値はない |
| CPU、CUDA、HIP、SYCL、または Metal を含めない build | この実装では読み取らない | 該当なし | 該当なし |

`getenv` が null かどうかだけを見るため、空文字も設定済みとして扱われます。大文字小文字、空白、数値としての妥当性は検査しません。unset 時の既定は「自己検査の結果に従う」です。CLI 引数による上書きや、別の環境変数による P*V の再有効化はありません（`tools/vision/own/vit_metal.mm:418-429`）。

## 有効になる条件

- ビルドに `vit_metal.mm` が含まれている必要があります。CMake は Apple 上で `STRATA_VIT_OWN_METAL` または `STRATA_VISION_METAL` が有効な場合に Metal を含めます（`tools/vision/own/CMakeLists.txt:56-69,157-163`）。
- own vision tower を GPU 経路で実行する必要があります。CPU 経路では `VitGpu::load` を呼ばず、この変数も読みません（`tools/vision/own/own_reader.cpp:114-137`）。スタンドアロン `strata-vision-own` では `--gpu` が GPU 経路を選びます（`tools/vision/own/own_main.cpp:13-24,41`）。
- Metal 4 対応 GPU と macOS 26 以降で MPP library がコンパイルでき、P*V の自己検査が通ると、本変数 unset 時には P*V が MPP 候補になります。Metal 4 非対応・macOS 26 未満・MPP library のコンパイル失敗なら `m.lib_mpp` がなく、元から MPP は使われません（`tools/vision/own/vit_metal.mm:404-424`）。
- `STRATA_VIT_NO_MPP` が設定されると MPP library 全体が作られないため、本変数がなくても P*V は通常 kernel です。本変数を設定してもその状態は変わらず、他の積に対する `STRATA_VIT_NO_MPP_W` と `STRATA_VIT_NO_MPP_S` の分岐も独立しています（`tools/vision/own/vit_metal.mm:405-428`）。

## 実行時の詳細

GPU reader の起動時、`VitGpu::load` は先に Metal 4 対応確認、MPP library のコンパイル、利用可能な各積の自己検査を行い、その後で本変数を読みます（`tools/vision/own/vit_metal.mm:404-428`）。したがって設定しても MPP library のコンパイルや P*V 自己検査は省略されません。変数を読む箇所に static cache はなく、GPU tower のロードごとに評価されます。ロード後の値変更を追う処理はなく、既にロードされた `VitGpu` には反映されません。

設定されている場合、P*V の自己検査結果にかかわらず `m.mpp_pv` を false にし、理由文字列を環境変数名にします（`tools/vision/own/vit_metal.mm:423-429`）。各画像の encode では `m.mpp_pv` が true のときだけ `vm_gemm_pv` を渡し、false のとき `gemm` が `vk_gemm_pv` を選びます（`tools/vision/own/vit_metal.mm:229-236,564-566`）。この分岐は P*V kernel の選択を示します。出力の数値差や性能差を示す測定値は、このソースからは確認できません。

## ログと測定値

ロード時に stderr へ出す `strata-vision` の製品選択ログでは、設定時の P*V 欄が `plain (STRATA_VIT_NO_MPP_PV)` と表示されます。これは設定値の内容にかかわらず同じです（`tools/vision/own/vit_metal.mm:428-431`）。変数専用の警告や終了コードはありません。

Metal GPU 自体がない場合は own reader が `this picture reader found no GPU (no Metal GPU)` としてロード前に失敗し、GPU tower のロード失敗は `cannot load the vision encoder ...` として報告されます（`tools/vision/own/vit_metal.mm:351-356`; `tools/vision/own/own_reader.cpp:116-125`）。本変数が有効なときに通常 kernel へ切り替わること自体は失敗経路ではありません。Strata の資料には本変数の測定値は見当たらず、性能・正確性への効果は記載しません。

## 根拠

- `tools/vision/own/vit_metal.mm:404-431` — MPP の条件、各積の自己検査、対象変数の判定、stderr の選択ログ。
- `tools/vision/own/vit_metal.mm:229-236,564-566` — P*V の kernel 選択と通常 `vk_gemm_pv` への切替。
- `tools/vision/own/CMakeLists.txt:56-69,157-163` — Metal 実装がビルドに含まれる条件。
- `tools/vision/own/own_reader.cpp:114-125,128-148`、`tools/vision/own/own_main.cpp:13-24,41` — GPU/CPU 実行経路とスタンドアロン CLI。
