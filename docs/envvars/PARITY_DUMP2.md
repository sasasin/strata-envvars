# `PARITY_DUMP2`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

SYCL 版 `qsa_prompt_attn_parity` の追加診断出力を有効にします。int8 KV の FP64 参照計算から、先頭の query/head/output 成分に関する 4 個の選択 cell と 6 個の query の score を標準出力へ出します。通常の Strata エンジンの挙動を切り替える変数ではありません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | 追加出力しない（`std::getenv` が null） |
| 設定あり | 値の内容にかかわらず追加出力の条件判定へ進む。`1` などの文字列比較や数値変換はしない。空文字も設定ありとして扱う |

値は parse されず、fallback、clamp、無効値警告もありません。判定は `run()` の参照計算ループ内で `std::getenv("PARITY_DUMP2")` を呼ぶたびに行われ、static cache はありません。

## 有効になる条件

環境変数が設定されていても、出力にはすべての条件が必要です。

- 実行対象は `qsa_prompt_attn_parity`。SYCL CMake はこの実行ファイルを構築しますが、CMake コメント上は ctest に登録しない構成です。
- `run()` の `fmt` が `1`（int8 KV）。SYCL の `main()` は `run(1, ...)` を呼びます。FP16 / Q4_0 の実行では出ません。
- 参照計算のループが先頭の `i == 0`、`h == 0`、`d == 0` に到達すること。たとえば query 数 `nq` が 0 以下なら `i` ループがなく出力されません。

CLI の context / query 数 / repetition 引数は `main()` で別に読み取られます。`PARITY_DUMP2` と CLI の優先順位はなく、CLI はこの環境変数を上書きしません。既定引数はそれぞれ `32768`, `2048`, `5` です。

## 実行時の詳細

条件成立時、`c=0..3` と `n=0..5` の組み合わせごとに、選択 cell の int8 key と query の内積から計算した参照 score、および `nw[c * 16 + n]` を `printf` で出します。各行の形式は `S c%d n%d ref %.5f new %.5f` です。従って、このブロックに到達した `run(fmt=1, ...)` 1 回につき 24 行が追加されます。判定箇所は `i/h/d` のループ内ですが、条件が真になるのはこの先頭成分だけです。

SYCL の `main()` は通常の引数で int8 の run を 1 回行い、さらに context 1500 と 2100 の int8 run を行います。各 run の query 数が正で先頭成分に到達すれば、それぞれで同じ追加出力が出ます。最後に `FAILURES: %d` を表示し、parity 判定失敗数を終了コードとして返します。`PARITY_DUMP2` 自体は合否判定や終了コードを変えません。

## 根拠

- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:318-324` — 設定有無の判定、fmt/i/h/d 条件、追加計算と出力。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:386-418` — CLI の既定値、int8 run の呼び出し、最後の失敗数と終了コード。
- `sycl/CMakeLists.txt:404-408` — SYCL parity 実行ファイルを構築し、ctest 登録はしない旨。
- `CMakeLists.txt:522-527` — CUDA 版の同名 parity 実行ファイルは別ソース `src/kernels/qsa_prompt_attn_parity.cpp` から構築される。調査した commit で `PARITY_DUMP2` の読み取りは SYCL ソースの 1 箇所のみ。
