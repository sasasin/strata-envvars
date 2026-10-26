# `GEMV_X`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 判定

`GEMV_X` は Strata の通常実行ファイルが読む設定としては確認できませんでした。リポジトリ全体での唯一の読み取り箇所は `metal/tests/gemv_parity.cpp` で、Metal の GEMV parity / tile benchmark 用プログラム内にあります。このため、通常の Strata 推論実行の挙動を制御する環境変数としての役割・既定値・適用条件は確認できません。

`000_envvers.md` は候補リストであり、名前が利用者向け設定であることを保証しないとしています。この例はリストの候補名がテスト専用フックに由来するケースです。調査手順の境界に従い、テスト用コードを通常実行時の機能として説明しません。

## 候補名が現れる箇所

`metal/tests/gemv_parity.cpp` の bench 経路では `std::getenv("GEMV_X") != nullptr` で設定有無だけを確認しています。値の文字列・数値は読み取らず、空文字を含む何らかの値が設定されていれば true になります。未設定なら false です。同じ bench 経路で true の場合は `gemvx_*` 名の pipeline と専用の tile 候補群を選び、threadgroup memory の条件を適用します。false の場合は通常の `kCfgs` と `kname(...)` で選びます。ここでの分岐は benchmark の計測対象を選ぶためのもので、製品の推論経路に適用される根拠ではありません。

この判定は bench 部分で実行されるたびに評価され、関数 static 等へのキャッシュはありません。parity 専用経路は bench 部分より前に終了するため、その経路で `GEMV_X` は参照されません。これらはテストプログラム内での挙動であり、通常の Strata 実行について環境変数の評価時期や変更反映を示すものではありません。

## 有効になる条件と制限

`GEMV_X` を読むコードは `metal/tests/gemv_parity.cpp` だけで、Strata の `src`、`include`、`sycl`、`serve`、同梱 `tools` での読み取りは見つかりませんでした。`docs/DETAILS.md` にもこの変数の説明は確認できませんでした。従って、通常の Strata 実行ファイルにこの変数が含まれるか、また推論時に何らかの効果を持つかは、このソース調査からは裏付けられません。

## 根拠

- `metal/tests/gemv_parity.cpp:1-6` は対象を parity と性能測定と説明しています。
- `metal/tests/gemv_parity.cpp:243-245` は以下の処理を bench 経路として区切っています。
- `metal/tests/gemv_parity.cpp:288-315` は設定有無判定、pipeline 名と候補群の選択、threadgroup memory の設定を行います。
- `metal/tests/gemv_parity.cpp:226-240` は parity 経路が bench 部分より先に結果を出して終了する箇所です。
- `metal/kernels/gemv.metal:260` には `gemvx_*` kernel の登録がありますが、これはテストコード外から `GEMV_X` を読むことの根拠ではありません。
