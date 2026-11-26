# `--mtp-max-t`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | SYCL エンジンの root parser（`strata generate`、および `--serve` 実行） |
| オプション | `--mtp-max-t` |
| 別名 | なし |
| 値 | 整数引数 `M`。parser は `atoi` で変換し、負数を 0 に補正する |

## 役割

MTP（または DFlash2）の draft window の最大 token 数を指定する。suffix drafter（prompt lookup）を有効にしつつ MTP の窓を `--spec` より小さく保ちたい場合などに使う。MTP の窓をこの値で抑えた後も、suffix lookup は `--spec` までの窓を選べる。オプション値 0 は通常「`--spec` に従う」指定だが、suffix drafter または lookup-chain の条件を満たすと、初期化時に内部値が `--spec` へ置き換えられる（詳細は「実行時の動作」）。

## 使い方

```sh
strata generate --pack ./model --tokens '1,2,3' --spec 6 --mtp ./mtp-runtime --mtp-max-t 4
```

この例では、MTP の窓を最大 4 token に制限し、検証窓の上限を 6 token にする。実際の MTP 利用には MTP runtime も指定する必要がある。parser の値取りと MTP の設定は `engine/sycl/src/program/generate.cpp:1882-1887, 2049-2050, 2097-2099`、window cap は同ファイル `:9578-9582, 13991-13993` にある。

## 値と既定値

- 値は別引数として必要。値が省略されると parser の `next("--mtp-max-t")` が標準エラーに `--mtp-max-t needs a value` を出して終了コード 2 で終了する（`engine/sycl/src/program/generate.cpp:1884-1887, 2098`）。
- 初期値は 0。受け取った文字列は `atoi` で整数化し、`std::max(0, ...)` により負数は 0 となる。明示的な上限値の validation は parser にない（同ファイル `:771-772, 2098`）。
- 同じ引数を複数回指定した場合は parser の反復中に同じフィールドへ再代入されるため、最後に現れた値が残る（同ファイル `:1882-1887, 2098`）。
- 有効な MTP / DFlash2 window では、正の値は `--spec` との小さい方が使われる。0 は `--spec` 相当として扱われる（同ファイル `:9578-9582, 7892-7895, 13991-13993, 13769-13776`）。

## 実行時の動作

初期化前に、`--suffix-draft` が正で `--spec >= 2`、かつ `--mtp-max-t=0` なら、内部 cap を `--spec` に設定し、`--spec` を最大 8 まで 2 増やす。suffix drafter が MTP より長い窓を提案できるようにするためである（`engine/sycl/src/program/generate.cpp:2547-2553`）。

`--lookup-chain > 0` かつ `--spec >= 2` の場合も、cap が 0 なら内部 cap を `--spec` に設定し、検証窓 `--spec` を少なくとも `min(mtp_max_t + lookup_chain, 8)` まで広げる（同ファイル `:2554-2558`）。

実行ループでは、MTP cap `S_mtp` は正の値なら `min(mtp_max_t, spec)`、0 なら `spec` となる。MTP drafter に設定され、suffix 窓は全体の `spec` を上限として選ばれる。したがって、たとえば `--spec 6 --mtp-max-t 4` なら MTP 窓は最大 4、suffix lookup は最大 6 の範囲で選択される（同ファイル `:9578-9583, 13991-13994, 14052-14068`）。

MTP runtime がなく DFlash2 を使用する経路でも、この値から DFlash2 の draft 上限を `min(mtp_max_t, spec) - 1`（値 0 のときは `spec - 1`）として設定する。これは通常生成経路と `--serve` 起動経路の両方にある（同ファイル `:13764-13776, 7892-7903`）。サーバー起動時の engine info 行には `spec` と `mtp_max_t` が出力される（同ファイル `:9525-9534`）。

## 適用条件と副作用

- 値は生成処理の初期化時に読み込まれ、MTP / DFlash2 の draft 上限と verify window の長さに影響する。
- suffix-draft と lookup-chain の内部調整は、それぞれ有効値と `--spec >= 2` の条件を満たした場合だけ適用される。`--mtp-max-t` を正数で指定した場合、suffix-draft による自動的な `--spec` の 2 token 拡張は行われない（`engine/sycl/src/program/generate.cpp:2550-2557`）。
- MTP を使う通常経路では、cap を下げても suffix-draft による lookup window 自体は `spec` 上限まで選択可能（同ファイル `:9578-9583, 14052-14068`）。
- ソース上で明示的な上限 validation や、非数値文字列を拒否する検査は確認できなかった。parser は `atoi` の戻り値を非負化する。この文書は索引上の `strata-engine/root` に属する SYCL 実装（`engine/sycl/src/program/generate.cpp`）を調査した。他 backend の parser に同オプションがあるか、その挙動が同一かはこの checkout では確認できていない。

## 出力とエラー

値がない場合は parser が標準エラーに `--mtp-max-t needs a value` を出し、終了コード 2 で終了する（`engine/sycl/src/program/generate.cpp:1884-1887`）。未知の引数は標準エラーに `unknown argument: ...` を出し、usage を表示して終了コード 2 となる（同ファイル `:2214-2219`）。有効な値に対する専用の警告・エラー出力は確認できなかった。

## 根拠

- `engine/sycl/src/program/generate.cpp:771-772, 919, 2098` — option のフィールド、help 表示、parser と変換。
- `engine/sycl/src/program/generate.cpp:1882-1887, 2214-2219` — 引数取得、値欠落および未知引数の失敗経路。
- `engine/sycl/src/program/generate.cpp:2547-2558` — suffix-draft / lookup-chain との相互作用および `--spec` の調整。
- `engine/sycl/src/program/generate.cpp:7892-7903, 13764-13779` — `--serve` と通常生成の DFlash2 経路。
- `engine/sycl/src/program/generate.cpp:9525-9534, 9578-9583, 13991-14002` — 起動時情報と実行窓への cap 適用。
- `engine/sycl/src/program/generate.cpp:14052-14068` — MTP / suffix lookup が実際に選ぶ window の上限。

調査は上記 commit の Strata 所有ソースに限定した。GPU 実行、build、性能測定は行っていない。
