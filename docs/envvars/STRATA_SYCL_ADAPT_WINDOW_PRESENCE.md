# `STRATA_SYCL_ADAPT_WINDOW_PRESENCE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の mirror adaptive cache が verifier window ごとに集計する expert 利用量を、出現回数ではなく出現有無（0 または 1）として適応カウンター `drive.d.usage` に加算するかを切り替える。未設定または無効値では、window 内のルーティング回数をそのまま加算する。読み取りは `sycl/src/core/verify.cpp` の `Verifier::run` 内、window 完了後の利用量反映箇所にある（`sycl/src/core/verify.cpp:2663-2677`）。

これは生成時のルーティング結果や token の採否を直接変える設定ではなく、後続の適応 cache 候補スコアに入る利用量の単位を変える。適応処理は `drive.d.usage` を基に非 resident expert と resident expert を比較し、しきい値を満たすと cache 交換する（`sycl/src/program/generate.cpp:8515-8534`）。

## 値と判定

文字列全体の parse や数値変換はせず、`getenv` の戻り値が存在し、その先頭文字が `'1'` かだけを関数内 `static` の bool に保存する（`sycl/src/core/verify.cpp:2673-2676`）。

| 実行条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL verifier の mirror adaptive usage 集計が実行される場合 | 無効。window 内の route count を加算 | 先頭が `1` の値。例: `1`, `10`, `1anything`。その expert が window 内に 1 回以上選ばれた場合に `1` を加算 | 空文字、`0`, `0anything`, `2`, `true`, ` 1`。window 内の route count をそのまま加算 |
| それ以外の経路 | 読み取り箇所に到達しない | この変数による処理なし | この変数による処理なし |

大文字小文字や空白の trim はなく、先頭 1 文字だけで判定するため、`true` は有効にならず、`1anything` は有効になる。数値としての妥当性、符号、後続文字は検査しない。`static` 初期化は利用量反映箇所で初めて到達したときに行われ、その後同じプロセスでは再評価されない（`sycl/src/core/verify.cpp:2673`）。

## 有効になる条件

- Strata を SYCL backend としてビルドしていること。トップレベル CMake では `STRATA_ENABLE_SYCL` が別 backend として `sycl/` を追加し、CUDA/HIP と同時には使えない（`CMakeLists.txt:23-32`）。
- mirror adaptive cache を有効にする `STRATA_SYCL_MIRROR_ADAPT` が先頭文字 `1` であること。そうでなければ verifier の利用量バッファは作られず、この変数による集計は行われない（`sycl/src/core/verify.cpp:73-79,899-906`）。
- verifier の device planning と `STRATA_VERIFY_NO_HOST` が有効であること。`env_on` は未設定・空文字・先頭が `0` の値を false とし、それ以外を true とする。mirror adaptive が有効なのにこの条件が欠けると `mirror adaptive expert usage requires NoHost device planning` 例外になる（`sycl/src/core/verify.cpp:146-152,899-905`）。
- mirror adaptive cache では `--serve`、`--stream-experts`、単一 device の完全な stream mirror が必要で、borrow / elastic / profile save、stages、peer device、remote cache は許可されない。`--adapt-every` は正数、`--adapt-swaps` は 1〜96 である必要がある。満たさない場合は `SYCL mirror adaptive cache requires single-device complete stream mirror, no borrow/elastic/profile save` を stderr に出して `1` を返す（`sycl/src/program/generate.cpp:5373-5383`）。
- `--adapt-every` ごとの adaptation で `drive.d.usage` が参照される。値 `1` は各 window の expert ごとの加算量を 0/1 にするため、候補と追い出し対象のスコア、および結果として後続の cache 交換判断を変え得る（`sycl/src/program/generate.cpp:8426,8509-8534`）。

この変数自体には CLI 引数や別環境変数による上書き処理はない。`STRATA_SYCL_MIRROR_ADAPT` が無効ならこの変数は効果を持たず、mirror adaptive の前提が満たされない場合は前述のエラー経路になる。

## 実行時の詳細

mirror adaptive が初期化されると verifier は層数×expert 数の device histogram を確保する。各 verifier window の開始時に histogram をゼロクリアし、ルーティング ID が作られた層で GPU kernel が各 `(layer, expert)` の選択回数を atomic 加算する（`sycl/src/core/verify.cpp:899-905,1531-1533,2338-2341`）。

window 完了後、host は histogram を読み戻し、合計が `層数 × window の token 数 × top-k` と一致しなければ `mirror adaptive route histogram coverage mismatch` 例外を投げる。続いて本変数を一度だけ評価し、無効なら各 expert の生カウントを、先頭文字 `1` なら `count > 0 ? 1 : 0` を float の usage counter に加える（`sycl/src/core/verify.cpp:2663-2677`）。従って設定変更をプロセス実行中に反映するコードはない。

通常の mirror adaptive では adaptation 後に usage を `--adapt-decay` 倍する。presence 集計を選ぶと、window 内の同一 expert への複数 route は一回分になるが、window をまたいだ加算と decay は続く（`sycl/src/program/generate.cpp:8563-8565`）。この集計により得られる後続の cache 交換が生成結果へ与える影響はコード上この環境変数単独では確定できないため、token 選択が変わるとは断定しない。

## ログと測定値

この変数の値や presence 集計を直接報告する専用ログはない。mirror adaptive の条件を満たした起動では `SYCL mirror adaptive cache: sync exchange; ...` が stderr に出るが、値の有効・無効は表示しない（`sycl/src/program/generate.cpp:5382-5383`）。不正な有効条件では前節の拒否ログ、実行中の交換失敗では `SYCL mirror adaptive exchange failed: ...` が stderr に出て、生成ループは `ERR SYCL mirror adaptive exchange failed` を stdout に出して `1` を返す（`sycl/src/program/generate.cpp:8543-8545,12404-12408`）。この変数の測定値は Strata 資料で確認できなかった。

## 根拠

- `sycl/src/core/verify.cpp:73-79` — mirror adaptive を有効化する別環境変数の読み取り。
- `sycl/src/core/verify.cpp:899-906` — NoHost/device planning 条件と利用量 histogram の初期化。
- `sycl/src/core/verify.cpp:1531-1533,2338-2341` — window ごとの route count の加算と histogram 初期化。
- `sycl/src/core/verify.cpp:2663-2677` — window 完了後の検証、対象環境変数の判定、usage 加算。
- `sycl/src/program/generate.cpp:5373-5383,8426,8509-8565,12404-12408` — 適用条件、adaptive cache の利用量参照、交換と観測可能な失敗経路。
- `CMakeLists.txt:23-32` — SYCL backend の分離。
