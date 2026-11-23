# `INK_SYCL_HYBRID_STATS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は hybrid engine の有効化や計算方法を切り替えず、engine の `release()` 時に累積カウンタを stderr に出す条件だけを切り替える。カウンタ自体はこの変数の有無にかかわらず更新される。実装は Intel Arc SYCL backend に含まれる `InkSyHybridEngine` である（`engine/src/inkling2/sycl/ink_sy_hybrid.h:357-364,457-477`）。

## 値と判定

`release()` で `std::getenv("INK_SYCL_HYBRID_STATS")` の戻り値が null かどうかだけを見る。文字列の解析・数値変換・先頭文字比較はしない。そのため未設定なら出力条件を満たさず、空文字、`0`、`1`、`true`、大文字小文字を変えた値、空白を含む値など、設定されていればどの値でも同じ扱いになる。無効値として拒否される値や値域はない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:471-477`）。

| 条件 | unset | 設定時に出力条件を満たす例 | 出力条件を満たさない例 |
|---|---|---|---|
| Strata の SYCL backend を含む build | 環境変数が null のため出力しない | 空文字、`0`、`1`、`true` など、null でない値 | 値による無効値はない。engine が inactive の場合は値にかかわらず出力しない |

## 有効になる条件

- 実行ファイルに Strata の Intel Arc SYCL backend が含まれ、`InkSyHybridEngine::release()` まで到達する必要がある。SYCL backend は `strata_inkling_sycl` として定義され、`INKLING_ENABLE_SYCL=1` を設定して `strata-inkling` にリンクされる（`engine/src/inkling2/sycl/CMakeLists.txt:7-9,43-45`）。変数そのものに OS や `INK_SYCL_USE_ONEMKL` による値判定はない。
- `release()` の時点で hybrid engine が `active` でなければ出力しない。初期化では `INK_SYCL_NO_HYBRID` が未設定、または先頭文字が `'1'` でないこと、`m.n_host_experts > 0`、および `slot_stride != 0` が必要である。いずれかを満たさない場合は初期化が戻り、`active` にならない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:488-500,536`）。
- runner は初期化後、`hybrid.active` の場合にだけ hybrid MoE 処理を呼び出す。active でない場合は別の SYCL MoE 経路へ進む（`engine/src/inkling2/sycl/ink_sy_runner.h:328-333,656-680`）。
- CLI 引数や設定ファイルによるこの変数の上書き・優先順位は実装にない。これは出力条件であり、Hybrid 機能の有効条件とは別である。

## 実行時の詳細

`InkSyHybridEngine::release()` が worker を停止・join し、未完了の promotion があれば `Q_copy().wait_and_throw()` した後に、環境変数の有無と `active` を確認して統計行を出す。したがって起動時や各リクエスト時の読み取りではなく、`release()` ごとの読み取りで、static cache はない。runner の `release()` はこの関数を呼び、runner の destructor も `release()` を呼ぶ。初期化の先頭でも既存状態を `release()` するため、再初期化時にも条件を満たせば出力される（`engine/src/inkling2/sycl/ink_sy_hybrid.h:457-485,488-490`; `engine/src/inkling2/sycl/ink_sy_runner.h:165-168,328-330`）。

統計カウンタは engine のメンバーとして 0 初期化され、MoE pair の VRAM hit / CPU hit、prefill での host expert streaming、完了した cache promotion、cache に載った core loop の後続 pass hit に応じて加算される。カウンタをリセットする処理は `release()` にないため、同じ engine を再初期化した場合には値が累積する（`engine/src/inkling2/sycl/ink_sy_hybrid.h:357-362,573,655-673,756-769`）。

環境変数はキャッシュされず、各 `release()` 内でその時点のプロセス環境から読み取られる。Strata ソース内にこの変数を設定したり子プロセスへ転送したりする箇所は、候補名の全参照検索では見つからない。

## ログと測定値

出力先は stderr で、`active` かつ `getenv` が null でない場合に次の形式を 1 行出す。`%llu` 部分にはそれぞれ対応する累積カウンタの値が入る（`engine/src/inkling2/sycl/ink_sy_hybrid.h:471-477`）。

```text
[ink_sycl_hybrid] stats: vram_hits=%llu cpu_hits=%llu prefill_streamed=%llu cache_promotions=%llu loop_prom_hits=%llu
```

未設定または inactive ではこの行は出ない。設定値の不正を示す警告やエラーはない。統計出力前に未完了 promotion の `wait_and_throw()` が例外を送出した場合は、統計出力箇所まで到達しない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:467-477`）。この変数に関する性能測定値は Strata の `docs/DETAILS.md` に記載されていない。

## 根拠

- 候補名の Strata ソース内参照は `engine/src/inkling2/sycl/ink_sy_hybrid.h:471` のみ。値の有無判定と stderr 出力は同ファイル `:471-477`。
- engine の active 条件と初期化ログは `engine/src/inkling2/sycl/ink_sy_hybrid.h:488-542`。
- カウンタ定義・更新は `engine/src/inkling2/sycl/ink_sy_hybrid.h:357-362,573,655-673,756-769`。
- runner からの初期化・呼び出し・解放は `engine/src/inkling2/sycl/ink_sy_runner.h:165-168,328-333,656-680`。
- SYCL backend build の定義とリンクは `engine/src/inkling2/sycl/CMakeLists.txt:7-9,43-45`。
