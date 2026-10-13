# `STRATA_PREFILL_FIRST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL の prompt prefill で、最初の chunk だけを短くする token 数を指定します。短い初回 chunk の計算中に、次の層で必要になる PLE 行をホスト側で読み込めるようにするための設定です。`src/prefill/prefill.cpp` を含む SYCL prefill 実装で参照されます。CUDA/HIP の通常ビルドは別の `src/prefill/prefill.cpp` を使い、この環境変数の参照はありません（`sycl/CMakeLists.txt:233-236`、`CMakeLists.txt:589`）。

## 値と判定

値は `std::atoll()` で `int64_t` に変換されます。文字列全体の妥当性は検査しないため、先頭の空白と符号付き10進数を読み、数字でない文字に達した後ろは無視します。数字で始まらない文字列や空文字は `0` になります。明示した `0`、負数、または数値として `0` になる値は、短い初回 chunk を無効にします。

| 設定 | `first_chunk` | 効果 |
|---|---:|---|
| unset かつ全 expert が cache 内 | 256 | 条件を満たす長い prompt の初回 chunk を256 tokenにする |
| unset かつ全 expert が cache 内にない | 0 | 短い初回 chunk を使わない |
| 設定あり | `atoll` の変換結果 | 正数の場合、下記の chunk 条件を満たすと指定 token 数を使う |

「全 expert が cache 内」は `m.cache` と `m.g` が存在し、`cache->slots() >= n_layers * n_expert` の場合です。明示設定はこの既定値判定に優先します。値が正でも、初回 chunk の長さ `m.T` 未満であり、prompt 全体の token 数 `n` が `2 * first_chunk` より大きい場合に限り、初回 chunk をその長さにします。それ以外は通常どおり `min(m.T, n-c0)` です。したがって、`first_chunk >= m.T` や短い prompt では指定値による短縮は起きません。

## 有効になる条件

この変数を読む実装は SYCL prefill にあります。初回 chunk 短縮の条件を満たすと、prompt の最初の chunk のみが短くなり、後続 chunk は通常の最大長 `m.T`（末尾は残り token 数）を使います。短縮が無効、または条件を満たさない場合も、prefill 自体は通常の chunking で進みます。

## 実行時の詳細

`Prefill::run_impl()` 内の関数ローカル `static` が、最初にこの経路へ入ったとき `getenv()` の返却ポインタを取得し、以後それを使います。変換後の `first_chunk` と `all_cached` の判定は `run_impl()` の呼び出しごとに行われます（`sycl/src/prefill/prefill.cpp:2101-2107,2188-2200`）。

初回 chunk の埋め込み処理後、PLE 行の gather は非同期 task として開始します。chunk の層ループは layer 1 から使う行を `ple_land()` で待つため、短い初回 chunk ではその読み込みと layer 0 の GPU 処理を重ねられます（`sycl/src/prefill/prefill.cpp:2309-2316,2747`）。この変数専用のログ出力や警告はありません。

## 文書との照合

`docs/INTEL.md:776-783` は、expert が VRAM に収まらない Arc Pro B70 では短い初回 chunk が expert の PCIe 転送を余分に一巡させるため、既定値を「全 expert が cache 内なら256、それ以外は0」と説明しており、現行コードの既定値と一致します。同資料の測定条件は Arc Pro B70、IQ3_S、32 GB card、11.5k experts resident で、4,095-token prompt の `--prefill 4096` の速度は旧方式784 tok/sから980–1,002 tok/sに改善したと記載されています。この比較は prefill chunking の変更を含むため、差を `STRATA_PREFILL_FIRST` 単独の効果とは解釈できません。

同資料 `docs/INTEL.md:291` は、chunk 境界の変更で expert GEMM の丸め位置が変わり、長い greedy continuation が遅れて分岐した例（試験 prompt の64 token中45 token目）を記載しています。これは資料に記録された条件での観測であり、あらゆるモデルや設定で token が異なるという意味ではありません。

## 根拠

- `sycl/src/prefill/prefill.cpp:2188-2200` — 既定値、`atoll` 変換、cache 判定、短縮条件。
- `sycl/src/prefill/prefill.cpp:2309-2316,2747` — PLE gather と layer 1 での待機。
- `sycl/CMakeLists.txt:233-236`、`CMakeLists.txt:589` — SYCL と通常ビルドでの prefill ソース構成。
- `docs/INTEL.md:291,739-743,762-783` — chunk 境界の観測と Arc Pro B70 の測定条件・記録。
