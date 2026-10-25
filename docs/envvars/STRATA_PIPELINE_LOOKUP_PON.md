# `STRATA_PIPELINE_LOOKUP_PON`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` の生成経路で、suffix lookup から作る次の投機 window（B）の `p_on` 推定値を指定します。lookup が現在の window（A）より先までトークンを持ち、lookup の継続を A に採用した場合、その余りから B を作ります。この変数はその B の推定値だけを変え、suffix lookup の採用判定やトークン列そのものは変えません。

値は `src/program/generate.cpp` と `sycl/src/program/generate.cpp` で同じように読み取られます。いずれも `pipe_dbg_env()` を通るため、`STRATA_PIPELINE_DEBUG` が有効でないと設定値は参照されず、既定値 0.75 が使われます。

## 値と判定

| 状態 | `pl_lookup_pon` |
|---|---:|
| `STRATA_PIPELINE_DEBUG` が無効（またはこの変数が未設定） | 0.75 |
| debug が有効で、この変数が設定済み | `std::atof()` の結果を `float` に変換 |

`atof()` は文字列全体の厳密な数値検証をしません。空文字や数値として変換できない文字列は 0 になり、数値の後ろに文字が続く場合は数値部分が変換されます（例: `0.4tail` は 0.4）。負値や 1 を超える値も clamp されません。B を作る条件は `pl_lookup_pon > 0.0f` なので、0、負値、変換失敗値では lookup 由来の B を作りません。正値なら B にそのまま `p_on` として設定します。

debug helper は `STRATA_PIPELINE_DEBUG` の設定値の先頭文字だけを判定します。未設定、空文字、先頭文字が `0` の値は無効です。それ以外は有効です（例: `false` や先頭が空白の値も有効）。`STRATA_PIPELINE_LOOKUP_PON` 自体は、debug が無効なら読み取られません。

## 有効になる条件

- `--pipeline-windows` が有効で、実際に pipeline 経路が作られている必要があります。CUDA は `o.pipeline_windows > 0`、2 stage 以上、同一 split ではなく、stage 数が条件に合う場合です。SYCL は `o.pipeline_windows > 0` かつ2 stage の経路です。
- suffix drafting が有効である必要があります（`--suffix-draft` が 0 より大きい）。
- A 以外の window ではなく A の lookup が処理されること、lookup 提案が空でないこと、lookup の先頭 token が現在の chain の先頭と一致すること、draft policy が lookup を採用することが必要です。
- lookup 由来の A の末尾に B 用の token が少なくとも1個残っていて、B がまだ作られていないことが必要です。
- 生成された B が実行されるかは、この値だけでは決まりません。B の `p_on` は `theta` との比較に使われます。stage 0 では `B.p_on >= theta` などの条件が必要ですが、front stage の stage 0 より後では異なる分岐があります。また `STRATA_PIPELINE_PRESTAGE` や pipeline の状態も関わります。

## 実行時の詳細

`pipe_dbg_env()` は `STRATA_PIPELINE_DEBUG` の判定結果を translation unit 内の `static const bool` に一度だけ保存します。lookup 推定値も `static const float` で初回評価時に保存されます。そのため、同じプロセスで環境を後から変更しても再評価されません。CUDA と SYCL の各実装はそれぞれ独立に同じ判定を持ちます。

lookup 由来の B を作るとき、実装は A の後に続く余剰 token を最大 `S` 個まで B にコピーし、B の確率推定 `p_on` に本変数の値を設定します。投機起動の条件が成立すれば verifier が B を処理します。debug pipeline trace では `tre("CD", ..., 3, (int)(1000.0f * B.p_on))` を記録します。また `STRATA_PIPELINE_LOG` が有効な場合、stderr に B の `p_on` を含む pipeline log を出します。

既定値 0.75 は実装に記載された推定値です。測定結果や実際の確率精度を示す根拠は確認できなかったため、性能や確率の実測値は記載しません。

## 根拠

- 共通の debug ゲートと値判定: `src/program/generate.cpp:340-345`, `sycl/src/program/generate.cpp:296-301`。
- CUDA の pipeline 経路条件: `src/program/generate.cpp:8860-8864`。
- SYCL の pipeline 経路条件: `sycl/src/program/generate.cpp:7210-7215`。
- CUDA の既定値、lookup 条件、B の生成と `p_on` 設定: `src/program/generate.cpp:14300-14336`。
- SYCL の既定値、lookup 条件、B の生成と `p_on` 設定: `sycl/src/program/generate.cpp:11049-11085`。
- CUDA の B の prestage / 推定値による stage 0 投機条件: `src/program/generate.cpp:14480-14493,14512-14520`。
- SYCL の同等の条件: `sycl/src/program/generate.cpp:11225-11238,11251-11256`。
