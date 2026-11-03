# `strata --adapt-every`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root 引数） |
| オプション | `--adapt-every` |
| 別名 | なし |
| 値 | 整数。正の値は適応ラウンドの間隔、0 以下は適応 tier を停止 |

## 役割

GPU cache に入っていない expert の routing 使用数を集計し、指定間隔ごとに、よく使われた expert と cache 内の使用頻度が低い expert の入れ替えを試みる頻度を指定します。既定値は4です。交換候補を最大いくつ扱うかは別オプション `--adapt-swaps` が担い、既定値は96です（`src/program/generate.cpp:873-880,911`）。

## 使い方

```sh
strata --native model.gguf --serve --adapt-every 8
```

この例では、適応 tier が有効な実行経路で、通常の適応ラウンドの間隔を8にします。`--serve` を使わない生成経路にも同じ root parser の値が適用されます。

## 値と既定値

- 省略時は4です（`src/program/generate.cpp:873-879`）。
- parser は値を `std::atoi` で整数化し、`--adapt-every` を明示したことも記録します。個別の範囲検証や不正値エラーはありません（`src/program/generate.cpp:3503`）。したがって、`0` と負数は後段の正数条件を満たさず、適応 tier を無効にします。整数として読めない文字列も `atoi` の結果0となり、同様に無効になります。
- 値を省略すると `--adapt-every needs a value` を stderr に出して終了コード2で終了します（共通の値取得処理 `src/program/generate.cpp:3295-3299`）。
- 同じオプションを複数指定した場合、parser はその都度値を代入するため、最後に指定した値が残ります（`src/program/generate.cpp:3503`）。
- 整数型の表現範囲を超える値の変換結果はソースで検証されていません。範囲外値の動作はここでは断定しません。

## 実行時の動作

- 適応 tier は `--adapt-every > 0` かつ `--adapt-swaps > 0` のときだけ有効です。さらに、全 expert が GPU cache に常駐している場合は routing 使用数を集計せず、入れ替えも行いません（`src/program/generate.cpp:9758,12216-12217`）。
- 有効な場合、各適応ラウンドでは各層について、未常駐 expert のうち使用数が少なくとも2の候補と、常駐 expert の候補を比較します。候補が入れ替え先より `--adapt-min-gain` 以上多く使われているものを選び、全体で最大 `--adapt-swaps` 件に制限して交換します（`src/program/generate.cpp:12490-12516`）。使用数は各ラウンド後に `--adapt-decay` の係数で減衰します（`src/program/generate.cpp:880,12941-12945`）。
- 通常の `--serve` 経路では、適応 tier が有効なら resident RAM mode の起動メッセージに交換の有効/無効が表示されます（`src/program/generate.cpp:9959-9970`）。通常の生成経路でも、集計が有効な場合は最後に交換数と間隔を出力します（`src/program/generate.cpp:20424-20426`）。
- `--spec` が2以上で `--adapt-every` を明示しなかった場合に限り、`STRATA_SPEC_ADAPT_EVERY` と `STRATA_SPEC_ADAPT_WARM` が両方正の条件を満たし、前者が既定値より小さいと、最初の指定 verify round 数の間だけ短い間隔を設定します。その後は既定間隔に戻ります。明示した `--adapt-every` はこの短縮設定を抑止します（`src/program/generate.cpp:876-879,4177-4186`）。
- `--serve --batch` の multi-GPU pipelined groups では、パイプライン中に独自の適応ラウンドは開始せず、別環境変数 `STRATA_PIPE_ADAPT_EVERY` が正の場合に限り、その値の group-window 間隔でパイプラインを空にして実行します。これは `--adapt-every` の通常間隔とは別のスケジュール条件です。また、適応 tier 自体が無効なら環境変数を設定しても実行されません（`src/program/generate.cpp:14435-14449,14687-14692`）。

## 適用条件と副作用

- 適応ラウンドは routing 使用数と residency 表を参照して expert cache の入れ替えを行います。候補がない、または交換条件を満たす expert がないラウンドでは交換は発生しません（`src/program/generate.cpp:12496-12516`）。
- `--serve --adapt-async` の非同期 tier も、`--adapt-every` と `--adapt-swaps` がともに正であることを必要とします。間隔を0以下にすると tier が停止し、非同期 tier を有効にできません（`src/program/generate.cpp:9768-9775`）。
- speculative 実行では、通常の verify round 数を間隔として数えます。serve の通常 batch path では batch window 数、pipelined group path では前述の環境変数による group-window 数で動作します（`src/program/generate.cpp:17690-17693,14008-14020,14435-14449`）。
- HIP AMD iGPU で `STRATA_IO_PREFETCH=1` かつ適応 tier が有効な場合、メモリ圧迫時に GPU reset が観測された組み合わせとして警告を stderr に出します。処理は中断せず続行します。警告は `--adapt-every 100000` での回避例にも触れますが、これは実装上の診断メッセージであり、一般的な推奨値とは確認できません（`src/program/generate.cpp:7190-7197`）。

## 出力とエラー

- このオプションの値に対する範囲エラーや警告は実装されていません。値なしの場合の stderr と終了コード2は「値と既定値」を参照してください（`src/program/generate.cpp:3295-3299,3503`）。
- 適応処理自体が失敗すると、経路に応じて `ERR an adaptive refill failed` などを出して処理を失敗させます。たとえば pipelined batch 経路ではこのメッセージを stdout に出して false を返します（`src/program/generate.cpp:14662-14667`）。serve の resident RAM 予約に失敗した場合は理由を stderr に出し、終了コード1で終了します（`src/program/generate.cpp:9959-9963`）。

## 根拠

- parser、型変換、値なしエラー: `src/program/generate.cpp:3295-3299,3503`
- 既定値・間隔の切り替え・decay: `src/program/generate.cpp:873-880,4177-4186,12934-12945`
- 適応の候補選択と交換上限: `src/program/generate.cpp:12490-12516`
- 適応 tier の有効条件、全 expert 常駐時の除外: `src/program/generate.cpp:9758,12216-12217`
- batch / speculative scheduling と独立 pipeline 環境変数: `src/program/generate.cpp:14008-14020,14435-14449,17690-17693`
- AMD iGPU 警告と失敗時出力: `src/program/generate.cpp:7190-7197,9959-9963,14662-14667`
