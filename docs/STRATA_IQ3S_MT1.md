# `STRATA_IQ3S_MT1`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

ネイティブ形式の CPU expert 計算で、特定の CPU 上の IQ3_S gate/up 行を1 token のグループでも AVX2 multi-token kernel に通します。既定では1 token の IQ3_S は ggml-cpu の dot product 経路を使い、複数 token のグループは Strata の multi-token kernel を使います。この切り替えは1 token 時の丸めを変えるため、既定では無効です。

この変数が変えるのは `gu_type == 21`（IQ3_S）の gate/up 行の kernel 選択です。down 行や他の量子化形式には直接作用しません。対象のネイティブ expert 実装がビルドに含まれない場合、この環境変数を読む実装もありません。

## 値と判定

実装は値を数値や文字列として parse せず、`std::getenv("STRATA_IQ3S_MT1") != nullptr`、つまり設定の有無だけを判定します。したがって空文字、`0`、`false` を含め、何らかの値が設定されていればこの判定は真です。未設定なら偽です。

ただし、この設定が有効になる判定には `STRATA_IQ_MT_MIN` が未設定であることも必要です。`STRATA_IQ_MT_MIN` が設定されていると値が空文字や無効な数値であっても、この変数による特例は無効です。`STRATA_IQ_MT_MIN` 自体は未設定なら 2、設定時は `atoi` の結果です。

## 有効になる条件

`STRATA_IQ3S_MT1` の有無に加え、以下をすべて満たすと IQ3_S の最小 token 数を 1 にします。

- `STRATA_IQ_MT_MIN` が未設定。
- CPU が AVX2 を実行でき、`STRATA_NO_IQ256` が未設定。
- CPU が AVX-512 対応として検出されない。
- `iq256_gather_setting() != 0` で、`cpu_gather_fast()` が真。後者は `STRATA_FORCE_ISA` の上限、Intel の vendor ID、CPUID の AVX-VNNI、CPU model の除外条件を確認します。

`STRATA_IQ256_GATHER` は未設定または空文字なら自動判定値 `-1`、それ以外は `atoi` により 0 / 非0 に分かれます。ここで `0` と判定されると特例は無効です。値が非0でも、`cpu_gather_fast()` の条件が満たされなければ特例は有効になりません。`STRATA_NO_IQ256` は値ではなく設定有無で判定され、空文字を含め設定されていれば特例を止めます。

`STRATA_IQ_MT_MIN` が設定されている場合は、こちらの特例でなく、その変数の値がすべての IQ gate/up 形式に対して使われます。AVX-512 CPU、AVX2 非対応 CPU、または AVX2 kernel を無効化した構成では、本変数によって1 token の AVX2 IQ3_S kernel が選ばれることはありません。

## 実行時の詳細

判定は `native_gu_mt_min()` 内の関数ローカル `static` に保存されます。初回評価後にプロセス環境を変更しても再評価されません。特例が成立すると、この関数は IQ3_S にだけ `mt_min = 1` を返し、それ以外の形式には `STRATA_IQ_MT_MIN` の既定値または parse 結果を返します。

呼び出し側の `native_gu_rows()` は、グループの token 数 `nt` が `mt_min` 以上で、AVX-512 でない IQ format が対応形式なら、AVX2 kernel を選びます。IQ3_S は AVX2 対応形式なので、条件を満たす環境では `nt == 1` でもこの経路に入ります。対象環境で `nt >= 2` のグループは既定の閾値 2 でも同じ multi-token 経路を使うため、主な差は単独 token のグループです。対象 CPU でこの単独 token の丸めが従来の ggml-cpu 経路と異なり得ます。

この環境変数に対応する専用ログやエラー出力は見つかりませんでした。値を無効とするフォールバックもログなしで通常の閾値判定に戻ります。

## 文書との照合

`docs/DETAILS.md` は `STRATA_IQ3S_MT1=1` を opt-in と説明し、AVX-512 を持たない一部 CPU で IQ3_S の multi-token kernel を1 token にも使うこと、および1 token の丸めが変わることを記載しています。現行ソースの判定は `=1` との完全一致ではなく設定有無です。したがって `=0` や空文字もソース上は opt-in と同じ判定になります。資料は性能の説明をしていますが、この変数の効果量を裏付ける条件付きの測定値は該当箇所に記載されていません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:115-131` — `STRATA_IQ_MT_MIN` の取得と既定値、対象変数の有無判定、CPU / gather 条件、IQ3_S の閾値。
- `src/kernels/cpu/native_expert.cpp:134-185` — `nt >= mt_min` の判定、AVX2 IQ kernel の選択、未選択時の ggml-cpu dot 経路。
- `src/kernels/cpu/expert_layout.cpp:25-38,41-45,106-137,202-230` — ISA 上限、AVX-512 / AVX2 判定、gather 設定の parse と fast CPU 判定。
- `src/kernels/cpu/iq_avx2.cpp:459-460` — gather kernel の設定値と CPU 判定による選択。
- `src/kernels/cpu/expert_layout.cpp:368-376` — `STRATA_NATIVE_EXPERTS` が無効なビルドでは stub が使われ、`native_gu_mt_min()` は常に 2 を返すこと。
- `CMakeLists.txt:1210-1218,1265-1269` — `STRATA_NATIVE_EXPERTS` の設定と、ON の場合にネイティブ CPU expert 実装を追加するビルド経路。
- `docs/DETAILS.md:97-105` — `STRATA_IQ_MT_MIN` と本変数についての説明。
