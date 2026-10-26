# `CHAIN_PREFETCH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の `token_chain` 測定プログラムで、次の HC read が使う重み範囲を先読みする dispatch を追加します。Strata の Metal エンジン本体で使う環境変数ではありません。`metal/tests/token_chain.cpp` のみで参照され、このファイルは `metal/CMakeLists.txt` の `metal/tests/*.cpp` 一括登録により `token_chain` という実行ファイルになります。CMake の test 登録は `runtime_hello` だけです（`metal/CMakeLists.txt:41-47,65-68`）。

## 値と判定

| 環境変数の状態 | `token_chain` 内の判定 | 結果 |
|---|---|---|
| 未設定 | `getenv()` が null | prefetch dispatch を追加しない |
| 設定あり | `getenv()` が null でない | prefetch dispatch を追加する |

値の内容は parse も比較もしません。したがって `1` に限らず、`0`、空文字、その他の文字列も、設定されていれば同じく有効です。判定は `main()` 内で一度行われ、以後の処理はこの bool を使います（`metal/tests/token_chain.cpp:59-83,178-180`）。

## 有効になる条件

- macOS 専用の独立した Metal CMake プロジェクトでビルドされる `token_chain` 専用です。通常の CUDA/HIP/SYCL ビルドにこのコードは含まれません（`metal/CMakeLists.txt:1-3,16-18,41-47`）。
- `token_chain` に GGUF shard を渡して実行する必要があります。実行ファイルは引数が不足すると usage を stderr に出し、終了コード 2 で終了します（`metal/tests/token_chain.cpp:59-60`）。
- 環境変数が設定されても、最後の HC read (`final_`) の後には次の read がないため、そこに対する先読み範囲は追加されません（`metal/tests/token_chain.cpp:360-381`）。
- `docs/DETAILS.md` と Metal の設計資料に、この環境変数による速度向上などの測定値は見つかりません。性能効果はここでは断定できません。

## 実行時の詳細

各非最終 HC read の後、コードはモデル構造に従って次の read を決めます。次が同じ block の `hc_ffn` ならその down/inject/up 重みを、それ以外は次 block の `hc_attn` を対象にします。最終 block の次は `output_hc` で、こちらは down/up の重みを対象にします。Q8_0 の3-dispatch経路 (`hc_mode == "q8_3"`) では Q8 バッファ上の変換済み範囲、それ以外では元の重みバッファ上の範囲を `pending` に記録します（`metal/tests/token_chain.cpp:326-329,360-380`）。

次の projection GEMV を追加した後、pending の範囲ごとに `slc_touch` dispatch を積みます。dispatch は対象範囲を16-byte単位で読み、結果が特定値 `0x9e3779b9` のときだけ sink に書きます（`metal/tests/token_chain.cpp:194-206,220-230`; `metal/kernels/glue.metal:49-63`）。測定プログラムでは prefetch dispatch を `prefetch` クラスとして数え、その範囲の byte 数も集計します。最後に実行時間・実効帯域などを stdout に出します。これらの出力値は測定結果であり、環境変数の有効性やエラーを示すログではありません（`metal/tests/token_chain.cpp:644-659`）。

`--graph` が指定された場合、コマンドバッファ内で先読み dispatch と先行 projection を重ねられるよう、`push_prefetch()` は dispatch の `barrier` を無効にする状態を設定します。`run_graph()` は `barrier` が付いた dispatch の前にだけ buffer memory barrier を挿入します。`--graph` がない既定経路は serial encoder (`cx.run(ds)`) なので、prefetch dispatch は追加されても他の dispatch と重なりません（`metal/tests/token_chain.cpp:61-82,161-170,194-203,647`; `metal/src/mtl_rt.h:55-63,103-106`; `metal/src/mtl_rt.mm:296-304`）。

## 根拠

- 環境変数の全参照: `metal/tests/token_chain.cpp:178-180`。リポジトリ全体の完全名検索でもこの1箇所のみ。
- 実行ファイルがテスト用ソース群の一つとして登録されること: `metal/CMakeLists.txt:41-47`。
- 対象範囲の決定と pending 登録: `metal/tests/token_chain.cpp:360-380`。
- prefetch dispatch の組み立てと投入: `metal/tests/token_chain.cpp:194-206,220-230`。
- 読み出し kernel: `metal/kernels/glue.metal:49-63`。
- dispatch barrier の適用: `metal/src/mtl_rt.h:55-63,103-106`; `metal/src/mtl_rt.mm:296-304`。
