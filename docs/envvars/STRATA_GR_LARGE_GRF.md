# `STRATA_GR_LARGE_GRF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata の SYCL fused hyper-connection（GR）read で、一部の down/up GPU kernel に Intel の 256-register-per-thread GRF 属性を付けるか選びます。未設定時は Alchemist（Arc A-series）だけ有効、設定時は `atoi` の結果で強制 ON/OFF です。Strata のソースコメントは、128-register 時に A770 の up kernel が約 3.4 KB/thread を spill し、256-register にすると Xe core あたりの常駐 thread 数が半分になると記しています。これはコードコメント上の記述であり、この調査で再測定した値ではありません。実装は `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` の `gr_large_grf` と各 kernel launch です（同ファイル:808-818, 3360-3383, 3487-3493）。

この変数は CUDA/HIP の通常実装ではなく、SYCL の fused GR read 実装でのみ読み取られます。SYCL build が `fused_gr.dp.cpp` を kernel library に含めます（`engine/sycl/CMakeLists.txt:273-288`）。その fused read 自体も常時使われるわけではありません。`strata generate` では `--gr-native-mmvf`（または `--native` がこの設定を有効化）を選び、`--no-fused-gr`、GPU stage、layer/half dump、stage timing で無効化されない場合に fused GR が設定されます（`engine/sycl/src/program/generate.cpp:463,621,833,937,1952,2209,2592-2596,3221-3228`）。さらに layer の stage/half が先頭側で、モデル形状が `N/HC/LR` の実装値と一致する必要があります（`engine/sycl/src/core/layer.cpp:1558-1559`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`）。

## 値と判定

`gr_large_grf` は `std::getenv` で読み、値が存在すれば `std::atoi(e) != 0`、未設定なら `intel_gpu_gen` が `Alchemist` かを返します。値を文字列全体として検証せず、`atoi` が読む先頭の整数部分のゼロ/非ゼロで決まります（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:812-818`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL fused GR read の `gr_large_grf` 評価 | 最初に評価された queue の GPU が Alchemist なら ON。それ以外は OFF | `1`, `2`, `-1`, `1tail`（`atoi` が非ゼロ） | 空文字、`0`, `0tail`, `true`, 数字で始まらない文字列（`atoi` が 0） |

空文字も「設定あり」なので既定の世代判定には進まず、`atoi("") == 0` として OFF です。先頭空白と符号は `atoi` の整数変換に従い、例えば `  +1tail` は ON です。大文字小文字の区別や `true`/`false` の特別扱いはありません。末尾の非数字は整数部分の後なら無視されます。変換エラーを報告する処理や範囲チェックはありません（`std::atoi` の範囲外入力については結果を保証できません）。

未設定時の世代判定は `strata::intel_gpu_gen` に委ねられます。同ヘルパーは `STRATA_INTEL_GEN` が `battlemage` / `alchemist` / `unknown` のいずれかならその分類を使い、空文字・未設定なら device architecture/name 等で分類します。したがって `STRATA_GR_LARGE_GRF` が未設定のときは `STRATA_INTEL_GEN=alchemist` で既定 ON、`battlemage` または `unknown` で既定 OFF にできます。`STRATA_GR_LARGE_GRF` 自体が設定されていればその `atoi` 判定が優先されます（`engine/sycl/include/strata/sycl_queue.hpp:139-191`）。

## 有効になる条件

- SYCL build の fused GR kernel が実行されること。CUDA/HIP build にはこの読み取り箇所がありません（`engine/sycl/CMakeLists.txt:273-288`）。
- `strata generate` が fused GR を選び、該当 layer/half と対応するモデル形状を通ること。CLI/model 条件は「役割」を参照（`engine/sycl/src/program/generate.cpp:3221-3228`; `engine/sycl/src/core/layer.cpp:1558-1559`）。
- `STRATA_GR_V3` が有効で、device local memory 条件を満たして2-kernel v3 経路が選ばれる場合は、通常 GRF 分岐より前に戻るためこの設定は使われません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202,3296-3297`）。
- 通常経路では sliced down kernel に 256 属性を付ける分岐があり、up kernel でも通常/`STRATA_GR_MORE_GROUPS` 用 kernel の launch に属性を指定します（同ファイル:3360-3383,3485-3493）。ただし cached-norm / prepared-lo が選ばれると up の launch が分岐し、up 側に属性を付けない経路があります（同ファイル:3471-3493）。専用 private GR 経路は `gr_large_grf` が OFF の場合に限って `gf_enabled` の条件を満たすため、この変数が ON のときは選択されません（同ファイル:2685-2688,3466-3470）。`STRATA_GR_DOWN_SLICED` や `STRATA_GR_MORE_GROUPS` の選択も down/up のどの launch が使われるかに関係します（同ファイル:820-832,834-836,3360-3415,3485-3493）。
- 未設定時の既定は GPU 世代に依存します。明示値は世代判定を上書きします。queue は `gr_large_grf` の初回評価時に static 値へ保存されるため、プロセス実行中の環境変更や別 queue/device への切替は再評価されません（同ファイル:812-818）。

## 実行時の詳細

最初に `gr_large_grf(q)` が呼ばれた時、関数内 `static const bool` の初期化 lambda が `STRATA_GR_LARGE_GRF` を読みます。値が設定されていればその場で `atoi` 判定し、未設定なら同じ初回呼び出しの `q` から GPU 世代を調べます。結果はプロセス内で一度だけ保存され、以後はその bool を返します。環境変数をプロセス起動後に変更しても反映されず、複数 GPU/queue の場合も初回 queue の判定が共有されます（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:812-818`）。

通常の `fused_gr_read_multi` では、sliced down の launch と up の launch でこの bool を使い、ON なら SYCL `grf_size<256>` property 付き kernel、OFF なら同 property のない kernel を選びます。down では sliced 経路、up では multi-token kernel / `STRATA_GR_MORE_GROUPS` 経路が対象です（同ファイル:3360-3383,3485-3493）。`fused_gr_read` の単一 token API も `kDownXnTooBig`、sliced/norm split/direct のいずれかで multi-read API に委譲します。これらを使わず単一 read の通常 kernel を直接起動する場合は、この GRF 選択を通りません（同ファイル:3510-3555）。

CLI 引数が環境変数を読み替えたり、環境変数を子プロセスへ転送したりする処理は、この経路では確認できません。CLI やモデルの条件は fused read の利用可否を決めるもので、GRF 値の parse を変更するものではありません。

## ログと測定値

この変数の読み取り、ON/OFF、kernel property 選択に対応する Strata 独自のログや警告はありません。`atoi` で 0 になる不正文字列もエラーとして報告せず OFF 扱いです。ソースコメントには A770 の spill に関する記述がありますが、測定条件の詳細は記載されていないため、性能値として一般化できません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:808-811`）。

## 根拠

- 値の読み取り、parse、GPU 世代 fallback、static cache: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:808-818`
- down/up の large-GRF kernel 選択: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1166-1197,1213-1238,3360-3383,3485-3493`
- v3 経路での早期 return: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3168-3202,3296-3297`
- 単一 read から multi read への委譲: `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3510-3533`
- fused GR の CLI 条件と layer/model 条件: `engine/sycl/src/program/generate.cpp:3221-3228`; `engine/sycl/src/core/layer.cpp:1558-1559`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3506-3508`
- Intel GPU 世代分類と `STRATA_INTEL_GEN`: `engine/sycl/include/strata/sycl_queue.hpp:139-191`
- SYCL kernel library の構成: `engine/sycl/CMakeLists.txt:273-288`
