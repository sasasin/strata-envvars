# `STRATA_CPUEXP_KERNEL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

ハイブリッド配置でホスト RAM に置いた expert を計算する `hy4::CpuExperts` の GEMM カーネルを、CPUID による自動選択ではなく明示的に固定する。読み取り元は `engine/src/hy4flash/run/hy4_cpu_experts.cpp` の `CpuExperts::Impl::load()` だけで、結果は `Impl::kern` に保存される（`hy4_cpu_experts.cpp:1820-1858`）。

`kern == 0` はライブラリの `strata::quant::sk::gemm_sk_q8_1`、1 は AVX2、2 は AVX-512、4 は AVX2-VNNI、3 は NEON dotprod（`hy4_cpu_experts.cpp:1125-1127`）。`kern != 0` が `fast` になり、以降の expert 計算は `kern_gemm_dispatch` 経由に変わる（`:1857`, `:2311-2312`, `:2395`）。MoE のルーティング、expert 選択、Q8_1 活性化と S_K 重みの積和という計算内容そのものは変わらない。

## 値と判定

`std::getenv` の戻り値を `std::strcmp` で完全一致比較する。数値変換・先頭文字比較・空白除去・大文字小文字の正規化はない（`:1826-1837`, `:1845-1853`）。空文字は「設定あり」だがどの文字列にも一致しないため無効値として警告される。

| 条件（build / CPU） | 有効な値 | 既知でも実機が不支持なら | 無効な値 |
|---|---|---|---|
| x86-64 かつ `HY4_NO_FAST` 未定義（`HY4_KERNELS`） | `lib`（無条件）, `avx2`, `avx2-vnni` / `avxvnni`, `avx512` | `avx2` / `avx512` / `avx2-vnni` はカーネルを替えず自動選択値へ戻る | それ以外すべて（`0`, `1`, `true`, `AVX512`, 空文字など） |
| aarch64 かつ `HY4_NO_FAST` 未定義（`HY4_NEON_KERNELS`） | `lib`, `neon` | `neon` は dotprod 非対応なら自動選択値へ戻る | 上記以外すべて（`avx512` など） |
| それ以外、または `HY4_NO_FAST` 定義時 | 該当なし（`getenv` 自体が呼ばれない） | — | すべて無視。ログも出ない |

x86 の受理判定は `want == 0` が無条件、`want == 1` は `kcaps.avx2`、`want == 4` は `kcaps.avx_vnni`、`want == 2` は `kcaps.avx512` を要求する（`:1834`）。`kcaps` は CPUID + XGETBV の結果に `STRATA_FORCE_ISA` の cap を適用したもの（`:1154-1185`）。`avx2-vnni` の検出はビルド時 `HY4_AVX_VNNI` が 1 のときだけ行われる（`:79-83`, `:1171-1175`）。

未設定・無効値・不支持のときの既定は CPUID による優先順位 `avx512 > avx2-vnni > avx2 > lib`（`:1824`, `:1843`）。この変数に対応する CLI 引数や設定ファイル項目はない。

## 有効になる条件

- `strata-hy4` の起動時、tier-2 expert（ホスト RAM 常駐）または cold expert が 1 つ以上あるときだけ `cpu.init()` が呼ばれる（`hy4_graph.hip.h:1552, 1565`; `hy4_gpu_model.hip.h:1227`）。CPU tier を使わない起動では読まれず、警告も効果も出ない。
- fast カーネルが組み込まれたバイナリであること。`hy4_cpu_experts.cpp` は `-mavx2 -mfma -mf16c` / `/arch:AVX2` でコンパイルされる（`run/CMakeLists.txt:38-45`）。`HY4_NO_FAST` を定義する build はリポジトリの CMake 設定に存在しない。
- `STRATA_FORCE_ISA` が先に cap として効く。`avx`/`sse` で `kcaps` がすべて false になり、`avx512` を要求しても自動選択（この場合は `lib`）へ戻る（`:1180-1184`）。
- `avx2-vnni` を選ぶには `HY4_AVX_VNNI` が 1（clang ≥ 12 / GCC ≥ 11 / MSVC ≥ 1930）でコンパイルされている必要がある（`:79-83`）。
- fast カーネルが扱う SkCode は `0, 2, 3, 4, 5, 6, 8` のみ。`S1_5`(1), `SF4`(15), `MX8`(16), `GGUF_RAW`(20) の行列は fast 選択時でも per-call でライブラリへ fallback する（`:1129`, `:1264-1282`）。したがって `avx512` 指定でも全 expert が AVX-512 経路になるわけではない。

