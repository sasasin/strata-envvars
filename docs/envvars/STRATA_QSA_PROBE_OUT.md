# `STRATA_QSA_PROBE_OUT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

gfx906 向け HIP の単体 QSA query-swizzle プローブが、計算結果を保存するファイルのパスを指定します。Strata の通常の推論サーバーや engine の環境設定ではありません。値は結果ファイルの場所にだけ使われ、QSA 計算の選択・設定には使われません。

## 値と判定

プローブの `main()` は、4番目の位置引数（`output.bin`）がなければ `std::getenv("STRATA_QSA_PROBE_OUT")` を一度呼びます。環境変数の内容は数値変換や文字列比較をせず、C のファイルパスとして使います。

| 4番目の位置引数 | 環境変数 | 結果 |
|---|---|---|
| 指定あり | 任意 | 位置引数を使用。環境変数は参照しない |
| 指定なし | unset | stderr に `qsa_query_swizzle_probe: pass output.bin as fourth positional argument or set STRATA_QSA_PROBE_OUT` を出し、終了コード 2 |
| 指定なし | 空文字 | unset と同じエラー、終了コード 2 |
| 指定なし | 空でない文字列 | その文字列を出力パスとして使用 |

位置引数が空文字の場合も環境変数へ fallback せず、同じエラーになります。空白の除去やパスの存在確認は事前に行いません。環境変数は `main()` 内で一度読むため、このプロセスで読み取り後に値を変更しても反映されません。

根拠: `bench/gfx906_qsa_query_swizzle_probe.cpp:265-279`。

## 有効になる条件

この変数を読む実装は `gfx906_qsa_query_swizzle_probe` だけです。CMake は `STRATA_HIP_GFX906` が有効な場合に限り、この実行ファイルを追加します（`CMakeLists.txt:2003-2005`）。したがって、この変数を設定しても通常の Strata 実行ファイルには作用しません。

## 実行時の詳細

プローブは QSA decode attention の実行、出力検査、反復結果の一致確認を行った後、指定パスを `std::fopen(output, "wb")` で開き、結果の `float` 配列を書き込みます。`wb` のため、同名ファイルがあれば内容を上書きします。ファイルを開けない場合は `qsa_query_swizzle_probe: cannot open output file`、全件を書けない場合または close に失敗した場合は `qsa_query_swizzle_probe: cannot write complete output file` を stderr に出して終了コード 2 になります。成功時の標準出力には `output=<パス>` を含む `PASS ...` 行が出ます。

環境変数が指定するのは出力先だけです。プローブ内では固定データと QSA 計算を用い、結果配列をバイナリで保存します。設計資料 `docs/DETAILS.md` および `docs/QSAROWS.md` には、この出力先変数の説明は見当たりません。

根拠: `bench/gfx906_qsa_query_swizzle_probe.cpp:235-259`。
