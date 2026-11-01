# `GDN_PROBE_RUN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前を読むのは Metal の GDN prompt stage マイクロベンチマーク `gdn_chunk_bench` だけです。環境変数が設定されていると、各 token 長 `T` の通常計測に加えて、v2 の `gdn_cprep2` / `gdn_cstate2` pipeline を parameter 1、2、3 で個別に計測し、結果を stdout に出します。Strata の通常エンジンが読む設定ではなく、このベンチマークの追加 probe を選ぶ開発・診断用スイッチです。

## 値と判定

`std::getenv("GDN_PROBE_RUN")` の結果をポインターとして判定します。文字列の内容は parse しません。

| 値 | 判定 |
|---|---|
| 未設定 (`getenv` が `nullptr`) | probe を実行しない |
| 設定済み（空文字を含む） | probe を実行する |

`0`、`false`、その他の文字列も、設定されていれば同じく probe を実行します。数値変換、境界値検査、無効値時の fallback はありません。

## 有効になる条件

- `metal/tests/gdn_chunk_bench.cpp` の `main` を実行すること。対象ソースは GDN prompt stage のマイクロベンチマークおよび数値検査用と明記されています。
- Metal 専用の別 CMake プロジェクトでビルドすること。`metal/CMakeLists.txt` は Apple 以外の環境を拒否し、`tests/*.cpp` を個別 executable として登録します。このファイルから `gdn_chunk_bench` が作られます。
- ベンチマークで処理される各 `T` の反復で、変数を設定しておくこと。`--T` は対象の `T` 一覧を変えますが、probe の有効・無効を切り替える CLI 引数はこのプログラムにありません。

CUDA / HIP / SYCL の通常ビルドや Metal エンジンの生成・推論経路でこの変数を読む箇所は、対象 commit の全参照検索では見つかりませんでした。

## 実行時の詳細

読み取りは各 `T` 反復の probe ブロックに到達したときに行われ、`static` cache はありません。設定されている場合、その反復で `v2` を有効にして chunk dispatch を作り、`pr = 1..3` ごとに `gdn_cprep2` と `gdn_cstate2` の pipeline を作成して別々に `timeit` し、`probe <pr>: cprep2 ... cstate2 ... ms` を stdout に出力します。その後 `v2` を無効に戻します。

未設定の場合、この probe ブロックは何も出力せず、通常のベンチマーク処理を続けます。環境変数固有の警告・終了・失敗処理はありません。プログラム全体の終了コードは別の数値チェック結果 `fails` に基づき、最後に `fails ? 1 : 0` を返します。

## 根拠

- 参照一覧への掲載: `docs/envvars/000_envvers.md:381`。
- 候補名の Strata ソース全体の直接参照は1箇所: `metal/tests/gdn_chunk_bench.cpp:352`。
- 追加 probe の実行内容、parameter 範囲、stdout 出力、`v2` の復帰: `metal/tests/gdn_chunk_bench.cpp:352-364`。
- マイクロベンチマークであること、CLI 引数: `metal/tests/gdn_chunk_bench.cpp:1-7`。
- Metal 専用プロジェクトと tests の executable 登録: `metal/CMakeLists.txt:1-2,41-48`。
- ソース全体を検索した結果、通常エンジンや資料に別の `GDN_PROBE_RUN` 参照はありませんでした。
