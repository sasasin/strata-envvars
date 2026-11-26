# `STRATA_Q2_BITPLANE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native Q2_0 GGUF 行計算で、AVX2 または AVX1 の通常カーネルの代わりに bit-plane カーネルを選ぶ開発・最適化用スイッチです。AVX2 では activation quantizer が bit-plane 用画像を作り、行カーネルがそれを使います。AVX1 にも別実装があります。選択されると浮動小数点の加算順序が変わり、Q2_0 行の最下位ビットが変わり得ます。環境変数は行カーネルの算術方式を選び、CLI 引数やモデルの内容そのものは変更しません（`engine/src/kernels/cpu/q2_avx2.cpp:65-85,172-190`, `engine/src/kernels/cpu/q2_avx1.cpp:137-143,252-271`）。

## 値と判定

AVX2 と AVX1 の各翻訳単位で、ファイルスコープの `kBitplane` 初期化時に `std::getenv` し、値が存在して先頭文字が `'1'` の場合だけ true にします。文字列全体や数値としては解析しません。空文字、`0`、`true`、先頭が空白の ` 1` は false、`1`、`10`、`1anything` は true です。大文字小文字や後続文字は判定されません。未設定時は false で、明示的な無効値による警告や fallback はありません（`engine/src/kernels/cpu/q2_avx2.cpp:146-149`, `engine/src/kernels/cpu/q2_avx1.cpp:198-201`）。

| 実装経路 | unset / 空文字 | 有効になる値 | 無効になる例 |
|---|---|---|---|
| AVX2 | false | 先頭文字が `1`（例: `1`, `10`, `1abc`） | `0`, `true`, ` 1` |
| AVX1 | false | 先頭文字が `1`（例: `1`, `10`, `1abc`） | `0`, `true`, ` 1` |
| portable 実装 | bit-plane は無効 | なし | すべて（`q2_bitplane_enabled()` は常に false） |

## 有効になる条件

- 実行バイナリに x86 native-expert の AVX2 / AVX1 実装が含まれ、実行 CPU に対応 ISA が使えること。AVX2 カーネルは AVX2 経路、AVX1 カーネルは AVX があり AVX2 がない経路で選択されます（`engine/src/kernels/cpu/expert_layout.cpp:465-471`; `engine/include/strata/kernels/cpu/expert.hpp:184-203`）。
- `q2_native_kernels(type)` が対象レイヤーを native Q2_0 と判定すること。これは型 `42`（Q2_0）かつ AVX2 または AVX1 が使える場合です。pool は native Q2_0 gate/up または down 行を処理するとき `q2_rows_any` に渡します（`engine/include/strata/kernels/cpu/expert_layout.hpp:89-99`, `engine/src/kernels/cpu/pool.cpp:1278-1302`）。
- AVX2 / AVX1 の行カーネルに入り、`nblocks` が偶数で、対象 activation すべてに bit-plane 画像があること。条件を満たさなければ通常の legacy 行カーネルに戻ります（`engine/src/kernels/cpu/q2_avx2.cpp:172-180`, `engine/src/kernels/cpu/q2_avx1.cpp:252-260`）。画像生成側では `nchunks % 4 != 0` の場合に画像を作らず、`bp_pairs=0` とします（`engine/src/kernels/cpu/q2_avx2.cpp:197-199,229-268`, `engine/src/kernels/cpu/q2_avx1.cpp:205-207,274-311`）。
- AVX-512 Q2_0 行経路が選ばれると、このスイッチは使われません。通常は `q2_rows_512_ok()` が AVX-512/VNNI 経路を選びます。`STRATA_CPU_YMM` が設定されていると AVX-512 側の `kZmm` が false になり、条件を満たせば AVX2 経路に進みます。AVX-512 非対応 CPU で VNNI tier が使われるかは `STRATA_VNNI_TIER=1` など別条件にも依存します（`engine/src/kernels/cpu/expert.cpp:152,378-380`, `engine/src/kernels/cpu/expert_layout.cpp:188-203,465-471`）。
- `STRATA_FORCE_ISA=avx2` / `avx` は ISA dispatch の上限をそれぞれ AVX2 / AVX にし、`STRATA_FORCE_AVX2=1` も AVX-512 経路を無効にします。これらの条件では、CPU が AVX2 対応なら AVX2 経路が選択されます。`STRATA_FORCE_ISA` が未設定または空なら既定 cap は AVX-512 含む通常の自動判定で、認識されない値は警告して既定 cap に戻ります（`engine/src/kernels/cpu/expert_layout.cpp:26-38,75-77`; AVX-512 優先条件は `engine/src/kernels/cpu/expert_layout.cpp:465-471`）。
- ARM の portable 実装では bit-plane kernel を使用せず、`q2_bitplane_enabled()` は false 固定です。CPU backend の portable スタブも native Q2_0 行カーネルを提供せず、実際の行計算はここへ入りません（`engine/src/kernels/cpu/portable.cpp:98-109`; x86 と ARM の実装選択は `engine/CMakeLists.txt:73-82`, `engine/cmake/backends/cpu.cmake:243-257`）。

