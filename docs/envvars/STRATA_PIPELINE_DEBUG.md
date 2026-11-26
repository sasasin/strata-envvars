# `STRATA_PIPELINE_DEBUG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数自体がパイプラインを有効化するのではなく、パイプライン用のテスト・調整・診断変数を `pipe_dbg_env()` 経由で読むかどうかを決めるゲートである。CUDA/HIP 共通側と SYCL 側に同じ判定のヘルパーがあり、ゲートが無効なら引数で渡された環境変数名について `nullptr` を返すため、呼び出し元はそれぞれの既定値を使う。実際の読み取りは `engine/src/program/generate.cpp:684-687`、`engine/sycl/src/program/generate.cpp:337-340`。

このゲートの対象には `STRATA_PIPELINE_THETA`、`STRATA_PIPELINE_FORCE_MISS`、`STRATA_PIPELINE_SWITCH`、`STRATA_PIPELINE_LOG`、`STRATA_PIPELINE_TRACE`、`STRATA_PIPELINE_DOOM_SKIP`、`STRATA_PIPELINE_LOOKUP_PON`、`STRATA_PIPELINE_PRESTAGE`、`STRATA_PIPELINE_AGREE`、`STRATA_PIPELINE_SNAP_OVERLAP` がある。CUDA/HIP 側ではさらに `STRATA_PIPELINE_SPEC_DEPTH` を読む。各参照は同ヘルパーの呼び出しとして `engine/src/program/generate.cpp:13727,20264,20281,20284,21872,21931,21947,22070,22121,22125,22325`、`engine/sycl/src/program/generate.cpp:8009,11156,11160,11163,11817,11904,11920,12078,12125,12129` にある。

パイプラインの実行自体は別の条件で決まる。CUDA/HIP 側では `--pipeline-windows` の値、serve モード、複数 GPU の stage などを確認しており（`engine/src/program/generate.cpp:6584-6605,13267`）、SYCL 側も `--pipeline-windows` と serve・複数 GPU の条件を検査する（`engine/sycl/src/program/generate.cpp:3620-3630`）。したがって、この変数を有効にしても非対応構成でパイプラインが開始されるわけではない。

## 値と判定

両実装とも、`pipe_dbg_env()` が最初に呼ばれた時に `std::getenv("STRATA_PIPELINE_DEBUG")` を一度だけ評価し、値が存在し、空文字でなく、先頭文字が `'0'` でなければ有効とする。文字列全体の比較や数値変換は行わない（`engine/src/program/generate.cpp:684-687`、`engine/sycl/src/program/generate.cpp:337-340`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP・SYCL の `pipe_dbg_env()` | 無効 | `1`、`true`、`false`、` 0`、`01` | 空文字、`0`、`0anything` |

空白除去、大文字小文字変換、真偽値や数値としての妥当性検査はない。`false` は先頭が `0` ではないため有効、`01` は先頭が `0` のため無効となる。ゲート有効時に限り、ヘルパーは指定名の `getenv` 結果を返す。空文字の下流での扱いは変数ごとに異なる。例えば `STRATA_PIPELINE_LOG` は設定有無を見るため空文字でもログを有効にし、`STRATA_PIPELINE_TRACE` は空文字のパスを受け取る（`engine/src/program/generate.cpp:21872,21931,22567-22572`）。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が上記の判定で有効であり、かつ `pipe_dbg_env()` を通る設定値を使うコード経路に到達すること。実際に `pipe_dbg_env()` を使う呼び出しはパイプライン decode の処理内にある。
- パイプライン decode に入る条件は別途満たす必要がある。CUDA/HIP 側では `o.pipeline_windows > 0`、2 stage 以上、同一 GPU 分割でないことなどから `pipe` を決める（`engine/src/program/generate.cpp:13263-13267`）。自動設定時は serve、multi-GPU、stage 数、draft 等の追加条件も検査される（`engine/src/program/generate.cpp:6560-6582`）。SYCL 側の自動設定は serve、multi-GPU、Battlemage 世代、MTP などを `PipelineAutoInputs` に渡して判定する（`engine/sycl/src/program/generate.cpp:3594-3618`）。
- この変数は `--pipeline-windows` や自動設定を上書きしない。例えば CUDA/HIP 側の `STRATA_PIPELINE_AUTO` と `STRATA_PIPELINE_AUTO_MIN_STAGES` は直接 `getenv` され（`engine/src/program/generate.cpp:6560-6567`）、SYCL 側の `STRATA_PIPELINE_AUTO` も直接読み取られる（`engine/sycl/src/program/generate.cpp:3594-3607`）。
- `STRATA_PIPELINE_ADAPT_ASYNC`、`STRATA_PIPELINE_HIT_MIN`、`STRATA_PIPELINE_LAZY_CHAIN`、`STRATA_PIPELINE_LOOKUP_RUN`、`STRATA_PIPELINE_DUMP` も直接 `getenv` され、`pipe_dbg_env()` によるゲートを通らない（`engine/src/program/generate.cpp:11798-11809,20259-20278,22567-22572`、`engine/sycl/src/program/generate.cpp:12818-12823`）。したがって `STRATA_PIPELINE_DEBUG` は、名前が `STRATA_PIPELINE_*` のすべての変数を一律に無効化するものではない。

