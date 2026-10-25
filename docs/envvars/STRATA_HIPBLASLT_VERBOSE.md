# `STRATA_HIPBLASLT_VERBOSE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP の prefill GEMM で hipBLASLt の tuning table を使う経路における診断ログを増やす。解決した solution、tuning table に該当 shape がない場合などの fallback 理由、GEMM state の破棄時の launch/fallback 集計を `stderr` に出す。環境変数自体はアルゴリズム選択や GEMM の結果を切り替えない。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効（`getenv` が `nullptr`） |
| 空文字を含む、何らかの値が設定済み | 有効（`getenv` が非 `nullptr`） |

値を数値や文字列として parse せず、値の内容、大文字小文字、`0`/`1` の違いを見ない。したがって `STRATA_HIPBLASLT_VERBOSE=0` や空文字も有効になる。無効値や範囲、clamp はない。

## 有効になる条件

- HIP コンパイルであり、ビルド時に hipBLASLt が見つかって `STRATA_HIPBLASLT_AVAILABLE` が定義されていること。CMake は `STRATA_ENABLE_HIP` と `STRATA_HIPBLASLT_AVAILABLE` の両方が真の場合に、この定義と hipBLASLt のリンクを追加する。
- GEMM 初期化時に `STRATA_HIPBLASLT_TUNING` が空でないパスとして設定され、対応する tuning table の読み込みまで成功すると、hipBLASLt state が作られて通常の解決・実行ログが出る。パスが未設定または空なら state 作成関数は直ちに `nullptr` を返し、この変数によるログはない。handle・device・version の取得や table 読み込みに失敗した場合も hipBLASLt による GEMM は使われず hipBLASEx に fallback するが、作成途中の state が破棄されるため verbose summary は出る場合がある。
- CUDA のみのビルドでは HIP/hipBLASLt 用コードの条件を満たさず、この変数は Strata の GEMM 実装に影響しない。

## 実行時の詳細

環境変数は共通のキャッシュ helper を通さず、各出力箇所で `std::getenv` により直接確認される。GEMM 実行中は、shape・dtype・beta ごとの algorithm cache に未登録の呼び出しで tuning table の行を解決する際に、fallback 理由または solution id、dtype、shape、workspace を出力する。解決結果が cache 済みなら `resolve_hipblaslt_algo` は早期 return するため、その呼び出しではこの verbose 判定も行わず、同じ内容のログは繰り返さない。workspace 不足で `try_hipblaslt` が fallback する箇所は別途環境変数を再確認して理由を出す。

出力例の形式は以下の通り（値は実行時の shape 等に依存する）。

- `prefill gemm: Lt fallback; no calibration for dtype=... T=... N=... K=... ldy=...`
- `prefill gemm: Lt fallback; solution ... unavailable ...`
- `prefill gemm: Lt solution=... dtype=... T=... N=... K=... ldy=... beta=... workspace=...`
- state 破棄時の `prefill gemm: hipBLASLt summary launches=... fallbacks=... unique_fallback_shapes=...` と、fallback shape ごとの行

state 破棄時の summary 判定でも環境変数を再度読む。したがって起動後に環境を変更した場合、以降の cache miss、workspace fallback、state 破棄時の判定には変更が見える一方、既に解決済みの cache hit では解決ログは出ない。呼び出し頻度やログ文言は、tuning table、実際の shape、algorithm のサポート状況、workspace 量に依存する。hipBLASLt の launch 自体が失敗した場合の status ログと、非ゼロ beta 時に fallback を拒否して終了するログは、この変数の有無にかかわらず出る。

`docs/AMD_HIP.md` も hipBLASLt テーブルの smoke test を `STRATA_HIPBLASLT_VERBOSE=1` 付きで実行し、summary の `fallbacks=0` を確認する手順を案内している。これはログの利用例であり、すべての table・GPU・shape で fallback がゼロになる保証ではない。

## 根拠

- `CMakeLists.txt:586-595` — prefill GEMM のビルド対象、および HIP と hipBLASLt が有効な場合の定義・リンク。
- `src/prefill/gemm.cu:141-151` — state 破棄時に設定有無を調べて summary と fallback shape を stderr に出す。
- `src/prefill/gemm.cu:186-220` — tuning path が空の場合の早期 return、state 作成、table 読み込みと失敗時の hipBLASEx fallback。
- `src/prefill/gemm.cu:223-282` — cache hit 時の早期 return、環境変数の設定有無判定、解決時の fallback/solution ログ。
- `src/prefill/gemm.cu:296-345` — workspace 不足時の verbose ログと fallback 集計。hipBLASLt launch 失敗時の status と非ゼロ beta 時の終了ログは無条件。
- `src/prefill/gemm.cu:394-413`, `430-450` — 通常・外部 workspace の GEMM 初期化から state 作成への接続。
- `src/prefill/gemm.cu:600-607`, `693-700` — BF16/F16 GEMM から hipBLASLt 試行へ進み、使えない場合に既存経路へ戻る呼び出し。
- `docs/AMD_HIP.md:572-577` — verbose summary の `fallbacks=0` を見る smoke test の案内。
