# `STRATA_LM_PREFETCH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_LM_PREFETCH` は、layer-major prompt prefill において、その層で router が選ぶ expert が分かる前に、ストリーミング対象 expert の読み込みを `Stager` に先行投入するかを制御する。既定は ON。OFF にすると、attention と重ねて先行投入する段階を省き、router の結果が揃ってから必要な非 resident・非 pinned expert だけを `Stager` に投入する。expert の選択そのものや prefill の演算を切り替える変数ではなく、expert blob の読み込み開始時期と投入対象を変える（`engine/src/prefill/prefill.cpp:8579-8602, 8663-8687`）。

この判定は `Prefill::lm_run` の layer-major 経路だけで使われる。通常の chunk-major prefill、layer-major が選ばれない prompt、Metal の prompt 経路にはこの読み取り箇所がない（`engine/src/prefill/prefill.cpp:8401-8407, 9652-9705`）。

## 値と判定

`lm_run` 内の関数ローカル `static const bool` 初期化で `std::getenv` を一度呼び、値が未設定なら ON、設定されていれば `e[0] != '0'` を ON とする。文字列の parse や全体比較はなく、空文字も先頭文字が `'\0'` なので ON。先頭文字が `0` なら後続文字列にかかわらず OFF である（`engine/src/prefill/prefill.cpp:8582`）。

| 条件 | unset | ON になる例 | OFF になる例 |
|---|---|---|---|
| layer-major `lm_run` | ON | 空文字、`1`、`true`、`false`、` 0`、`10`、`x` | `0`、`0anything`、`00` |

大文字小文字、空白、数値としての妥当性は検査しない。したがって `false` は OFF を意味せず ON、先頭に空白がある ` 0` も ON である。CLI 引数・設定ファイル・別の環境変数によるこの値の上書きは実装中に見つからなかった。初回に `lm_run` がこの初期化箇所へ到達した時点の値がプロセス内に保持され、同じプロセスでの環境変更は反映されない（同 `:8582`）。

## 有効になる条件

- `Prefill::run` が layer-major の実行条件を満たすこと。実装は `hand_in_ == nullptr` かつ `impl_` があり、`prefill_layer_major_resolve(...)` が true の場合に `run_layer_major` へ進む。`STRATA_PREFILL_LAYER_MAJOR` の明示値や既定判定がこの経路の選択を決め、`STRATA_LM_PREFETCH` は layer-major を有効化しない（`engine/src/prefill/prefill.cpp:9657-9684`）。
- layer-major 実行中で、対象が最終層ではないこと。`lm_prefetch(l)` の呼び出しは `l < LE` に限られる（同 `:9068-9071`）。
- `m.src` が非 null であること。null の場合 `lm_prefetch` はすぐ成功して戻り、`pf_on` の値にかかわらず先読みは始めない（同 `:8583-8586`）。
- 先読みするのは `lm_streamed_experts(...)` が返す streamed expert。resident / pinned 状態などでリストから除かれた expert はこの先行投入に含まれない（同 `:8588-8601`）。
- `STRATA_MMQ_TIER_SORT=1` が有効な場合、tier sort に `pf_on` が渡される。prefetch ON では Tier 2 の expert を ID 順に保ち、OFF では Tier 2 を row count 順（同数なら ID 順）に並べる。tier sort 自体はこの変数ではなく `STRATA_MMQ_TIER_SORT` が要求する（`engine/src/prefill/prefill.cpp:8651-8662`; `engine/src/prefill/mmq_resident_sort.hpp:40-45, 125-139`）。

## 実行時の詳細

prefetch ON では、各非最終層の attention halves を実行する前に `lm_prefetch(l)` が streamed expert 一覧を作り、expert ID から Stager job への対応を保存してから `m.stager->start(...)` する。blob が安定したポインタを持つ場合はそのポインタを job に渡し、transient な blob や安定ポインタがない場合は expert source と layer / expert ID を渡す（`engine/src/prefill/prefill.cpp:8579-8602`）。このため Stager の読み込みを layer の attention halves と並行させる構成である（同 `:9068-9071`; `engine/src/prefill/prefill.cpp:1121-1125`）。

router の結果を集めた後、routed expert 以外に先行投入済みの job があれば `skip` される。routed expert の staging 時には job を `pass`、`wait` し、その blob を GPU へコピーして `issued_one` で DMA 完了イベントを記録する（`engine/src/prefill/prefill.cpp:8663-8668, 8801-8828`）。Stager worker は skip 済み job の blob を読まず、`wait` は ready になるまで待機する実装で、ここに時間制限はない（`engine/src/prefill/prefill.cpp:1233-1248, 1283-1305`）。

prefetch OFF では、事前投入で `pf_job` が埋まらない。router の結果を得た後、resident expert と pinned expert を除外し、routed な残りだけで job を作って Stager を開始する（`engine/src/prefill/prefill.cpp:8663-8687`）。どちらの設定でも、routed expert を処理するときの resident / pinned 判定と GPU への staging 経路は共通である（同 `:8801-8828`）。

## ログと測定値

この変数の ON/OFF を直接表示する専用ログは見つからなかった。layer-major 経路が完了すると `strata prefill: layer-major ...` の統計ログが出るが、その文面はこの変数の値を表示しない（`engine/src/prefill/prefill.cpp:9566-9574`）。ソース内の `Stager::copy_blobs` が失敗した場合は stderr に `prefill: the expert source could not copy experts %d.. of layer %d` を出して `std::abort()` する。この失敗は Stager の共通処理であり、この変数固有の警告ではない（`engine/src/prefill/prefill.cpp:1237-1247`）。layer-major 側でエラーを検出した場合は `err` を設定して `false` を返し、呼び出し側も失敗を返す（同 `:8804-8810, 9684-9692`）。

`docs/DETAILS.md` と release notes にこの変数の性能測定値は見つからなかったため、速度・token 結果については記載しない。

## 根拠

- 値の読み取りと既定値、先行 job の生成: `engine/src/prefill/prefill.cpp:8579-8602`
- prompt / layer 条件、呼び出し時点: `engine/src/prefill/prefill.cpp:9068-9071, 9657-9705`
- OFF 時の routed expert のみの staging: `engine/src/prefill/prefill.cpp:8663-8687`
- job の skip、wait、GPU copy: `engine/src/prefill/prefill.cpp:8801-8828, 1283-1305`
- tier sort との連携: `engine/src/prefill/prefill.cpp:8651-8662`; `engine/src/prefill/mmq_resident_sort.hpp:40-45, 125-139`
- 完了ログと staging worker の失敗経路: `engine/src/prefill/prefill.cpp:9566-9574, 1237-1247`
