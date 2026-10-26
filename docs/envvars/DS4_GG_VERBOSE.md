# `DS4_GG_VERBOSE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4.1 の CPU expert lane が、Strata の AVX row 実装と ggml-cpu の `vec_dot` の結果を照合したとき、不一致があれば stderr に診断行を出します。この環境変数は計算方法や fallback を切り替えず、その不一致行を表示するかどうかだけに使われます。

## 値と判定

値の内容は parse せず、`std::getenv("DS4_GG_VERBOSE")` が null でないかだけを判定します。

| 状態 | この変数による診断行 |
|---|---|
| 未設定 | 有効化しない |
| 空文字を含む任意の設定値（`0`、`false` なども含む） | 有効化する |

ただし、別の診断変数 `DS4_DBG_GG` が設定されていれば、この変数が未設定でも同じ不一致行が出ます。`DS4_DBG_GG` はこの不一致通知以外にも ggml CPU lane の処理ログを出します。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で作られる `strata-dsv41` の実行経路であること。
- `STRATA_NATIVE_EXPERTS=ON` で CPU lane がコンパイルされていること。この設定が無効なら `ds4_gg_cpu.cpp` の本体はコンパイルされず、スタブ実装になります。
- 対象 GGUF block type が CPU lane に割り当てられ、AVX2/AVX-512 row 実装を選ぶための `own_ok()` 検査まで到達すること。
- その検査で、検査用の各 token 数・row の結果が ggml-cpu の結果と `memcmp` で一致しないこと。

値が設定されていても、AVX row 検査を実行しない型・経路や、一致した場合には `DS4_GG_VERBOSE` による出力はありません。不一致時には accelerated row を採用せず、呼び出し元の選択処理が ggml-cpu の dot に戻ります。

## 実行時の詳細

`gg_cpu_gate_up()` / `gg_cpu_down()` から `dots()` が呼ばれ、`use_iq256()` が AVX row 実装を選ぶと `own_ok(type, impl)` で CPU 上の照合を行います。照合は impl と型ごとの `std::call_once` で一度だけ実行されます。不一致なら `own_ok()` は false を返し、その型・実装の row kernel を使わないようにします。その照合中に環境変数または `DS4_DBG_GG` が設定されている場合、次の行を stderr に出します。

```text
ds4: CPU lane type %d: AVX2 rows differ from ggml-cpu's dot at %d tokens, not used
```

この `fprintf` は `DS4_GG_VERBOSE` 自体を static cache せず、不一致検査が実行される時点で設定有無を読みます。一方、各 impl・型の検査は `call_once` のため、その組み合わせでは出力機会も一度です。環境変数を後から変更しても、すでに完了した検査は再実行されません。

なお、実装は AVX-512 row の検査にも同じ固定文言 `AVX2 rows` を使っています。これはログ文字列の内容であり、当該 impl の実際の kernel が AVX-512 の場合にも表示されます。

## 根拠

- `CMakeLists.txt:797-811,833-839` — DS4.1 executable は `STRATA_BUILD_DSV41` の下で定義され、`ds4_gg_cpu.cpp` を含む。`STRATA_NATIVE_EXPERTS` が有効な場合に CPU lane 定義を付ける。
- `src/dsv41/ds4_gg_cpu.cpp:12-17,27-33,99-148` — CPU lane の compile guard、照合、`std::call_once`、不一致時の環境変数判定と診断出力。
- `src/dsv41/ds4_gg_cpu.cpp:179-214,217-232` — AVX row 実装の選択、および照合失敗後に ggml-cpu dot へ進む処理。
- `src/dsv41/ds4_iq_cpu.cpp:757-779` — CPU lane wrapper が ggml block type の gate/up/down 計算を `gg_cpu_*` に渡す経路。
- `docs/DEEPSEEK41.md:133-134` — DS4.1 CPU lane のビルド条件として `STRATA_NATIVE_EXPERTS=ON` を説明。ここに `DS4_GG_VERBOSE` の記載はない。
