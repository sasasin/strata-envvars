# `STRATA_VIT_NO_MPP_W`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Metal 版の Strata 独自 vision tower で、重み行列（BF16 / F16）の積に使う Metal 4 tensor-op（MPP）を無効にし、通常の `vk_gemm_bf16` / `vk_gemm_f16` カーネルを選ばせる診断用スイッチ。attention score `S` と context `P*V` の積には作用しない。それらを切り替える名前はそれぞれ `STRATA_VIT_NO_MPP_S` と `STRATA_VIT_NO_MPP_PV`。全 product の MPP を止める `STRATA_VIT_NO_MPP` も別にある。`VitGpu::load` が重み積用の選択状態を落とし、`VitGpuImpl::wgemm` がその状態に応じて実際のカーネル名を渡す（`tools/vision/own/vit_metal.mm:238-243, 404-431`）。

この読み取りは `tools/vision/own/vit_metal.mm` にだけある。CMake で macOS の Metal own tower を有効にした build に入り（`tools/vision/own/CMakeLists.txt:56-69, 157-164`）、実行時に `strata-vision` が own tower を GPU で使うときに適用される。CPU tower、CUDA/HIP、SYCL、mtmd reader にはこの変数を読むコードがない。tower の選択は `--tower` が明示されればそちらが優先し、未指定時は `STRATA_VISION_TOWER` と `auto` の対応で決まる（`tools/vision/strata_vision.cpp:94-100, 137-170`）。

## 値と判定

値の内容は変換・比較されず、`std::getenv(...)` が null でないかだけを確認する（`tools/vision/own/vit_metal.mm:425-428`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal own GPU tower の `VitGpu::load` | このスイッチによる変更なし。通常の MPP 可否判定を使う | `1`、`0`、`true`、`false`、空文字、その他どんな設定値でも設定済みなら重み積の MPP を止める | なし（環境変数が設定されていれば値にかかわらず有効） |
| CPU / CUDA / HIP / SYCL / mtmd reader | 読み取りなし | 該当なし | 該当なし |

文字列全体の parse、先頭文字・空白・大文字小文字の検査、数値範囲や無効値 fallback はない。CLI 引数や設定ファイルからこの名前を上書きする処理も見つからない。

## 有効になる条件

- `strata-vision` が own tower の GPU 経路を使い、Metal 実装がビルドに含まれていること。`--tower mtmd` を選んだ場合や CPU 経路では効果がない（`tools/vision/strata_vision.cpp:161-170`; `tools/vision/own/own_reader.cpp:114-125, 128-149`）。
- MPP が利用できる条件は macOS 26 以降かつ GPU が Metal 4 対応で、MPP カーネルのコンパイルと積ごとの plain kernel との自己検査に通ること（`tools/vision/own/vit_metal.mm:404-423`）。ただしこの環境変数が設定されていれば、その検査結果にかかわらず BF16 / F16 重み積を plain にする。MPP が未対応・コンパイル失敗・自己検査失敗で元から plain のときは、実行カーネルに追加の変化はない。
- `STRATA_VIT_NO_MPP` が設定されていれば MPP ライブラリ自体が試されず全積が plain になるため、この変数は重み積の選択をさらに個別に指定するもの（同 `vit_metal.mm:404-428`）。

## 実行時の詳細

値は Metal own GPU tower の `VitGpu::load` 中、読込時に一度だけ調べ、`mpp_bf16` / `mpp_f16` の状態に反映する。これらの状態は同じ `VitGpuImpl` 内で画像 encode 時の重み行列積に用いられる（`tools/vision/own/vit_metal.mm:368-431, 238-243, 482-493, 532-539, 569-603`）。関数内 static cache ではないが、読込後に環境を変更しても既に作られた reader の選択状態は変わらず、新しい reader の load 時に反映される。

plain と MPP は同じ重み積の代替カーネルとして呼び分けられる。ここで確認できるコードはカーネル選択を変えるもので、生成される vision embedding の同一性や速度・精度の差を保証していない。`STRATA_VIT_NO_MPP_W` 固有のエラー終了経路はない。reader はロード後に stderr へ product の選択結果を出し、続けて GPU warm-up を行い、成功すれば stdout に `READY ... own` を出す（`tools/vision/own/vit_metal.mm:429-431`; `tools/vision/own/own_reader.cpp:121-125, 141-168`）。

## ログと測定値

stderr の `strata-vision: Metal tower on ...; products: BF16 weights ...` 行で選択を確認できる。変数が設定され、MPP が使えた場合、該当部分は `BF16 weights plain (STRATA_VIT_NO_MPP_W), F16 weights plain (STRATA_VIT_NO_MPP_W)` と表示される。MPP が使えない場合も `plain (STRATA_VIT_NO_MPP_W)` と表示される。attention S と P*V の表示はこの変数では変わらない（`tools/vision/own/vit_metal.mm:425-431`）。

この変数による性能値・精度値は `docs/DETAILS.md` に記載されていない。そこには vision reader の一般的な選択肢が記載されているが、この診断スイッチや Metal product の切替測定は扱っていない（`docs/DETAILS.md:984-1016`）。

## 根拠

- `tools/vision/own/vit_metal.mm:404-431` — Metal 4 条件、MPP 読込・自己検査、環境変数判定と stderr 表示。
- `tools/vision/own/vit_metal.mm:238-243, 482-493, 532-539, 569-603` — 選択状態から重み行列積カーネルを選び、encode で使う箇所。
- `tools/vision/own/CMakeLists.txt:56-69, 157-164` — macOS Metal own tower のビルド条件。
- `tools/vision/own/own_reader.cpp:114-125, 128-149, 151-168` — GPU/CPU 経路、読込時の適用、warm-up と READY。
- `tools/vision/strata_vision.cpp:94-100, 137-170` — tower 選択と own reader 起動。
- `docs/DETAILS.md:984-1016` — vision の一般的な利用説明。対象変数の説明はなし。
