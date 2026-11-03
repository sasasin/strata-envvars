# `DS4_VISION_NO_MPP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 の Metal vision tower で、Metal 4 tensor-op GEMM（MPP）を選ばず plain GEMM を使わせます。これは Metal backend の vision encode 経路だけにある opt-out です。Metal 以外の backend に同名変数を読む Strata の実装は見つかりませんでした。Metal の CMake は macOS 以外では構成を停止し、Metal 専用の `strata_ds4` に vision 実装を含めます（`metal/CMakeLists.txt:16-18,135-146,165-169`）。

## 値と判定

| 状態 | 判定と結果 |
|---|---|
| 未設定 | この変数による opt-out はない。ほかの条件を満たせば MPP の選択を試みる。 |
| 設定あり | 値の内容にかかわらず MPP を使わない。`1` だけでなく `0`、空文字、任意の文字列も同じ。 |

実装は `std::getenv("DS4_VISION_NO_MPP") != nullptr` で設定有無だけを調べ、整数や真偽値への変換、文字列比較はしません（`metal/src/engine/ds4_vision_metal.cpp:189-194`）。したがって空文字も設定ありとして扱われます。

## 有効になる条件

この変数が効くのは、macOS の Metal `strata_ds4` で DeepSeek-V4.1 vision tower の `encode()` が呼ばれた場合です。Metal ビルドでは `STRATA_GPU_METAL` 経路から `strata::ds4::vismetal::encode()` を呼びます（`src/dsv41/ds4_vision.cu:551-574`）。モデルが画像を処理しない実行では、この判定に到達しません。

未設定なら、MPP はさらに次の条件を満たすときだけ選ばれます。GPU と macOS が Metal 4 をサポートし、MPP kernel のコンパイルが成功し、plain kernel と比較する自己検査が成功することです。`DS4_VISION_REF_GEMM` が設定されている場合も MPP を使いません。`DS4_VISION_FORCE_MPP_FAIL` が設定されている場合は、Metal 4 対応確認後に MPP を不採用にします（`metal/src/engine/ds4_vision_metal.cpp:189-207`）。

## 実行時の詳細

変数の値は `encode()` 内から呼ばれる `choose_mpp()` が参照します。選択結果は関数内の `static const MppChoice` に保存されるため、プロセス起動後でも最初の vision encode より前の環境変更は判定に反映されますが、最初の判定後の変更は再評価されません（`metal/src/engine/ds4_vision_metal.cpp:217-227`）。

設定されていると `choose_mpp()` は理由を `asked for by DS4_VISION_NO_MPP / DS4_VISION_REF_GEMM` とし、MPP 用 kernel のコンパイルと自己検査を行わず plain kernel を選びます。stderr には次の行が出ます（環境変数が設定されている場合でも、表示上は `=1` と値を付けません）。

```text
ds4: vision tower GEMM: plain kernel (asked for by DS4_VISION_NO_MPP / DS4_VISION_REF_GEMM)
```

選択結果 `use_mpp=false` では GEMM 呼び出しは plain `vis_gemm`（または別途指定された `DS4_VISION_REF_GEMM` 用 reference pipeline）へ進みます。MPP が有効な場合だけ MPP pipeline が使われ、attention GEMM と softmax の scale の渡し方も `use_mpp` に応じて切り替わります（`metal/src/engine/ds4_vision_metal.cpp:235-248,261-276,309-315`）。

この変数自体は警告やエラーを発生させません。plain kernel のコンパイルに失敗すると Metal runtime の `compile()` が stderr に失敗内容を出して終了コード 3 で終了します（`metal/src/mtl_rt.mm:332-341`）。pipeline 作成や encode 中の失敗はエラー文字列を返し、画像 encode の呼び出し側では stderr に表示して終了コード 1 を返す経路があります（`metal/src/engine/ds4_vision_metal.cpp:53-60,245-252,349-354`; `src/dsv41/ds4_vision.cu:568-570`; `src/dsv41/ds4_main.cpp:2645-2651`）。

## 根拠

- 候補一覧には `DS4_VISION_NO_MPP` が掲載されています（`docs/envvars/000_envvers.md:444`）。Strata 所有コードで値を読む箇所は `metal/src/engine/ds4_vision_metal.cpp:192` の `getenv` 判定です。動的 helper への名前の受け渡しはありません。
- MPP の選択条件、plain kernel への理由ログ、読み取り結果の cache は `metal/src/engine/ds4_vision_metal.cpp:189-212,217-227`。
- Metal 4 の OS/GPU 判定は `metal/src/engine/ds4_vision_metal.cpp:194-195` と `metal/src/mtl_rt.mm:325-328`。
- Metal 専用ビルドと DS4 vision ソースの組み込みは `metal/CMakeLists.txt:16-18,132-146,165-169`。
