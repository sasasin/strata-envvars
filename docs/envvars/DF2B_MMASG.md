# `DF2B_MMASG`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal の standalone DFlash2 ベンチマーク `df2_bench` で、`DF2B_KIND=mma` のときに使う `gemv_mma_2_<値>` カーネル名の suffix と dispatch geometry の値を指定します。通常の `strata` CLI やサーバーがこの変数を読む箇所は確認できませんでした。

## 値と判定

| 環境値 | ベンチマーク内での扱い |
|---|---|
| 未設定 | `"4"` を使う。カーネル名は `gemv_mma_2_4`、`sg` は 4。 |
| 設定あり | 文字列をそのままカーネル名に連結し、同じ文字列を `std::atoi` に渡して `sg` にする。 |
| 空文字 | 設定ありとして空文字を保持する。カーネル名 suffix は空、`atoi("")` の結果 `sg` は 0。 |

`atoi` は整数全体の厳密な検証ではありません。先頭の空白と符号の後にある数字列を変換し、数字が始まらない場合は 0 を返し、数字列の後ろは値に含めません（例: `4x` は 4）。コードには許容値の検査や範囲制限がありません。`sg` は grid の計算で `8 * sg` による除算、threadgroup size で `32 * sg` に使われます。したがって空文字や数字で始まらない値は 0 となり、grid 計算時にゼロ除算になる経路があります。その他の値が有効なカーネル設定かどうかは、この環境変数の読み取りコードでは検証されません。

## 有効になる条件

- macOS 専用の `metal/` CMake プロジェクトでビルドされる `metal/tests/df2_bench.cpp` の実行時に限ります。CMake は `metal/tests/*.cpp` を個別 executable として登録します。
- `DF2B_KIND` が文字列全体で `"mma"` と一致し、Q4 行列が native 経路を通る必要があります。未設定、空文字、`"MMA"`、`"mma "` などでは native 経路にならず、この変数は読まれません。
- `DF2B_SKIP` が文字列全体で `"mm"` の場合、行列 dispatch helper は早期 return するため、`DF2B_MMASG` の読み取りにも到達しません。
- 関連する CLI 引数は任意の kernel directory を指定する `argv[1]` だけで、この値を上書きする CLI option はありません。`DF2B_ENGINE_KERNELS` は `DF2B_KIND=mma` 時に別の Metal kernel files を読むディレクトリを指定します。

## 実行時の詳細

`df2_bench` は起動時に Metal context と `dflash2.metal` を準備し、`DF2B_KIND=mma` なら `DF2B_ENGINE_KERNELS` から `quant.metal`、`units.metal`、`gemv.metal`、`mma.metal` をコンパイルします。native Q4 行列の dispatch を組み立てるたびに `DF2B_MMASG` を読み、`gemv_mma_2_<値>` という関数名で pipeline を取得します。同じ pipeline 名と列数はベンチマーク側の map に保持されます。環境値自体を static cache する処理はありませんが、通常の実行中に環境を書き換えるコードも見つかりませんでした。

この値で pipeline を作れない場合、Metal runtime helper は標準エラーに `mtl: no function <関数名> ...` または `mtl: pipeline <関数名>: ...` を出して終了コード 3 で終了します。値が 0 になりゼロ除算へ進む場合の実行結果はコード上で定義されていません。正常に計測へ進めば、ベンチマークは stdout に設定行と各 stage の GPU/wall median 等を出します。これらは standalone ベンチマークの出力で、通常の推論動作を表すものではありません。

## 根拠

- `metal/tests/df2_bench.cpp:1-9,62-82` — DFlash2 Metal 計測プログラムであること、起動時の `DF2B_KIND` 判定と関連 kernel の読み込み。
- `metal/tests/df2_bench.cpp:285-288,305-317` — `DF2B_SKIP` による早期 return、`DF2B_MMASG` の既定値・読み取り、関数名と grid/threadgroup 計算。
- `metal/tests/df2_bench.cpp:423-438,441-465` — 行列 helper の呼び出し、計測の実行、stdout の結果形式。
- `metal/CMakeLists.txt:1-2,13-17,41-48` — Metal project が macOS 専用であり、`tests/*.cpp` を個別 executable として登録すること。
- `metal/src/mtl_rt.mm:484-521` — pipeline 関数が見つからない場合・作成に失敗した場合の stderr と終了コード 3。
