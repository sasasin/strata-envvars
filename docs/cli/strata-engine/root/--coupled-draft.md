# `--coupled-draft`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ `strata` 推論エンジンの root option） |
| オプション | `--coupled-draft` |
| 別名 | なし。無効化用の別 option は `--no-coupled-draft` |
| 値 | 値を取らないフラグ |

## 役割

MTP drafter が sampled request の draft token を作る際、target sampler と同じ sampler chain と Philox draw を使う coupled draft sampling を有効にします。`--help` の説明も「MTP drafter under sampling」としています。MTP のロードや spec window を単独で有効にする option ではありません。

## 使い方

モデルの MTP runtime directory と spec window を指定し、sampling を有効にして実行します。たとえば:

```sh
strata generate --pack ./model-pack --tokens "1,2,3" --mtp ./model-mtp --spec 4 --seed 1 --coupled-draft
```

この例の `--pack` と `--tokens` は `strata generate` の必須入力、`--mtp` は MTP directory、`--spec` は verify window、`--seed` は sampling を有効にする指定です。実際のモデルが MTP に対応し、指定した runtime directory を利用できる必要があります。

## 値と既定値

値を取らず、引数に現れた時点で `coupled_draft` 状態を `true` にします。未指定時の状態は `STRATA_SPEC_COUPLED` の初期値です。環境変数が未設定・空文字・文字列全体が `0` のときは無効、それ以外の値では有効です。`--coupled-draft` と `--no-coupled-draft` の両方を指定すると、引数処理順で最後に現れた方が状態を決めます。

## 実行時の動作

引数 parser はこの option を値なしで認識し、`Options::coupled_draft` を true にします。引数処理後、その状態を共有 helper に設定します。MTP bind 時に状態が有効なら coupled sampler 用の parameter、penalty history ring、scratch などを準備し、setup 成功後は stderr に有効化ログを出します。draft head が token subset の場合は token ID と subset index の対応表も作ります。

実際に coupled sampler を使うのは、MTP がロードされている経路で、要求が greedy でなく、温度が 0 より大きく、かつ `STRATA_SPEC_MIN_TEMP` 以上の場合です（`STRATA_SPEC_MIN_TEMP` 未設定時の閾値は 0）。条件を満たさない場合は通常の argmax draft 経路に残ります。coupled 経路では MTP draft が target の sampler parameter と乱数 draw を使い、verify window が draft を照合します。

`STRATA_SPEC_PROB` が有効な場合も同じ coupled setup が必要なため、CUDA/HIP 実装では `--no-coupled-draft` で CLI 状態を false にしても probabilistic draft setup は有効です。その場合、coupled draft sampling ではなく probabilistic draft sampling が選ばれます。SYCL 側 helper は `STRATA_SPEC_PROB` を coupled setup の OR 条件に含めず、挙動が異なります。

## 適用条件と副作用

- `--mtp` と `--spec`（2 以上）が有効で MTP drafter が bind される必要があります。`--mtp` は `--spec` が 2 未満だと無視される実装です。option 自体は MTP がない場合にも parser で受理されますが、その場合に coupled draft は動きません。
- `--greedy` が有効な要求、温度が 0 以下の要求、`STRATA_SPEC_MIN_TEMP` より温度が低い要求では sampled coupled drafting は有効になりません。
- setup は GPU buffer と mapped host buffer を確保し、MTP draft vocabulary subset を使う場合は逆引き token map も GPU に確保します。setup に失敗すると MTP load が失敗し、`strata generate` はエラーを stderr に出して終了コード 1 を返します。
- coupled sampler が扱える幅を超える draft logits では setup を無効のまま成功扱いにし、stderr に警告を出して argmax drafts に戻ります。

## 出力とエラー

setup 成功時は stderr に `strata mtp: coupled draft sampling on (STRATA_SPEC_COUPLED): ...` を出します。coupled buffer、token map、probabilistic buffer、device synchronize の失敗は MTP load error となり、generate 側が `strata generate: <error>` として stderr に出し、終了コード 1 で終了します。幅超過はエラー終了ではなく警告と argmax fallback です。

## 根拠

- parser、help 表示、`Options` の環境変数初期値、CLI 状態の共有 helper への反映: `src/program/generate.cpp:535,1058-1059,2552-2553,2892`。
- 環境変数の判定と `STRATA_SPEC_PROB` との合成: `include/strata/core/coupled_draft.hpp:57-83`。SYCL 側 helper が `STRATA_SPEC_COUPLED` のみを使う箇所: `sycl/include/strata/core/coupled_draft.hpp:55-69`。
- MTP が `--spec` なしでは無視される条件と load の失敗経路: `src/program/generate.cpp:5455-5472`。MTP draft head が必要な箇所: `src/core/mtp.cpp:670-675`。
- coupled setup の allocation、幅 fallback、エラー、ログ: `src/core/mtp.cpp:558-606`。MTP bind から setup を呼ぶ条件: `src/core/mtp.cpp:746`。
- sampled request と温度条件: `src/core/mtp.cpp:609-614`、閾値の既定値と環境変数: `include/strata/core/spec_prob.hpp:64-73`。
- coupled / probabilistic / argmax draft 分岐: `src/core/mtp.cpp:1199-1218`。verify round の sampler state staging: `src/core/mtp.cpp:1270-1281`。
- 索引上の配置と scope: [`docs/cli/README.md`](../../README.md) の `strata-engine` 項目。調査基準: [`001_investigation.md`](../../001_investigation.md)。

調査範囲は指定 commit の checkout 内の parser・CUDA/HIP MTP 経路・SYCL helper です。CLI help はソース内の表示文字列を参照しました。実行可能バイナリや配布 Release artifact の動作確認は行っていません。
