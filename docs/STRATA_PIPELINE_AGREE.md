# `STRATA_PIPELINE_AGREE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` のデコード中、投機窓 B の起動見込み確率 `B.p_on` を計算する際、直前の窓 A が丸ごと受理される確率の推定元を切り替えます。これはパイプラインの内部調整用フックで、通常の利用者向け設定ではありません。

この変数単独では読まれません。`STRATA_PIPELINE_DEBUG` が有効な場合に限り読み取り helper が値を返し、それ以外では unset と同じ既定動作になります。CUDA と SYCL の実装に同じ判定があります。

## 値と判定

`STRATA_PIPELINE_DEBUG` が有効なとき、`STRATA_PIPELINE_AGREE` の文字列を `std::atoi` に渡し、結果が 0 かどうかで判定します。文字列全体の数値妥当性は検査しません。

| `STRATA_PIPELINE_AGREE` | 動作 |
|---|---|
| 未設定 | 有効（既定値 `true`） |
| 数値変換結果が 0 でない値（例: `1`, `-1`, `2tail`） | 有効 |
| 空文字、`0`, `0tail`, 数字で始まらない文字列 | 無効 |

`atoi` のため、先頭空白と符号は変換規則に従い、数字列の後ろの文字は無視されます。大文字小文字の比較はありません。`STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` の場合、この変数の設定値にかかわらず helper は `nullptr` を返し、`STRATA_PIPELINE_AGREE` は既定の有効扱いです。デバッグ gate 自体は先頭文字が `0` でない非空文字列で有効になり、ここでは `atoi` を使いません。

## 有効になる条件

- `--pipeline-windows` のデコード用パイプライン経路が実行され、ドラフト層チェーン `chain_kind == 1` から次の窓 B を組み立てる場合に確率推定へ使われます。
- チェーン結果が揃うか、B の確率計算に必要な出力まで到着し、B を決定する分岐に入る必要があります。
- `STRATA_PIPELINE_DEBUG` が有効でない場合は `STRATA_PIPELINE_AGREE` を読まず、既定の有効動作になります。
- CUDA と SYCL の `generate.cpp` に実装があります。プラットフォーム別の値判定差はありません。

`docs/MULTI_GPU.md` はパイプライン窓が投機実行であることと `STRATA_PIPELINE_*` 調整変数が `STRATA_PIPELINE_DEBUG=1` のときに読まれることを説明していますが、この変数が選ぶ確率式や parse の詳細は説明していません。

## 実行時の詳細

強制チェーン（`chain_kind == 1`）では、A のドラフト各 token について、チェーンがその位置で予測した確率 `op[i]` を掛け合わせて A 全体の受理見込み `pa` を作ります。チェーンが出した token と A の token が一箇所でも違えば、`STRATA_PIPELINE_AGREE` が有効な場合は `pa` を 0 にし、不一致カウンターを増やします。無効の場合は比較結果を確率に反映せず、A に保存された確率 `A.prob[i]` の積を使います。

その後 `make_b()` は `B.p_on = pa * op[base]` として B の起動見込みを設定します。既定の `STRATA_PIPELINE_THETA` と比較して投機起動するかを決めるため、値は B を前段 GPU で投機実行する判断に影響します。ここでの不一致は見込み確率を変えるもので、最終 token の採否は verifier の結果に基づきます。

環境値は `pipe_dbg_env()` と関数内 `static const bool` を通して一度だけ取得・保存されます。`STRATA_PIPELINE_DEBUG` の gate 値も helper の static 初期化で一度だけ保存されます。どちらも初回評価後のプロセス内環境変更は反映されません。`STRATA_PIPELINE_LOG` が有効なら chain の `p_on` などを stderr に記録し、デコード timing が有効なら最終統計に forced-chain disagreements 数が表示されます。`STRATA_PIPELINE_AGREE` 自体の値に対する専用ログはありません。

## 根拠

- `src/program/generate.cpp:340-345`: `STRATA_PIPELINE_DEBUG` による gate、設定時の先頭文字判定、`pipe_dbg_env()`。
- `src/program/generate.cpp:14357-14360`: `STRATA_PIPELINE_AGREE` の既定値と `atoi` 判定。
- `src/program/generate.cpp:14466-14480`: 強制チェーンで使う確率、token 不一致時の `pa=0`、B の生成。
- `src/program/generate.cpp:14207-14222`: `make_b()` が `B.p_on` を計算。
- `src/program/generate.cpp:14517-14548`: B の投機起動条件と閾値未満時の抑止。
- `src/program/generate.cpp:14606-14610`: disagreement 数を含む timing 統計。
- SYCL の同等箇所: `sycl/src/program/generate.cpp:296-301,11106-11109,11211-11225,10918-10934`。
- 関連資料: `docs/MULTI_GPU.md:445-453,498-500`（パイプライン窓の投機動作と tuning 変数の debug gate）。
