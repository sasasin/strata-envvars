# `STRATA_CACHE_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソース。外部ライブラリやドライバーが独自に読む環境変数は対象外。

## 役割

SYCL の prompt expert int8 経路で使う、int8 と FP16 の処理時間が逆転する平均 rows/expert（crossover）のキャッシュファイルを置くディレクトリを指定します。ファイル名は常に `i8-crossover.txt` です。この変数はキャッシュの場所だけを変え、int8 経路を有効化したり、測定値や閾値を直接指定したりしません。

## 値と判定

| `STRATA_CACHE_DIR` | 使用するファイル |
|---|---|
| 未設定、または空文字 | `HOME` が設定されていれば `$HOME/.cache/strata/i8-crossover.txt`。未設定なら `LOCALAPPDATA` が設定されている場合 `%LOCALAPPDATA%/strata/i8-crossover.txt`。両方未設定ならキャッシュなし。 |
| 非空文字列 | 値をディレクトリとしてそのまま使い、末尾に `/i8-crossover.txt` を連結。 |

空白除去、パス正規化、存在確認はありません。`HOME` または `LOCALAPPDATA` が空文字で設定されている場合も getenv は成功するため、それぞれ `/.cache/strata/i8-crossover.txt` または `/strata/i8-crossover.txt` になります。末尾が `/` の値では `//i8-crossover.txt` になります（通常の POSIX パス解釈では同じ場所を指します）。Windows でもコードは `/` を連結します。ファイルを読めない、存在しない、または一致するキーがない場合はキャッシュヒットになりません。書き込み時は、最初の `fopen` が失敗した場合に対象ディレクトリへ `mkdir(..., 0755)` を一度試してから再度開きます。親ディレクトリを再帰作成せず、書き込み失敗のログも出しません。

## 有効になる条件

この変数が使われるのは、SYCL prompt の expert 処理が int8 の `auto` モードで crossover を必要とした場合です。既定では、Battlemage と識別され、該当 int8 kernel が利用可能なデバイスで `auto` が選ばれます。`STRATA_PREFILL_MMQ=auto`（またはその alias `STRATA_PF_I8=auto`）でも選べます。他の GPU では既定は FP16 経路であり、`STRATA_CACHE_DIR` を指定しただけでは測定もキャッシュ読み書きも行いません。

さらに対象 layer が native expert で、対応する gate/up・down format、640×2560 の形状、kernel availability などの int8 経路条件を満たす必要があります。auto で crossover を初回計算するとき、デバイス名・driver version・gate/up と down の形式番号・形状からキーを作ります。同一プロセス内では queue と形式ごとに計算結果を map に保持するため、同じキーで毎 group ごとにファイルを読み直すわけではありません。

## 実行時の詳細

auto 経路でキーがまだ map にないとき、実装はキャッシュを検索します。一致行があれば rows と confident flag を読み込み、stderr に `strata: int8 experts: crossover ... from the cache for ...` と出して計測を省略します。一致しなければ合成 expert を使って 16、32、64、128、256 rows の int8/FP16 chain を測り、crossover を算出します。測定成功時は結果をファイルへ書き、auto は group の平均 rows/expert が crossover 未満なら int8、そうでなければ FP16 を使います。測定に失敗すると閾値64 rows、confidence false の結果となり、ソース上その失敗結果はキャッシュへ書きません。

キャッシュファイルは行ごとに `key<TAB>rows<TAB>confident` の形式です。読み取りは `sscanf` で数値変換し、走査中に一致した行を結果へ代入します。書き込みでは同じ key の既存行を除いて他の key の行を残し、現在の結果を書きます。読み取り時・書き込み時に `i8_cache_file()` がそれぞれ環境を参照するため、値は静的変数に一度だけ保存される形ではありません。通常の運用でプロセス中に環境を変更した場合の挙動は、読み込みと書き込みの間で別ディレクトリになる可能性があり、サポートされた設定変更としては示されていません。

## 根拠

- `sycl/src/prefill/prefill.cpp:858-865` — `STRATA_CACHE_DIR` の読み取り、空値時の `HOME` / `LOCALAPPDATA` fallback、ファイル名。
- `sycl/src/prefill/prefill.cpp:867-903` — ファイルの読み書き、行形式、既存 key の保持、単一階層の mkdir。
- `sycl/src/prefill/prefill.cpp:906-919,999-1029` — cache hit のログ、計測、失敗時の64 rows fallback、成功時の保存。
- `sycl/src/prefill/prefill.cpp:275-292,4230-4235,4266-4276` — int8 mode の既定と適用条件、auto 閾値での group 選択。
- `sycl/include/strata/prefill/esimd_moe.hpp:39-50` — auto / 強制 / 既定 mode の判定。
- `docs/INTEL_INT8_EXPERTS.md:18-27` — auto の crossover 利用と既定 cache path の説明。コード上の path fallback は同文書の短い説明より細かく上記の通り。
