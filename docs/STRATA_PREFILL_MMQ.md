# `STRATA_PREFILL_MMQ`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの内部動作は対象外。

## 役割

この名前は二つの用途に使われる。CMake の `STRATA_PREFILL_MMQ` オプションは HIP build に GGML MMQ prompt prefill 経路を組み込むビルド設定で、実行時環境変数も同じ名前で、組み込み済みの MMQ 経路を prompt prefill で使うかを切り替える。実行時に有効なら、対応する expert layer は expert weight を MMQ 用に gather し、activation を量子化して gate/up と down の MMQ 積を実行する。無効ならその layer は既存の FP16 dequantize 経路を使う。

## 値と判定

実行時の判定は `std::atoi(env) != 0` であり、文字列全体の厳密な boolean parse ではない。

| 環境変数の状態・値 | 実行時の判定 |
|---|---|
| 未設定 | MMQ が build に含まれていれば有効 |
| `0`、`00`、`-0`、数値に変換できない文字列、空文字 | 無効（`atoi` が 0 を返す） |
| 先頭の空白や符号の後の整数が 0 以外 | 有効。例: `1`, `-1`, `2abc`, ` 1` |
| 整数変換後に文字が続く値 | 後続文字は無視。例: `0abc` は無効、`1abc` は有効 |

未設定時の ON は `mmq::built()` が true の場合に限る。環境変数を設定しただけでは未 build の MMQ 実装を有効にできない。CMake オプションは別の評価段階であり、既定 OFF。ルート `CMakeLists.txt` では `STRATA_PREFILL_MMQ=ON` は `STRATA_ENABLE_HIP=ON` を要求し、`STRATA_NATIVE_EXPERTS=ON` も要求する。CUDA 構成では MMQ の基礎ターゲットが別途組み込まれ、このオプションは HIP のためのビルド選択として宣言されている。

## 有効になる条件

- MMQ が組み込まれている必要がある。未組み込み build では stub の `mmq::built()` が false を返し、環境変数に非ゼロ値を設定しても `on` は false。
- 対象モデルの expert layout に layer があり、各 layer の gate/up と down の format・形状が `mmq::fits()` を満たす場合に、その layer の `use_mmq` が true になる。MMQ が対応しない layer は FP16 経路へ fallback する。native expert format の一部は fused 経路の対象になり得るが、MMQ 自体が無効でも同じ条件で動くとは限らない。
- CMake の HIP 用オプションは `STRATA_ENABLE_HIP=ON` および `STRATA_NATIVE_EXPERTS=ON` が必要。GGML MMQ のソースが選択した checkout にない場合は configure 時に fatal error となる。
- SYCL 版 `sycl/src/prefill/prefill.cpp` にも同名の `getenv()` 判定がある。ただしリポジトリの `sycl/CMakeLists.txt` は prefill の SYCL ソースを追加するだけで `STRATA_PREFILL_MMQ` を定義せず、MMQ ソースも build しない。その通常の SYCL build では stub により `mmq::built()` が false であり、環境変数だけでは有効にならない。

## 実行時の詳細

CUDA/HIP 共通の prefill 実装と SYCL 移植実装は、`mmq_plan()` 内の関数ローカル `static const MmqPlan` 初期化時に値を一度読み、結果を cache する。従ってプロセス起動後に環境変数を書き換えても再判定されない。値は plan の layer ごとの MMQ 選択、MMQ buffer の確保量、fallback 状態を決める。実際の layer 処理では `use_mmq` に従って、入力 activation の量子化、expert weight の MMQ buffer への gather、group ごとの gate/up MMQ・SwiGLU・down MMQ、または FP16 側の処理を選ぶ。

MMQ の対応範囲は build 時に含めた GGML MMQ kernel instance と format に依存する。CMake では `STRATA_MMQ_KQUANTS` などの別 build option が追加 format を compile する。これらは実行時 `STRATA_PREFILL_MMQ` の値とは別の条件である。Strata の `docs/DETAILS.md` は prompt prefill 全体の高速化を説明し、RTX 5070 12 GB の 32K prompt などの測定値を記載しているが、その測定は MMQ 環境変数だけを切り替えた比較ではないため、ここでは環境変数単独の効果として引用しない。

## 根拠

- `CMakeLists.txt:71-86,1214-1216` — CMake option の既定値と HIP/native expert の前提。
- `CMakeLists.txt:1353-1398,1418-1462` — CUDA/HIP の MMQ library の構築と compile definition。HIP 側の必要 GGML source の検査は `1426-1429`。
- `src/prefill/prefill.cpp:60-78,992-1018` — MMQ 未組み込み時の stub、実行時 parse、static plan、layer format/shape 判定。
- `src/prefill/prefill.cpp:1277-1286,2978-2987,3372-3397,3782-3828` — buffer 確保、per-layer 経路選択、MMQ 処理と FP16 fallback。
- `sycl/src/prefill/prefill.cpp:56-74,861-887` — SYCL 実装にもある stub と同じ実行時判定。
- `sycl/CMakeLists.txt:232-239` — 同梱 SYCL prefill target の構成。
- `docs/DETAILS.md:317-327` — prompt prefill 全体の処理説明と、複数変更を含む測定への案内。
