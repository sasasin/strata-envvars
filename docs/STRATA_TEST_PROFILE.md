# `STRATA_TEST_PROFILE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この commit の Strata 本体および調査対象に含まれる通常の同梱ツールには、`STRATA_TEST_PROFILE` を読む実装を確認できませんでした。したがって、Strata の実行ファイル、サーバー、セットアップ処理について、この変数が制御する動作は確認できません。`000_envvers.md` に載っていることだけでは、Strata の利用者向け設定とは判断できません。

候補名の参照は `bench/results/2026-10-07-community-arc-b65-v01402/` 内のベンチマーク記録用ファイルに限られます。調査手順の対象外であるベンチマーク結果・記録は Strata 本体の挙動の根拠に含めていません。

## 値と判定

Strata 本体の読み取り箇所がないため、未設定・空文字・設定値の parse、既定値、無効値時の fallback は該当しません。Strata がこの値を数値化・文字列比較する処理も確認できませんでした。

## 有効になる条件

本体での読み取りが確認できないため、OS、backend、build macro、CLI、モデル状態、他の環境変数による有効条件や相互作用はありません（本体の実装に関する調査結果です）。

## 実行時の詳細

対象 commit の tracked files で完全一致検索した結果、本体およびベンチマーク結果・記録以外に `STRATA_TEST_PROFILE` の参照は見つかりませんでした。従って、起動時・リクエストごとの評価、プロセス起動後の変更、子プロセスへの継承・上書き、ログやエラーなど、Strata が行う処理は確認できません。

## 根拠

- 候補名は `docs/000_envvers.md` にあります。同一覧は grep 由来の候補であり、実装の存在を保証しません。
- `git grep -n -w STRATA_TEST_PROFILE HEAD -- ':!bench/results/**'` では該当がありませんでした。
- 対象 commit のベンチマーク記録配下には参照があります（`bench/results/2026-10-07-community-arc-b65-v01402/public-fixtures.py:26`, `BUILD.md:98`）。これらは調査手順で定める対象外のため、Strata 本体の機能・値の仕様を裏付ける根拠として扱っていません。
