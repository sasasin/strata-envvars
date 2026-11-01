# `STRATA_ADAPT_ASYNC_WAIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert arena を使う非同期 adaptive tier の swap-in コピーについて、コピー完了をその tick 内で待つか、未完了なら次の tick へ処理を持ち越すかを制御します。既定値は待つ動作です。変数名に `WAIT` とありますが、`0` にしてもコピーを待たずに residency table を更新するわけではありません。コピー完了を確認してから table を更新する条件は保たれ、待ち方が同期 wait から poll に変わります。

## 値と判定

ローカル helper は環境値が未設定または空文字なら既定値を返し、それ以外は `std::atoi` で変換します。変換結果が 0 なら無効、0 以外なら有効です。文字列全体の検証やエラー報告はありません。

| 環境値 | `a_wait` | 判定 |
|---|---:|---|
| 未設定 | 1 | 既定で待つ |
| 空文字 | 1 | helper が既定値を返す |
| `1`, `2`, `-1` など数値として 0 以外 | 1 | 待つ |
| `0`, `00`, `0xyz`, `xyz` | 0 | 待たずに poll する |

`atoi` は先頭の空白と符号を許容し、数値接頭辞の後ろは判定しません。したがって例の `0xyz` は 0、`1xyz` は 1 になります。数値に変換できない文字列は 0 です。CLI 引数でこの変数を上書きする処理は見つかりませんでした。

根拠: `src/program/generate.cpp:11689-11697`。

## 有効になる条件

この設定値は `srcp == &arena_src` のときだけ読み取られ、arena mode 以外では `a_wait` は常に false です。読み取られても、実際の効果が出るには async adaptive tier の job thread が作られている必要があります。これは明示的な `--adapt-async 1`、または CLI で async 設定を指定しなかった場合にエンジンが自動選択する `adapt_async_self` のいずれかで成立します。adaptive tier が空（`--adapt-every` または `--adapt-swaps` が無効）なら job thread は作られず、値は使われません。

明示 `--adapt-async 0` は async tier を止めます。CLI で `--adapt-async` を指定しない場合は別変数 `STRATA_ADAPT_ASYNC` を含む自動選択が先に行われ、この変数はその選択そのものを切り替えません。arena mode の async tier は `--serve` が必要で、複数 GPU の layer split および `--pipeline-windows 2` では無効化されます。無効化時には `--adapt-async 1 is off (...)` の stderr ログが出て blocking tier になります。

根拠: `src/program/generate.cpp:9022-9063,11686-11712`、`include/strata/core/adapt_async_default.hpp:34-44`。

## 実行時の詳細

値は async tier の状態機械を組み立てるときに一度読み、`const bool a_wait` に保持します。サーバーの各 request ごとに環境を読み直す処理ではありません。arena async tier の swap-in 状態では `a_ready(drain || a_wait)` を呼びます。

- 値が有効、または `drain` 中なら、job 完了を待ってから CUDA event を `cudaEventSynchronize` します。
- 値が無効で drain 中でなければ、job がまだ動いている場合や CUDA event が未完了の場合に false を返し、その tick の処理を止めます。後続 tick が再確認します。
- 完了を確認してから incoming expert を resident として登録し、residency table を更新します。したがって `=0` は完了前の expert を GPU 計画に載せません。drain は `a_ready(true)` となるため、この環境変数の値にかかわらず完了を待ちます。

async tier が動作している arena では、終了時の stderr 統計に `arena, copy-in only, batch ..., wait N, pick ...` と出て、この設定値から得た `a_wait` を確認できます。CUDA event wait がエラーになると adaptive refill error 状態になり、通常の decode 経路では `ERR an adaptive refill failed` を stdout に出して終了コード 1 を返します。コピー wait の方式自体がログやエラー文言を変える分岐は確認できませんでした。

根拠: `src/program/generate.cpp:11555-11563,11686-11712,11857-11867,11972-11984,12023-12031,17083-17086,17510-17519`。
