# `STRATA_VIT_ROWS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 同梱の `strata-vision` にある独自 GPU Vision tower の行列積チャンク行数を指定する診断用環境変数です。既定は 512 行で、受理される値を使うと Vision encoder の layer 内の projection などを処理する行数と、その行数に合わせた一時 GPU buffer のサイズが変わります。対象は CUDA/HIP、Metal、SYCL の GPU 実装です。通常のテキスト生成エンジンや CPU Vision tower はこの名前を読みません（CUDA/HIP: `tools/vision/own/vit_gpu.cu:461,1002`; Metal: `tools/vision/own/vit_metal.mm:114,467`; SYCL: `tools/vision/own/vit_sycl.cpp:292,476`; CPU/GPU reader 分岐: `tools/vision/own/own_reader.cpp:112-137`）。

この値は `--tower` や `--gpu` の選択を行いません。GPU の own tower が選択され `VitGpu::load` が実行された場合にだけ適用されます。`strata-vision` の tower 選択は `--tower` が環境の `STRATA_VISION_TOWER` より優先し、GPU 使用は別の `--gpu` 引数です（`tools/vision/strata_vision.cpp:94-112,136-170`）。

## 値と判定

各 GPU backend の `VitGpu::load` が `std::getenv` で値を読み、`std::atoi` の結果が 16 以上なら `kRows` に代入します。変換は文字列全体の厳密な検証ではなく、`atoi` の整数接頭辞変換です。unset または `atoi` 結果が 16 未満なら既定値 512 のままです。上限 clamp はありません（CUDA/HIP: `tools/vision/own/vit_gpu.cu:461,1002`; Metal: `tools/vision/own/vit_metal.mm:114,467`; SYCL: `tools/vision/own/vit_sycl.cpp:292,476`）。

| backend | unset | 受理例 | 既定値のままになる例 |
|---|---|---|---|
| CUDA/HIP, Metal, SYCL | `kRows = 512` | `16`, `512`, `1024`, `16tail` → 16, 512, 1024, 16 | 空文字、`0`, `15`, `-16`, `true`, `0anything` |

先頭の空白や符号は `atoi` の規則で扱われます。小数点以降や数字の後ろの文字は検証されず、数値接頭辞のみが使われます（例: `16.5` は 16）。したがって `16tail` は受理され、`15tail` は 16 未満なので無視されます。値の上限チェックがないため、極端に大きい値に対する安全な上限は実装されていません。

## 有効になる条件

- `strata-vision` が own tower を使い、さらに GPU reader を実行すること。`--tower mtmd` では読み取りません。`--tower auto` はファイル/backend の対応で own または mtmd を選び、`--gpu` がない経路は CPU reader です（`tools/vision/strata_vision.cpp:94-112,136-170`; `tools/vision/own/own_reader.cpp:112-137`）。
- 対応 backend を組み込んだビルドであること。CUDA/HIP は `vit_gpu.cu`、SYCL は `vit_sycl.cpp`、macOS Metal は `vit_metal.mm` がビルド対象になる構成です（`tools/vision/own/CMakeLists.txt:13-69,120-163`）。
- 該当する `VitGpu::load` で値が一度読み込まれること。`--threads`、`--max-tokens`、`--min-tokens` や別環境変数による `kRows` の優先・上書きはありません。`STRATA_VIT_SCORES` などは別の score buffer 設定です（`tools/vision/own/vit_gpu.cu:1001-1008`; `tools/vision/own/vit_metal.mm:466-471`; `tools/vision/own/vit_sycl.cpp:475-479`）。

## 実行時の詳細

各 backend の GPU reader は tower load 中に環境値を読み、その `VitGpu` インスタンスの `kRows` に保存します。static cache は使いませんが、load 後に環境を変更しても、そのインスタンスの値は変わりません。`strata-vision` の GPU own reader は `READY` を出す前に warm-up encode を行います（`tools/vision/own/own_reader.cpp:120-124,150-168`）。

buffer 確保では実画像の patch 行数 `N` と `kRows` の小さい方 `R = min(N, kRows)` を用い、`d_y`、入力用 `d_a`、FFN 用 `d_f16` などのサイズを `R` に比例させます（CUDA/HIP: `tools/vision/own/vit_gpu.cu:780-808`; Metal: `tools/vision/own/vit_metal.mm:251-272`; SYCL: `tools/vision/own/vit_sycl.cpp:372-391`）。encode 中も `kRows` ずつ layer の正規化・QKV projection などを進め、最後の chunk は残り行数に縮めます（CUDA/HIP: `tools/vision/own/vit_gpu.cu:1064-1071`; Metal: `tools/vision/own/vit_metal.mm:531-539`; SYCL: `tools/vision/own/vit_sycl.cpp:538-545`）。値を増やすと chunk buffer が大きくなる一方、画像の `N` を超えた分は `R` に反映されません。ソースは行数以外の結果同一性を保証していません。

この変数専用のログや警告はありません。buffer 確保または warm-up が失敗すると own reader の起動失敗経路になります。自動選択で fallback 可能な構成では `strata-vision` が stderr に `strata-vision: Strata's picture reader did not start (...); reading pictures with llama.cpp's reader` を出して mtmd reader に移ります。fallback しない own 起動では `ERR ...` を出して失敗します（`tools/vision/own/own_reader.cpp:92-100,120-125,150-168`; `tools/vision/strata_vision.cpp:161-175`）。この診断の詳細な失敗文言や fallback 条件は `STRATA_VIT_ROWS` 固有ではありません。

## ログと測定値

`STRATA_VIT_ROWS` の値を表示するログはありません。調査文書側の候補索引 `docs/envvars/000_envvers.md:2249` に名前があります。Strata の実装資料・ソースから、この設定についての測定値や推奨値は確認できないため、性能値は記載しません。

## 根拠

- 候補一覧（Strata のソースツリー外にある調査文書）: `docs/envvars/000_envvers.md:2249`。
- 値の読み取り、既定値、行列 chunk: `tools/vision/own/vit_gpu.cu:461,780-808,1002,1064-1071`; `tools/vision/own/vit_metal.mm:114,251-272,467,531-539`; `tools/vision/own/vit_sycl.cpp:292,372-391,476,538-545`。
- own/CPU/GPU reader の選択と起動失敗経路: `tools/vision/strata_vision.cpp:94-112,136-175`; `tools/vision/own/own_reader.cpp:89-100,112-168`。
- backend の build 条件: `tools/vision/own/CMakeLists.txt:13-69,120-163`。
