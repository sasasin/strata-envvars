# `STRATA_PIPELINE_SWITCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_PIPELINE_SWITCH` は真偽値ではなく、パイプラインの試験設定を記したファイルのパスです。サーバーの各リクエストでファイルを開き、`pw`、`theta` などの項目があれば、そのリクエストに限ってパイプライン設定やプロンプト読み取り上限を上書きします。対象箇所は CUDA/HIP 実装と SYCL 実装の `engine/.../program/generate.cpp` です（`engine/src/program/generate.cpp:20245-20302`、`engine/sycl/src/program/generate.cpp:11151-11176`）。

この変数だけではパイプラインを有効にできません。`pipe` が成立し、さらに `STRATA_PIPELINE_DEBUG` が有効なときだけファイルを開きます。`pipe` は CUDA/HIP では `--pipeline-windows > 0`、複数 stage、同一 GPU 上の分割でないこと、全 stage が存在することが条件です（`engine/src/program/generate.cpp:13256-13267`）。SYCL では `--pipeline-windows > 0`、2 stage、同一 GPU 上の分割でないこと、stage 数が 1 つであることが条件です（`engine/sycl/src/program/generate.cpp:7708-7712`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP・SYCL 共通 | ファイルを開かず、各リクエストは通常の設定を使う | `STRATA_PIPELINE_DEBUG` が有効で `pipe` も成立していれば、環境変数の値をファイルパスとして `fopen(..., "r")` に渡す | 空文字は設定済みポインタですが空パスを開けず、何も上書きしない。存在しない・読めないパスも同様 |

環境変数値の文字列比較や数値変換はありません。環境変数が指すファイルから最大 255 byte を読み、NUL 終端した内容を検索します。内容全体の文法検証はせず、`strstr` で各キーの最初の出現を探し、その直後を `atoi` / `atof` / `atoll` で変換します。したがって空白や前後の文字列を含められ、数値の後ろにある非数値文字は変換時に無視されます。キーに値がない、または変換先頭が数値でない場合、`atoi` / `atoll` は 0、`atof` は 0.0 相当になります（`engine/src/program/generate.cpp:20284-20301`、`engine/sycl/src/program/generate.cpp:11163-11174`）。

| ファイル内キー | CUDA/HIP | SYCL | 境界・無効値の扱い |
|---|---|---|---|
| `pw=` | 対応 | 対応 | 整数変換後に 0〜2 へ clamp。例: `pw=-1` と `pw=garbage` は 0、`pw=3` は 2、`pw=1tail` は 1 |
| `theta=` | 対応 | 対応 | `atof` の float 値をそのまま使い、範囲 clamp なし。数値でない値は 0.0 相当 |
| `hit=` | 対応 | 非対応 | CUDA/HIP のみ。`atof` の値をそのまま使う。`theta=` が同じファイルに無ければ、判定を hit 率方式に切り替える |
| `lazy=` / `run=` | CUDA/HIP のみ | 非対応 | `atoi(...) != 0`。`1`, `-1`, `1tail` は true、`0`, 空値、非数値始まりは false |
| `force_miss=` | 対応 | 対応 | 整数変換後に 0 未満を 0 に clamp。正の `k` は k 回ごとの speculative window に強制 miss を入れる |
| `short_read=` | 対応 | 対応 | `atoll` 後に 0 未満を 0 に clamp。プロンプトの短い読み取りに使う上限 token 数 |

ファイルで項目を指定しない場合、既存値を引き継ぎます。`pw` は `--pipeline-windows`（または自動選択値）、`short_read` は `--short-read` の値です。CUDA/HIP の `theta` は `STRATA_PIPELINE_THETA` が有効ならその値、なければ `STRATA_PIPELINE_HIT_MIN` が 0 以上のとき hit 率方式用の `-1`、それ以外は `0.2` です。`hit` は `STRATA_PIPELINE_HIT_MIN` の初期値を上書きします。`lazy` と `run` はそれぞれ `STRATA_PIPELINE_LAZY_CHAIN` と `STRATA_PIPELINE_LOOKUP_RUN` の値を上書きします。`force_miss` は `STRATA_PIPELINE_FORCE_MISS` の値を上書きします。SYCL では `theta` と `force_miss` の初期値に `STRATA_PIPELINE_THETA` と `STRATA_PIPELINE_FORCE_MISS` が使われます（`engine/src/program/generate.cpp:20248-20283`、`engine/sycl/src/program/generate.cpp:11154-11161`）。

