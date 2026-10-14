# `STRATA_NO_IQ512`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

ネイティブ expert の CPU gate/up 行で使う Strata の AVX-512 i-quant カーネルを選択対象から外します。AVX-512 対応 CPU では、対象形式に AVX2 カーネルもあり、`STRATA_NO_IQ256` が未設定なら、複数 token 用の計算は AVX2 カーネルへ切り替わります。AVX2 も無効なら ggml-cpu の `vec_dot` に進みます。

この判定は `native_gu_rows()` にだけあり、native expert の gate/up 行に適用されます。down 行の dispatch と、canonical Q2_0 pack の専用 `q2_rows_any()` 経路はこの変数を参照しません。

## 値と判定

値の内容は parse せず、`std::getenv()` が `nullptr` かどうかだけを確認します。

| 環境変数の状態 | AVX-512 i-quant カーネル |
|---|---|
| 未設定 | CPU が AVX-512 対応なら選択可能 |
| 空文字を含む、何らかの値を設定 | 選択対象外 |

`1`、`0`、`false` などの文字列の違いはありません。設定の有無だけが判定されます。AVX-512 非対応 CPU ではもともと同カーネルを選ばないため、この変数を設定しても dispatch は変わりません。

## 有効になる条件

- native expert の CPU gate/up 行が `native_gu_rows()` に到達すること。ExpertPool の native レイヤー処理がこの関数を呼びます。
- CPU が Strata の `cpu_avx512_ok()` 判定を通ること。AVX-512 の実行可否に加えて `STRATA_FORCE_AVX2` やビルドの ISA 上限も影響します。
- `nt >= native_gu_mt_min()` であること。既定の閾値は2 token です。`STRATA_IQ_MT_MIN` などによって閾値が変わる経路があります。閾値未満ではこの i-quant AVX-512/AVX2 grouped dispatch に入らず、ggml-cpu の dot に進みます。
- gate/up の型が該当カーネルでサポートされること。AVX-512 と AVX2 の両方が対応する型は `native_expert.cpp` の type ID 16、17、18、21、22 です。

本変数が設定されて AVX-512 経路が無効になったとき、AVX2 経路は別変数 `STRATA_NO_IQ256` が未設定で、型が AVX2 対応である場合に限って使用されます。AVX2 も無効なら、その行は ggml-cpu の `vec_dot` で処理されます。AVX-512 CPU では AVX2 専用型 IQ4_XS は従来どおりこの multi-token AVX2 分岐の条件を満たさず、ggml-cpu に進みます。

## 実行時の詳細

`native_gu_rows()` 内の `static const bool avx512` 初回評価時に環境変数を読み、結果をプロセス内で保持します。初回評価後にプロセス環境を書き換えても反映されません。未設定で AVX-512 対応なら AVX-512 実装を優先します。変数を設定すると、その優先経路を外し、AVX2 対応型では有効な AVX2 実装へ進みます。どちらも条件を満たさない場合は行ごと、token ごとに ggml-cpu の `vec_dot` を呼びます。

この変数専用のログ出力は確認できませんでした。`docs/DETAILS.md` に本変数の個別説明や測定値は見つかりませんでした。実装コメントは AVX-512 を外すと AVX2 カーネルへ進むことを説明していますが、切り替え時の性能や数値結果の同一性を示す測定条件は同資料にありません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:40-46` — AVX-512/AVX2 カーネルが対応する型。
- `src/kernels/cpu/native_expert.cpp:124-140,143-190` — multi-token 閾値、環境変数の存在判定、AVX-512/AVX2/ggml-cpu の dispatch。
- `src/kernels/cpu/native_expert.cpp:218-229` — fallback の ggml-cpu `vec_dot` 処理。
- `src/kernels/cpu/pool.cpp:685-718` — ExpertPool の native gate/up 行から `native_gu_rows()` への呼び出し。Q2_0 gate/up は別の `q2_rows_any()` 分岐。
- `src/kernels/cpu/expert_layout.cpp:41-45` — CPU の AVX-512 判定が ISA 上限と `STRATA_FORCE_AVX2` を考慮すること。
