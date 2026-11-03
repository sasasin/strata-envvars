# `STRATA_MTP_MULTI_COPY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP draft 用に mapped host memory から GPU へ入力を移す際、複数の領域を一つの CUDA/HIP カーネル起動でコピーするか、領域ごとにコピーするかを選びます。既定は複数領域をまとめる方式です。これはコピー手段の切り替えであり、MTP の入力値や draft の選択を変える CLI 設定ではありません。

## 値と判定

値を数値や真偽値として parse せず、`getenv()` の結果が null か、先頭文字が `'0'` かだけを調べます。空文字は設定済みですが先頭文字が終端文字なので、まとめる方式になります。

| 設定値 | コピー方式 |
|---|---|
| 未設定 | 複数領域を一つのカーネル起動でコピー（既定） |
| 空文字 | 複数領域を一つのカーネル起動でコピー |
| 先頭文字が `0`（例: `0`, `01`, `0anything`） | 領域ごとのコピーに切り替え |
| それ以外（例: `1`, `true`, `false`, 空白で始まる値） | 複数領域を一つのカーネル起動でコピー |

大文字小文字・後続文字・数値としての妥当性は検査しません。したがって `false` も有効扱いで、`0anything` は無効扱いです。対応する CLI 引数や他の環境変数による上書きは、この変数の読み取り経路にはありません。

## 有効になる条件

- この読み取りは `src/kernels/cuda/elementwise.cu` の実装にあり、CMake では CUDA または HIP を有効にしたときに同ファイルが `strata_kernels` に含まれます。Metal の MTP 経路は `MtpDrafter::draft()` 内で Metal engine に分岐するため、このコピー関数を通りません。
- CUDA/HIP の MTP draft が round または step の graph を初めて capture するときに作用します。MTP が使われず `copy_from_mapped_multi()` が呼ばれなければ、この変数は評価されません。
- `STRATA_MTP_MULTI_COPY=0` の領域ごと方式では、各領域について `words > 1024`、語数が 4 の倍数、src/dst が 16-byte aligned のすべてを満たす場合に `copy_from_mapped()` を使います。それ以外は `copy_i32_from_mapped()` を使います。
- まとめる方式では、領域情報をまとめた `MappedCopies` を作り、一回の `copy_from_mapped_multi_kernel` 起動で処理します。個々の領域は src/dst の 16-byte alignment と語数が 4 の倍数という条件を満たせば `float4` 単位で読み、そうでなければ `int32` 単位で読みます。

## 実行時の詳細

値は `copy_from_mapped_multi()` が呼ばれるたびに読みます。関数自体に static cache はありません。ただし MTP は CUDA graph を capture し、同じ T の round graph と同じ j の step graph がすでにあれば capture 関数は既存 graph を返します。そのため実際には、その graph を初めて作る時点の設定がコピー方式として graph に記録され、後から環境変数を書き換えても既存 graph の方式は変わりません。未 capture の別 graph は、作成時点で改めて読み取ります。chain 用 graph も `prepare_chain()` で capture されます。

通常の有効・無効を示すログはありません。入力数 `n <= 0` は何もしません。`n > 8` は stderr に `copy_from_mapped_multi: at most 8 copies` を出して終了コード 1 でプロセスを終了しますが、MTP の呼び出し数は round が 7、step が 2 です。GPU kernel 起動のエラーは `check_launch()` が stderr に `<kernel name> launch: <CUDA error>` を出して終了コード 1 にします。

## 根拠

- `src/kernels/cuda/elementwise.cu:423-448`: `STRATA_MTP_MULTI_COPY` の唯一の本番読み取り、先頭文字による分岐、8 領域上限、領域ごとの fallback と multi kernel の起動。
- `src/kernels/cuda/elementwise.cu:399-412`: multi kernel 内の 16-byte alignment / 4-word 条件に応じた `float4` または `int32` コピー。
- `src/kernels/cuda/elementwise.cu:299-309`: 領域ごと方式で選ばれる aligned float copy の前提条件と launch check。
- `src/kernels/cuda/elementwise.cu:122-129`: kernel 起動エラー時の stderr と終了処理。
- `src/core/mtp.cpp:1432-1453,1473-1484`: round は 7 領域、step は 2 領域を渡すこと、および capture 済み graph の再利用。
- `src/core/mtp.cpp:1702-1729,1928-1934`: Metal draft の別経路、CUDA/HIP draft の graph capture 呼び出し、chain graph の capture。
- `CMakeLists.txt:431-436,475-491`: CUDA または HIP backend の GPU core / kernel target と、`elementwise.cu` の組み込み。
- `src/kernels/verify_parity.cpp:107-163`: parity 用コードがこの値を `1` と `0` に切り替えてコピー結果を比較する。これは検証用コードであり、本番挙動の追加根拠にはしていません。
