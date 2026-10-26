# `STRATA_PREFILL_ROOFLINE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この HEAD の Strata 本体では、この環境変数を読む実装を確認できない。したがって、HEAD の通常ビルドや実行中の prefill 動作をこの変数で変更するとは確認できず、値の設定で本体にカウンター出力が加わるともいえない。

候補名の由来として、リポジトリのベンチマーク記録には計測専用パッチでの使用が記録されている。ただし、そのパッチは結果提出物に含まれる測定用 artifact で、PR のエンジンソースには適用されていないと README が明記している。下記の値の説明はその artifact に限定され、調査対象 HEAD の挙動ではない。

## 値と判定

HEAD の Strata 本体では読み取り箇所がないため、未設定・空文字・任意の文字列に対する本体の判定規則はない。

参考として、ベンチマーク用 `instrumentation.patch` では `std::getenv("STRATA_PREFILL_ROOFLINE") != nullptr` で設定有無だけを判定する。したがって、パッチを適用した当時の計測ビルドでは値の内容は比較せず、空文字を含む設定済みの値で計測カウンターを有効にする。これは HEAD の本体に適用できる説明ではない。

## 有効になる条件

HEAD に有効化条件はない。ベンチマーク記録では、この計測パッチを Strata `0.1.41` のベースソース `fb58e0dbc8399662c0e47c76578c6e878b14f6cf` に適用し、CUDA `sm_61` でビルドしたとされる。README は HIP/SYCL をビルドしていないと記載している。これらは当時の測定環境についての記録であり、現在の HEAD での対応状況を示さない。

## 実行時の詳細

HEAD で本体・サーバー・セットアップ・同梱ツールのコードを対象に名前を検索したが、実装読み取り箇所は見つからなかった。ベンチマーク結果ディレクトリを含めたリポジトリ全体での出現も、ベンチマーク README、`instrumentation.patch`、その測定設定・結果に限られる。よって、起動時の評価、リクエストごとの評価、子プロセスへの設定、ログ出力など、HEAD の実行時挙動は確認できない。

測定 artifact の README は、この変数を設定した計測パッチが primary GPU の expert copy payload、copy call 数、重複を除く byte 数と expert 数を prefill 呼び出しごとに数える、と説明している。peer copy と GPU DRAM transaction は対象外である。測定値やこのカウンターの挙動を HEAD の機能として扱わない。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:672`。
- HEAD 全体で名前を検索し、本体コードに参照がないことを確認。ベンチマーク結果以外の tracked HEAD には一致箇所なし（`git grep -n 'STRATA_PREFILL_ROOFLINE' HEAD -- ':!bench/results/**'`）。これは不在の確認であり、実装箇所の行番号はない。
- 計測パッチでの環境変数判定: `bench/results/2026-10-09-community-p4-prefill-roofline/instrumentation.patch:9-21`。計測器の判定方法を示す資料であり、HEAD の実装根拠ではない。
- パッチが測定 artifact であり、エンジンソースに適用されていないこと、記録された計測範囲・ビルド対象: `bench/results/2026-10-09-community-p4-prefill-roofline/README.md:24`。
