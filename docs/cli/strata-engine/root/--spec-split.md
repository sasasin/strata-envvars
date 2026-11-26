# `strata --spec-split`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数） |
| オプション | `--spec-split` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

推測デコードの検証窓に2群の分割実行を opt-in します。検証窓の前半群の expert 計算中に、GPU が後半群の mixer/router を進められるよう処理順を重ねます。ソースコメントではトークンごとの算術は変えない設計と説明されていますが、オプション定義は分割あり・なしでビット単位に同一とは限らず、分割窓の batch shape が異なるとしています。

## 使い方

```sh
# 推測デコードを有効にし、検証窓を分割する
strata --model model.gguf --draft draft.gguf --spec 4 --spec-split
```

`--spec-split` 自体は引数を消費しません。標準 parser では後続に `--no-spec-split` を置くと無効化できます。

## 値と既定値

- `Options::spec_split` の初期値は `false` です。`--spec-split` を読むと `true`、`--no-spec-split` を読むと `false` に設定します（`engine/src/program/generate.cpp:1069,4064,4196`）。
- 数値や文字列の値を取らず、個別の値 validation はありません。指定順に parser が処理するため、両方を指定した場合は最後に現れた方が有効です（同 `engine/src/program/generate.cpp:3838-3847,4064,4196`）。
- SYCL 実装にも同じ初期値、真偽フラグ、および解除フラグがあります（`engine/sycl/src/program/generate.cpp:706,2057,2160`）。

## 実行時の動作

通常の生成経路と `--serve` 経路の両方で、parser の値を verifier の `set_split()` に渡します（`engine/src/program/generate.cpp:13702,24542`）。`record_window()` は `--spec-split` が有効で検証対象が2トークン以上なら、batch 再構成中でない検証窓を2群に分けます。群 A は `[0, ceil(T/2))`、群 B は残りです。各群は層ごとの mixer/router と expert 処理の順を交互に進め、CPU 側の expert 計算と GPU 側の処理を重ねられる構成です（`engine/src/core/verify.cpp:1460-1467,1484-1486,1520`）。

batch 再構成中でない検証窓は、長さが `kVerifyMaxT` を超える場合、フラグがなくても2群になります。`batch_rec_` が有効な再構成窓では `--spec-split` による2群化条件は適用されません（`engine/src/core/verify.cpp:1484-1486`）。したがって、このフラグは通常の生成経路で実際に複数トークンを含む推測検証窓に効果を持ちます。

## 適用条件と副作用

- デフォルトは無効です。推測候補を検証する窓が1トークンだけなら `T >= 2` の条件を満たさず、このフラグによる分割は起きません（`engine/src/core/verify.cpp:1484-1488`）。
- 同じ逐次窓の `STRATA_ADAPT_FETCH` による適応的 expert fetch とは併用されません。`fetch_off` の判定で `o.spec_split` が無効理由として選ばれ、`STRATA_ADAPT_FETCH` が有効な場合は stderr に不使用理由が出ます。判定は residency table、expert cache の slot 数の後に `--spec-split` を確認し、その後に layer split 等を確認します（`engine/src/program/generate.cpp:15055-15076,24571-24589`）。
- ビルドや GPU 上の所要時間、特定モデルでの性能差はこの調査では実行していません。ソースコメントには overlap study で約7%遅いとの記載がありますが、測定条件をこの文書では独立に検証していません（`engine/src/program/generate.cpp:1069`）。

## 出力とエラー

このフラグ固有の値 validation やエラー分岐はありません。認識されない引数は `unknown argument: ...` を stderr に出して parser が終了コード `2` を返します（`engine/src/program/generate.cpp:4268-4273`）。`STRATA_ADAPT_FETCH` が有効でこの設定により利用されない場合の stderr メッセージは前節のとおりです。

## 根拠

- `engine/src/program/generate.cpp:1069,4064,4196` — 既定値、parser 登録、解除フラグ。
- `engine/src/program/generate.cpp:13702,24542` — `--serve` と通常生成の verifier への反映。
- `engine/src/core/verify.cpp:1460-1467,1484-1488,1520` — 分割窓の意図、2群を選ぶ条件と群境界。
- `engine/src/program/generate.cpp:15055-15076,24571-24589` — `STRATA_ADAPT_FETCH` が不使用になる条件と stderr 出力。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数の失敗経路。
- `engine/sycl/src/program/generate.cpp:706,2057,2160,7963-7982` — SYCL parser と verifier への反映。

調査範囲は上記 checkout の Strata 所有ソースです。実行バイナリの help 表示、build、GPU 実行、性能測定は行っていません。