## 実行時の詳細

値は AVX2 / AVX1 ソース内の静的 bool 初期化で一度読み、後続の quantize / 行計算でキャッシュ値を使います。プロセス実行中に環境を変更しても反映されません。CLI、設定ファイル、別の環境変数がこの値を上書きする読み取り箇所はありません（`engine/src/kernels/cpu/q2_avx2.cpp:146-149,172-190`, `engine/src/kernels/cpu/q2_avx1.cpp:198-201,252-271`）。

AVX2 では `act_quant_q8_1_avx2` が通常の q8 activation を作った後、スイッチが true の場合だけ `bitplane_image` を作ります。AVX1 も同様に `act_quant_q8_1_avx1` から生成します。行カーネルは偶数個の 64 要素 Q2_0 ブロックを 2 ブロック単位の bit-plane 計算へ渡し、条件不一致なら legacy 実装へ戻ります（`engine/src/kernels/cpu/q2_avx2.cpp:197-225,229-268,172-190`, `engine/src/kernels/cpu/q2_avx1.cpp:205-233,274-311,252-271`）。

この経路は GPU backend やサーバーモード固有ではなく、native Q2_0 行処理を行う CPU 経路に属します。portable ビルドでは有効化されません。Strata の `DETAILS.md` は AVX2 かつ AVX-512 なしと記載していますが、現行コードには AVX1 実装もあります。また AVX-512 CPU でも dispatch が AVX2 に落ちれば条件付きで対象になります（`docs/DETAILS.md:1272`, `engine/src/kernels/cpu/q2_avx1.cpp:1-15,252-260`, `engine/src/kernels/cpu/expert_layout.cpp:465-471`）。

## ログと測定値

通常の native Q2_0 実行経路では、このスイッチの有効・無効を報告するログは見つかりません。テスト専用の `q2_bitplane_parity` 実行ファイルは環境変数が有効でない場合に `q2_bitplane_parity: STRATA_Q2_BITPLANE=1 is not set` を stdout に出して終了コード 1 を返し、AVX のない CPU では `q2_bitplane_parity: no AVX on this CPU, skipped` を出して 0 を返します。CMake のテスト登録はこのテストに `STRATA_Q2_BITPLANE=1` を設定します（`engine/src/kernels/cpu/q2_bitplane_parity.cpp:23-29`, `engine/cmake/backends/cpu.cmake:512-518`）。

`expert_layout.hpp` のコメントには i7-3770 の単一 token Q2_0 ベンチとして legacy 0.52 ms、bit-plane 0.42 ms とあります。条件として `kq_cpu_bench --pairs q2_0/q2_0` が記載されていますが、測定回数などは示されていないため、この値はソースコメントにある報告としてのみ扱い、一般的な性能差とはしません（`engine/include/strata/kernels/cpu/expert_layout.hpp:89-93`）。

## 根拠

- 環境変数の値判定・キャッシュ: `engine/src/kernels/cpu/q2_avx2.cpp:146-149`, `engine/src/kernels/cpu/q2_avx1.cpp:198-201`。
- 適用対象と fallback: `engine/src/kernels/cpu/expert_layout.cpp:465-485`, `engine/src/kernels/cpu/q2_avx2.cpp:172-190`, `engine/src/kernels/cpu/q2_avx1.cpp:252-271`。
- bit-plane 画像の生成条件: `engine/src/kernels/cpu/q2_avx2.cpp:197-225,229-268`, `engine/src/kernels/cpu/q2_avx1.cpp:205-233,274-311`。
- AVX-512 dispatch: `engine/src/kernels/cpu/expert.cpp:152,378-380`, `engine/src/kernels/cpu/expert_layout.cpp:188-203,465-471`。
- native Q2_0 の pool 経路: `engine/include/strata/kernels/cpu/expert_layout.hpp:89-99`, `engine/src/kernels/cpu/pool.cpp:1278-1302`。
- portable 実装: `engine/src/kernels/cpu/portable.cpp:98-109`。
- parity 専用テストと出力: `engine/src/kernels/cpu/q2_bitplane_parity.cpp:23-29`, `engine/cmake/backends/cpu.cmake:512-518`。