## 実行時の詳細

読み取りは `CpuExperts::Impl::load()` の後半、expert 本体のロードと THP 処理の後・ワーカースレッド起動の前の 1 回だけ（`:1819-1866`）。`static` cache はなく、`init()` を呼び直せば再読込される。プロセス起動後に環境変数を変えても、実行中のジョブや再 init をしない限り反映されない。子プロセスへの転送やサーバー側からの設定はない（`strata-hy4` が自分で設定する CPUEXP 系は `STRATA_CPUEXP_COLD_IO` のみ: `hy4_main.hip.cpp:465`）。

`kern` の効果は次の 4 点。

1. GEMM 本体が fast カーネルか `gemm_sk_q8_1` か（`:2311-2312`, `:2395`）。
2. トークンタイルが 32（`MGF`）か 16（`MG`）か（`:131-132`, `:2301`）。
3. 活性化の保持形式が `ActRow` か `BlockQ8_1_G64` 配列か、z/h2 の量子化経路（`:2595-2612`）。
4. SwiGLU に AVX2 実装を使うか。`kern == 1 || 2 || 4` のときだけで、`kern == 3` と `lib` はスカラー実装（`:2344`）。

`kern` は活性化精度の既定にも影響する。`load()` 末尾で `hi = (kern == 1)`、`STRATA_CPUEXP_ACT` 未設定なら AVX2 を選んだときだけ 2 項 Q8_1（hi）が既定になる（`:1857-1862`）。ただし `strata-hy4` は `init()` 直後に `STRATA_CPUEXP_ACT` 未設定なら `set_hi_activations(true)` を呼ぶため、この起動経路では `hi` は常に true になる（`hy4_graph.hip.h:1579`; `hy4_cpu_experts.cpp:3165-3168`）。fast と lib は同じ積和でも加算順とタイルが異なり、コード自身は `selftest_kernels` で 2e-6 の許容比較を行っている（`:3046`）。

## ログと測定値

読み取り時の stderr 出力（すべて `[cpuexp]` 接頭辞）。

- 未知の値: `[cpuexp] STRATA_CPUEXP_KERNEL=%s is not avx512, avx2-vnni, avx2 or lib; ignored`（`:1832`）。aarch64 では `... is not neon or lib; ignored`（`:1849`）。
- 値は既知だが実機/OS 不支持: `[cpuexp] STRATA_CPUEXP_KERNEL=%s is not supported by this CPU/OS; using %s`（`:1836`, `:1852`）。末尾の `%s` は自動選択されたカーネル名。
- 受理された場合は警告なし。ロード完了時に選択結果が `[cpuexp] ... kernel=%s, act=%s` として必ず 1 行出る（`:1863-1865`）。`kernel=` は `lib` / `fast(avx2)` / `fast(avx512-vbmi)` / `fast(avx2-vnni)` / `fast(neon-dotprod)`（`:1125-1126`）、`act=` は `hi(2xQ8_1)` か `q8`。
- `HY4_NO_FAST` build や CPU tier なしの起動では、どの文言も出ない。

`docs/` にこの変数の性能値や条件付き測定値の記載はない（`rg CPUEXP docs/` は 0 件）。カーネル間の速度差は本調査では断定しない。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:60`（値の一覧コメント）, `:1820-1838`（x86 の読み取りと判定）, `:1840-1856`（aarch64 の読み取りと判定）
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1125-1127`（`kern_name`）, `:1154-1186`（CPUID と `STRATA_FORCE_ISA` の cap）
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1857-1866`（`fast`/`hi` の決定とログ）, `:2301-2312`, `:2344`, `:2395`, `:2595-2612`（実行経路）
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`（`cpu.init` の条件と `set_hi_activations`）
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1227-1235`（tier-2 / cold mask）
- `engine/src/hy4flash/run/CMakeLists.txt:38-45`（コンパイルオプション）
- `engine/src/hy4flash/run/hy4_cpu_experts.h:98-102`（ヘッダの説明。S2..S6 限定という記述は現行コードと一致せず、`avx2-vnni` と `neon` も列挙されていない）