## 実行時の詳細

`static const bool on` は各 `pipe_dbg_env()` 関数内で初回呼び出し時に初期化される。従って `STRATA_PIPELINE_DEBUG` は起動直後に一律読み取られるのではなく、そのプロセスで最初にヘルパーが呼ばれた時点の値がキャッシュされる。その後のプロセス内での環境変更はゲート判定に反映されない。ヘルパーが有効と判定された後、要求された変数自体は呼び出しごとに `getenv(name)` で取得されるが、呼び出し側で `static` に保存する値はその呼び出し側の初回評価時の値となる（例: `STRATA_PIPELINE_LOG` と `STRATA_PIPELINE_TRACE`、`engine/src/program/generate.cpp:21872,21931`）。

ゲートが無効なら、ヘルパー経由の変数は未設定と同じ扱いになる。例えば `STRATA_PIPELINE_THETA` が無効なら CUDA/HIP 側は `STRATA_PIPELINE_HIT_MIN` の状態に応じた既定値または `0.2` を使い、SYCL 側は `0.2` を使う（`engine/src/program/generate.cpp:20259-20266`、`engine/sycl/src/program/generate.cpp:11155-11158`）。`STRATA_PIPELINE_FORCE_MISS` は既定で `0` となり、`STRATA_PIPELINE_PRESTAGE` と `STRATA_PIPELINE_AGREE` は既定で有効、`STRATA_PIPELINE_LOOKUP_PON` は既定 `0.75` となる（`engine/src/program/generate.cpp:20280-20282,22070-22072,22120-22126`、`engine/sycl/src/program/generate.cpp:11159-11161,12077-12080,12124-12130`）。

## ログと測定値

`STRATA_PIPELINE_DEBUG` 自体を有効化したことを示すログはない。ゲート有効時に `STRATA_PIPELINE_LOG` が設定されていれば、標準エラーに `strata pipeline: chain ...` や `strata pipeline: verdict ...` の行を出す（CUDA/HIP: `engine/src/program/generate.cpp:21872,22302-22304,22455-22461`、SYCL: `engine/sycl/src/program/generate.cpp:11817,12321-12323,12430-12432`）。`STRATA_PIPELINE_TRACE` が設定されていれば、イベント行を指定パスに追記する。書き込みに失敗しても、この箇所からはエラーを報告しない（CUDA/HIP: `engine/src/program/generate.cpp:21930-21939,22567-22572`、SYCL: `engine/sycl/src/program/generate.cpp:11903-11912,12533-12538`）。この環境変数自体について記載できる測定値はない。

## 根拠

- `engine/src/program/generate.cpp:684-687` — CUDA/HIP 側の環境値判定と helper 経由の読み取り。
- `engine/sycl/src/program/generate.cpp:337-340` — SYCL 側の同じ判定。
- `engine/src/program/generate.cpp:13263-13267` — パイプライン処理へ入る条件。
- `engine/src/program/generate.cpp:21872-21947,22302-22304,22455-22461,22567-22572`、`engine/sycl/src/program/generate.cpp:11817-11920,12321-12323,12430-12432,12533-12538` — ゲート対象のログ・trace 等。
