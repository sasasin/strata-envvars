# `STRATA_VERIFY_ALL_SLOTS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `strata generate` のプロファイル済み expert cache を、初期 fill 後に全 slot について読み戻し、GGUF 内の元データと byte 単位で比較する診断フックです。通常の fill では最後に slot を一つ検証しますが、この変数を設定すると、パイプライン fill で実際に埋めた全 slot を検証します。GPU 上の slot の内容が元の expert blob と一致するかを調べる用途で、生成・cache の動作を変更する設定ではありません。

実装は `sycl/src/program/generate.cpp` にだけあります。CUDA 側の `src/program/generate.cpp` にはこの変数の読み取りはありません。

## 値と判定

値の parse はありません。fill 完了後の `std::getenv("STRATA_VERIFY_ALL_SLOTS") != nullptr` だけで判定します。

| 状態 | 結果 |
|---|---|
| 未設定 | 全 slot の追加検証を行わない |
| 設定あり | 値が空文字でも、`0`、`false`、その他の文字列でも全 slot の追加検証を行う |

この判定はプロセス内で static cache されません。判定に到達する前の環境変更は反映されます。検証関数が作られた後に変更しても、検証の有無は変わりません。

根拠: `sycl/src/program/generate.cpp:4703-4706`。

## 有効になる条件

環境変数が設定されていても、次の条件が必要です。

- SYCL 版の `strata generate` を実行している。
- expert profile が空でなく、cache fill に使うデータソース `srcp` がある。
- fill がパイプライン経路である。コード上の条件は `srcp == &gguf_src` かつ per-layer cache admission が無効で、`STRATA_FILL_SERIAL` が未設定であること。
- パイプライン fill が読み取りエラーなく完了する。

この経路は GGUF からの profile fill を 64 slot ずつ読み、device cache にコピーします。`STRATA_FILL_SERIAL` が設定されている場合（値の内容は問わない）、per-layer admission の場合、または `srcp` が `gguf_src` でない場合、この変数による全 slot 検証は設定されていても実行されません。パイプライン以外の fill では通常の1 slot 検証が別途行われます。

根拠: `sycl/src/program/generate.cpp:4634-4649,4697-4704,4788-4796`。

## 実行時の詳細

パイプライン fill の queue 完了を待った後、検証関数を作り、直ちに `after the fill` の比較を行います。さらに session の初期化が完了し `session is up` を出力した直後に `session up` として同じ全 slot をもう一度比較します。各比較では、各 expert の blob を GGUF から host buffer に読み、対応する device slot を host buffer に読み戻して `memcmp` します。差があった slot ごとに差分 byte 数、最初と最後の差分位置、fill 順序、layer/expert、slot 番号、アドレスを stderr に出し、最後に不一致 slot 数と最初の不一致 index を出します。GGUF の再読み込みに失敗した場合も不一致数に加えます。

この追加検証で差が出ても、この関数はログを出すだけで失敗終了させません。通常の1 slot 検証は別に行われ、そちらが失敗した場合はエラーを出して `return 1` します。診断関数内では、不一致時に限り `STRATA_VERIFY_FIND` が設定されていれば誤った blob の探索を行い、`STRATA_VERIFY_DUMP` が設定されていれば最初の不一致 slot の `.got` / `.want` ファイルを書きます。これら補助変数も設定有無で判定され、値の parse はありません。

根拠: `sycl/src/program/generate.cpp:4704-4747,4788-4796,5336-5339`。

## 文書との照合

`docs/INTEL.md` は Arc A770 の 4 GiB 超 cache slot の調査で全 slot の比較が通ったこと、および Arc Pro B70 の cache aliasing 調査で `STRATA_VERIFY_ALL_SLOTS=1` と `STRATA_VERIFY_FIND=1`、`STRATA_VERIFY_DUMP=dir` を使ったことを記しています。これは診断の利用例であり、測定・記録された環境での説明です（`docs/INTEL.md:718-726,747-755`）。実装上は値 `1` に限定されず、環境変数が設定されていることだけが条件です。
