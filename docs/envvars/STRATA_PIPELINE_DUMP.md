# `STRATA_PIPELINE_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL engine の verifier commit ごとの診断を stderr に出し、decode window ごとの GDN 状態の要約（合計値と hash）を指定ファイルへ追記する debug 用環境変数である。モデル計算の選択を変える設定ではないが、状態を GPU stream から同期 readback して CPU で走査するため、設定時は追加の待ち・処理が入る。pipelined decode では pipeline 側の記録、serial decode では serial 側の記録を行う。`engine/sycl/src/core/verify.cpp` と `engine/sycl/src/program/generate.cpp` に読み取り箇所がある。

## 値と判定

値は数値や真偽値として parse せず、`std::getenv(...) != nullptr` で設定有無だけを見る。未設定なら追加の診断・状態記録を行わない。空文字を含め、設定されていれば commit ログと状態の readback/hash 計算を有効にする。`0`、`false`、`0anything` も無効値扱いにはならず、状態記録の箇所では値全体をファイル名として `fopen(..., "a")` に渡す。空白、大文字小文字、数値妥当性の検査や trim はない。ファイルを開けなかった場合の fallback はない。`engine/sycl/src/core/verify.cpp:4498-4501`, `engine/sycl/src/program/generate.cpp:12439-12440`, `12821-12822`, `12469-12474`, `12850-12855`。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL verifier の commit / decode 記録 | `getenv` が null。追加ログ・状態コピーなし | null 以外すべて（`""`、`"0"`、`"false"`、`"0anything"` を含む） | 値の parse による無効値はない。状態ファイルへの追記は `fopen` の成否に依存 |

## 有効になる条件

- 読み取り箇所は `engine/sycl/` にあるため、この処理は SYCL engine のコード経路に限られる。CUDA/HIP 実装で同名変数を読む箇所は候補名の全参照検索で見つからなかった。
- verifier commit の stderr 行は `Verifier::pl_commit_async` が呼ばれたときに出る。同メソッドの呼び出しは SYCL の pipelined prompt-window 経路と pipelined decode 経路にある。通常の serial `ver.commit` からはこの commit 行は出ない（`engine/sycl/src/program/generate.cpp:11207-11245`, `12393`, `12497`; `engine/sycl/src/core/verify.cpp:4493-4501`）。
- pipeline decode の GDN 記録は `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` であり、さらに request が cancel 済みでなく生成上限にも達しておらず、repetition penalty（`hist_n > 0`）や coupled draft sampling により serial fallback されない場合に入る。`pipe` 自体は `--pipeline-windows > 0`、2 stage、異なる GPU 上の stage で成立する（`engine/sycl/src/program/generate.cpp:7712`, `11783-11799`）。
- `--pipeline-windows` は `--serve`、2 GPU の layer split、ちょうど 2 stage、MTP drafter と `--spec` 2 以上を必要とし、`--batch`、`--peer-device`、helper cache がある場合は無効化される。CLI 指定がない場合の自動有効化は対象 GPU 等の条件に依存し、`STRATA_PIPELINE_AUTO=0` または `--pipeline-windows 0` で止められる。これらは pipeline 記録だけに関係し、serial decode の状態記録を止めない（`engine/sycl/src/program/generate.cpp:3590-3634`）。
- pipelined prompt-window 経路は `pipe && pl_pw >= 1` でも使われるが、`STRATA_LOGPOS` が設定されていると serial 経路を選ぶ。その場合 `pl_commit_async` の commit ログもその prompt 読み取り中には出ない（`engine/sycl/src/program/generate.cpp:11277-11281`）。
- serial decode の状態記録は `ver.commit` 成功後の通常 decode loop にあるため、`--pipeline-windows` が無効または pipeline decode の条件を満たさず serial fallback した場合も対象になる。記録対象は `ss.gdn_alloc` 件の GDN state であり、ループ内の再帰 state と conv history の値を走査する（`engine/sycl/src/program/generate.cpp:12811-12827`, `12832-12855`）。

## 実行時の詳細

3 つの読み取りはそれぞれ関数内 `static` に保存される。commit 行の有無は `pl_commit_async` の初回呼び出し時、pipeline 側のファイルパスは初回 pipeline decode verdict 後、serial 側のパスは初回 serial window の commit 後に読み取られる。その後にプロセス環境を変更しても、各箇所の判定・パスには反映されない。起動引数や設定ファイルによる `STRATA_PIPELINE_DUMP` の上書きはない（`engine/sycl/src/core/verify.cpp:4493-4501`, `engine/sycl/src/program/generate.cpp:12439-12440`, `12820-12822`）。

pipeline decode 側は各 verdict の後、stage 0 の stream から `ss.gdn_state` を `memcpy(...).wait()` で host vector に読み戻し、全 allocated GDN row の recurrence state と conv history を別々に走査する。serial 側も commit 後に verifier stream から同じ state を同期 readback して走査する。いずれも各 window で vector を作り、要素値の double 合計と hash を計算するため、この設定は timing を歪めうる（`engine/sycl/src/program/generate.cpp:12435-12468`, `12817-12849`）。

両経路は `fopen(path, "a")` を使い、pipeline 側は `pos <position> windows <count> rec <sum> <hash> cnv <sum> <hash>`、serial 側は `pos <position> serial rec <sum> <hash> cnv <sum> <hash>` の行を追記する。値はそのままファイルパスに使われ、環境変数が設定されているのに `fopen` が失敗した場合、状態の readback/hash 計算後に出力行を省略する。Strata 側に失敗ログや別パスへの fallback はない（`engine/sycl/src/program/generate.cpp:12469-12474`, `12850-12855`）。

## ログと測定値

`STRATA_PIPELINE_DUMP` が設定され、`pl_commit_async` が呼ばれるたび stderr に `strata commit: n_keep=%d T=%d pos0=%lld self_skip=%d\n` を出す。`self_skip` は `last_t_ == 1 && one_token_self_commit()` の値で、実際に早期 return する条件にはさらに `!self_commit_off_` があるため、この表示だけでは commit graph の skip を断定できない（`engine/sycl/src/core/verify.cpp:4498-4502`, `4525-4545`）。ファイル出力の形式は上記のとおり。`docs/DETAILS.md` にこの変数固有の測定値は見つからず、ここでは性能値を記載しない。状態 readback の待ちはソースコメントでも timing を歪めるとされている（`engine/sycl/src/program/generate.cpp:12435-12439`）。

## 根拠

- `engine/sycl/src/core/verify.cpp:4493-4502`, `4525-4545` — `pl_commit_async` の有無判定、stderr 診断、commit 分岐。
- `engine/sycl/src/program/generate.cpp:3590-3634`, `7712`, `11783-11799` — pipeline の既定・無効条件と decode 経路の条件。
- `engine/sycl/src/program/generate.cpp:11277-11281`, `11207-11245` — prompt-window の pipeline 選択と `pl_commit_async` 呼び出し。
- `engine/sycl/src/program/generate.cpp:12435-12474` — pipelined decode の GDN readback・hash・ファイル追記。
- `engine/sycl/src/program/generate.cpp:12811-12855` — serial decode commit 後の GDN readback・hash・ファイル追記。
