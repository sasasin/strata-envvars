# `STRATA_VERIFY_STEPPED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

SYCL verifier の window 実行を、GPU queue の境界ごとに分割し、その間に CPU expert pool を処理する stepped 経路を有効にします。実装コメントは Intel Arc A-series / DG2 向けの opt-in と説明していますが、環境変数の判定自体に GPU 世代や OS の検査はありません。CUDA/HIP の `src/core/verify.cpp` にはこの変数の読取箇所がなく、実装は `sycl/src/core/verify.cpp` にあります。

この経路は verifier が動く実行に限られます。`Verifier::init()` は VRAM expert tier の profile/cache や対応するモデル geometry などを要求し、条件不足なら verifier 初期化を失敗させます（`sycl/src/core/verify.cpp:482-506`）。そのため通常の verifier 非使用実行にこの値だけで stepped 処理が追加されるわけではありません。

## 値と判定

`env_on()` は `std::getenv()` の結果が存在し、空文字でなく、先頭文字が `'0'` でない場合に true を返します。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭が `0` の文字列（`0`, `0abc`） | 無効 |
| それ以外（`1`, `true`, `false`, `2`, ` 1` など） | 有効 |

大文字小文字や後続文字は評価されません。したがって文字列 `false` も有効です。CLI 引数による同値の上書きは確認できません。

## 有効になる条件

- この実装が組み込まれた SYCL verifier を実際に使うこと。対象コードは SYCL ディレクトリにあります（`sycl/src/core/verify.cpp:94-105`）。
- 通常の非 all-resident window では、`STRATA_VERIFY_EAGER` が未設定で segment capture ができていること。`capture()` は stepped かつ non-resident のとき `capture_segments()` を呼びます（`sycl/src/core/verify.cpp:1830-1837`）。`run()` は segment が存在する場合に stepped serve を実行します（`sycl/src/core/verify.cpp:2163,2177-2179`）。
- all-resident window は別経路です。test-stall 中でなければ stepped 用に host flag を graph launch 前に立て、その後 window 内の per-layer serve をスキップします（`sycl/src/core/verify.cpp:2164-2175,2307-2309`）。

`STRATA_VERIFY_EAGER` は run 時の `stepped_run` 条件と capture 時の segment capture を無効にしますが、all-resident の `stepped_ar` 条件には含まれません（同 `:1833,2163-2164`）。`STRATA_VERIFY_SPLIT=0` は capture 時に split-point hook を設定せず、層 group ごとの serve boundary は残します（同 `:1799-1809`）。`STRATA_VERIFY_PIPE=0` は split segment と CPU pool の並行実行を無効にします。未設定・空文字・先頭が `0` 以外なら並行実行を許します（同 `:2209-2212`）。

`STRATA_VERIFY_HOST_UNCACHED` が未設定または `env_on()` で無効なら、stepped mode 中は verifier の window buffer に uncached host memory を要求しません。有効にすると uncached host memory を使う分岐を維持します（同 `:220-243`）。

## 実行時の詳細

`g_stepped` は namespace scope の `const bool` として初期化されるため、プロセス起動時の環境値を読み、その後は再読込しません（`sycl/src/core/verify.cpp:94-105`）。`STRATA_VERIFY_STEPPED` 自体を読む箇所はこの一箇所です。non-resident 経路では window の token 数 `T` ごとに segment graph を capture し、`seg_[T]` が埋まっていれば再利用します（同 `:1783-1819,1830-1837`）。

segment は queue boundary で閉じられ、serve point では queue を待って doorbell の sequence と payload を確認し、CPU pool に expert を処理させます。必要なら次の split segment を先行 submit し、DMA copy 完了後に flag B と次の window flag を立てます（同 `:1799-1809,2185-2267`）。`STRATA_VERIFY_PIPE` の既定はこの並行化を許可する値です。`STRATA_VERIFY_SPLIT` は split-point を追加する設定です。

値が有効でも、all-resident window は segment serve を行わず、prefill expert row があれば gather 後に flag を graph launch 前に設定する一括 graph 経路です（同 `:2163-2175,2307-2309`）。また `STRATA_VERIFY_STEPPED` が有効な間は shared-expert stream fork と verifier の lean 経路も抑止されます（同 `:830,1361`）。

non-resident stepped 経路は `--remote-expert-opt` に対応せず、`run()` は `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` を返して失敗します（同 `:2177-2179`）。segment serve 中に sequence が届かない場合は `verify (stepped): layer ... did not ring after its queue drained ...`、pool が失敗した場合や queue/graph の例外も `err` に格納して `false` を返す経路があります（同 `:2185-2194,2212-2236,2258-2270`）。呼び出し元の generate 経路は verifier failure を `ERR ...` として出力し終了コード 1 を返します（`sycl/src/program/generate.cpp:11834-11839`）。この変数固有の有効化ログは確認できません。

## 根拠

- `sycl/src/core/verify.cpp:94-105` — 値判定 helper と起動時の `g_stepped` 初期化。
- `sycl/src/core/verify.cpp:830,1361` — stepped 有効時の lean / shared-expert fork 抑止。
- `sycl/src/core/verify.cpp:220-243` — stepped 時の host uncached memory 選択と `STRATA_VERIFY_HOST_UNCACHED`。
- `sycl/include/strata/core/verify.hpp:365-376` — stepped mode と serve/split hook の説明。
- `sycl/src/core/verify.cpp:1783-1819,1830-1837` — segment capture、再利用、eager/all-resident 条件。
- `sycl/src/core/verify.cpp:2160-2270,2307-2309` — run 時の分岐、serve、失敗経路。
- `sycl/src/program/generate.cpp:11834-11839` — verifier 失敗の CLI 出力と終了。
