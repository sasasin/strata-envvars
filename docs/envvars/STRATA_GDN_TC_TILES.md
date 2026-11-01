# `STRATA_GDN_TC_TILES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の GDN（DeltaNet recurrence）tensor-core scan が通常の scan を実行できず split scan に fallback するとき、1 value head あたりの tile 数を指定します。この変数だけでは tensor-core scan は有効になりません。通常の CUDA recurrence dispatch に入り、別変数 `STRATA_GDN_TC` が有効で、token 数が 128 以上で、通常 scan が失敗した場合に初めて tile 数が split scan の実行に影響します。

## 値と判定

実装は `std::atoi` で文字列を整数化し、全体の妥当性を検証しません。値が正なら `1` または `2` に制限します。

| 環境値 | `atoi` の結果 | tile 数 |
|---|---:|---:|
| 未設定 | 変換しない | 自動判定。GPU の SM 数が 96 以上なら 2、それ以外は 1 |
| 空文字 | 0 | 自動判定 |
| 数値として 1 | 1 | 1 |
| 数値として 2 以上 | 正数 | 2 |
| 0、負数、数値に変換できない文字列 | 0 以下 | 自動判定 |
| 数字の後ろに文字がある値（例 `2x`） | `atoi` が読む先頭数値 | その結果に従う（`2x` は 2 tiles） |

範囲外の整数文字列に対する `atoi` の結果は C/C++ の仕様上保証されないため、特定の値として扱えるとは記しません。値の大文字小文字や空白を別途検査するコードはありません。

テスト用 `GdnProbe` が設定され、その `tc_tiles` が正なら、probe の値を先に 1/2 に丸めて使い、環境変数を読みません。通常の engine 経路では probe は設定されません。

## 有効になる条件

- CUDA 用の `src/prefill/kernels.cu` の通常 dispatch が対象です。HIP 用コードではこの CUDA dispatch ブロックがコンパイル対象外です。
- serial 出力付き経路、`T <= 0`、または `variant == 2` の経路では通常 dispatch に入らず、この変数は使われません。
- `STRATA_GDN_TC` が `std::atoi` で非ゼロと判定され、かつ `T >= 128` のとき tensor-core scan が候補になります。`STRATA_GDN_TC` が未設定または 0 なら、この変数は tensor-core scan を開始させません。
- 最初の通常 tensor-core scan が成功すれば、tile 数の指定はその実行に使われません。指定値が作用するのは通常 scan がエラーを返し split scan を試す場合です。
- split scan が選べるかは別途 GPU の compute capability、SM 数、shared memory、scratch allocation に依存します。split scan も失敗すると、dispatch は有効なら chunked scan、それも選ばれなければ key-head / pipelined / columns kernel へ進みます。

## 実行時の詳細

`gdn_tc_tiles()` は通常 dispatch の `STRATA_GDN_TC` 分岐より前で呼ばれるため、probe override がない場合は tensor-core scan が有効でない呼び出しでも初期化されます。関数内の `static const int` は環境値を一度だけ読み取り、その結果をプロセス内に保持します。自動判定時の SM 数も device ごとに cache されます。したがって、初回評価後にプロセスの環境値を変えても再評価されません。

通常 scan が失敗した後の split scan では、tile 数 2 かつ `STRATA_GDN_TC_NP` の有効値が既定の 3 の場合、value head ごとに 2 blocks を起動する別 kernel を使います。それ以外の組み合わせは 1 block/head の split kernel です（`STRATA_GDN_TC_NP` は 1、2 以外を 3 に置換）。出力 norm がある経路では、tile 数 1 かつ `STRATA_GDN_TC_FUSE` が有効な場合に限り norm を split scan 内で融合でき、tile 数 2 では後段の norm kernel に進みます。

この環境変数専用のログ、警告、終了動作はありません。通常 dispatch では通常 scan または split scan が使えない場合に後続 kernel へ fallback します。テスト probe 経由では選択経路と理由を `GdnProbe` の出力欄に記録しますが、これは engine の利用者向けログではありません。kernel launch 後のエラーは通常の `check("gdn_recurrence")` に渡されます。

`docs/DETAILS.md:1539-1545` は `STRATA_GDN_TC` の概要と測定値を記載していますが、`STRATA_GDN_TC_TILES` の値、fallback 条件、tile 数の効果は説明していません。本書では測定値や速度差を推定していません。

## 根拠

- `src/prefill/kernels.cu:1279-1299`: tensor-core scan の tile 値の読み取り、`atoi`、1/2 への丸め、自動 SM 数判定と cache。
- `src/prefill/kernels.cu:1308-1327,1348-1368`: scan の適用条件、split/non-split の shared memory 判定と scan kernel launch。
- `src/prefill/kernels.cu:2986-3002`: CUDA dispatch、`STRATA_GDN_TC` 判定、probe、tile 値取得、および norm 融合の条件。
- `src/prefill/kernels.cu:3003-3069`: forced probe 経路と通常経路、TC 失敗後の split/chunked/base kernel fallback、probe の結果記録。
- `include/strata/prefill/gdn_probe.hpp:29-39`: probe の tile override と結果欄。`src/prefill/gdn_harness.cu:168-207` は harness が probe 値を渡して結果を記録する箇所。
- `docs/DETAILS.md:1539-1545`: 関連する `STRATA_GDN_TC` の説明。tiles 変数についての記載はありません。