`STRATA_PIPELINE_DEBUG` は `pipe_dbg_env` 内で一度だけ評価され、未設定・空文字・先頭文字が `0` の場合は無効、それ以外は有効です。したがって `0anything` は無効、`false` や ` 0` は有効です（`engine/src/program/generate.cpp:681-686`、`engine/sycl/src/program/generate.cpp:325-340`）。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。無効なら helper が常に `nullptr` を返すため、対象ファイルは読みません（`engine/src/program/generate.cpp:684-686`、`engine/sycl/src/program/generate.cpp:337-339`）。
- `pipe` が成立していること。従ってパイプライン対応の serve 経路で `--pipeline-windows` が 1 以上である必要があります。`pw=` で 0 から 1/2 に変えることはできず、もともと `pipe` が成立していない場合はファイル読み取り分岐にも入りません（同 `engine/src/program/generate.cpp:13267,20284`、同 `engine/sycl/src/program/generate.cpp:7712,11163`）。
- CUDA/HIP では prompt の pipelined read は `n_stages == 2`、`pl_pw >= 1`、`STRATA_LOGPOS` 未設定のときに選ばれます。3 stage 以上では prompt read は serial ですが decode の pipeline 条件は別に評価されます（`engine/src/program/generate.cpp:20414-20419`）。SYCL の prompt read は `pl_pw >= 1` かつ `STRATA_LOGPOS` 未設定で pipeline へ進みます（`engine/sycl/src/program/generate.cpp:11277-11281`）。
- decode の speculative pipeline は `pl_pw >= 2` に加えて snapshot が利用可能である必要があります。CUDA/HIP では repetition penalty (`hist_n > 0`) または coupled draft sampling のリクエストは serial decode に戻ります（`engine/src/program/generate.cpp:21810-21818`）。SYCL でも `pl_pw >= 2` と snapshot の条件があります（`engine/sycl/src/program/generate.cpp:11783-11794`）。
- `short_read=` は `STRATA_CKPT_REREAD` が設定されていると効きません。これは `windows_ok` が `no_short` を先に検査するためです。画像 embedding 行を含む区間も verify windows を使いません（`engine/src/program/generate.cpp:20230-20243`、SYCL: `engine/sycl/src/program/generate.cpp:11142-11149`）。CUDA/HIP では非有限 prompt logits 後の一回限りの `req_short_read=0` 設定より後に switch file を読むため、ファイル内 `short_read=` があればその値で上書きします（`engine/src/program/generate.cpp:20231-20237,20284-20299`）。
- CLI の `--pipeline-windows` が明示されていれば通常その値が初期値ですが、switch 内 `pw=` が読み取られるとリクエスト単位で上書きします。未指定時の自動値は backend・GPU・serve/model 等で異なります。例として SYCL は 2 枚の Arc B-series、serve、MTP drafter などの条件で 2 を選び、CUDA/HIP の自動選択も serve、layer split、stage 数、draft、batch、helper cache などで制限されます（`engine/sycl/src/program/generate.cpp:3590-3633`、CUDA/HIP: `engine/src/program/generate.cpp:6555-6592`）。

## 実行時の詳細

`pipe_dbg_env` の有効/無効判定は関数内 `static` で、最初の呼び出し時に決まります。switch のパスも `if (static const char* sw = ...)` により最初にこのリクエスト箇所へ到達したときの値を保持し、以後の環境変数変更は反映しません。一方、保持したパスのファイルは各リクエストで再度 `fopen`・`fread` するため、ファイル内容の変更は後続リクエストに反映されます（`engine/src/program/generate.cpp:20284-20289`、SYCL: `engine/sycl/src/program/generate.cpp:11163-11168`）。

読み取った値は当該リクエストの `pl_pw`、speculative launch gate (`pl_theta` / CUDA/HIP の `pl_hit_min`)、lazy chain / lookup continuation (`pl_lazy`, `pl_run`)、強制 miss (`pl_force_miss`)、prompt の `req_short_read` に適用されます。`pw >= 1` は条件を満たす prompt read を pipelined windows に切り替え、`pw >= 2` は snapshot 条件を満たす decode に speculative window を許します。`theta` は推測 window の gate 閾値、`force_miss` はテスト用の miss 発生間隔です（`engine/src/program/generate.cpp:21810-21818,21850-21870,21982`、SYCL: `engine/sycl/src/program/generate.cpp:11783-11794,11815-11816,11952`）。

ファイルは 256 byte のバッファに最大 255 byte 読み込まれ、後続部分は無視されます。`fopen` が失敗した場合は警告やエラーを出さず switch の上書きもログもありません。正常に開けた場合はキーの有無にかかわらず stderr に `strata pipeline switch: ...` の行を出します。CUDA/HIP のログ項目は `pw/theta/hit/lazy/run/force_miss/short_read`、SYCL は `pw/theta/force_miss/short_read` です（`engine/src/program/generate.cpp:20285-20302`、`engine/sycl/src/program/generate.cpp:11164-11175`）。

## 根拠

- `engine/src/program/generate.cpp:681-686` — CUDA/HIP の `STRATA_PIPELINE_DEBUG` gate。
- `engine/sycl/src/program/generate.cpp:325-340` — SYCL の同 gate。
- `engine/src/program/generate.cpp:20231-20302` — リクエスト値、switch file の読み取り・変換・ログ。
- `engine/sycl/src/program/generate.cpp:11142-11176` — SYCL の同処理。
- `engine/src/program/generate.cpp:13256-13267,20414-20419,21810-21818` — CUDA/HIP の適用条件。
- `engine/sycl/src/program/generate.cpp:3590-3633,7708-7712,11277-11281,11783-11794` — SYCL の自動設定・適用条件。
- `docs/MULTI_GPU.md:203` — `STRATA_PIPELINE_*` tuning/test variables は `STRATA_PIPELINE_DEBUG=1` のときだけ読み込むという資料上の説明。具体的な値の処理は上記ソースで確認。
