# `--draft-vocab`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 専用 parser） |
| オプション | `--draft-vocab` |
| 別名 | なし |
| 値 | 整数 `N`。MTP draft が候補にする先頭 `N` 個の token ID の範囲 |

## 役割

Qwen3.6 の MTP draft head が次 token の提案を行うとき、通常の出力語彙のうち先頭 `N` 個の ID に候補を限定します。これは draft の候補選択だけに適用され、検証 window が採用する本回答の greedy token は制限しません。MTP が有効でない実行では draft head が呼ばれず、この値は使われません。

## 使い方

```sh
# Qwen3.6 GGUF の MTP draft 候補を先頭 120000 token ID に制限して入力 ID を生成する
strata-q36 --model /path/to/qwen36.gguf --tokens '1,2,3' --mtp 2 --draft-vocab 120000
```

`--tokens` の値は token ID 列です。`--mtp` は GGUF 内の MTP block で行う draft 数を指定します。モデルに MTP block がない場合は MTP draft 数が 0 になり、このオプションも draft 処理に影響しません。

## 値と既定値

- parser は `--draft-vocab` の次の引数を `std::atoi` で整数化します。範囲や数値形式の検証はありません。不正な文字列や空文字列は `atoi` の結果 `0` となり、整数の前置部分だけが数値ならその部分が使われます。
- 未指定時の内部値は `-1` です。環境変数 `STRATA_Q36_DRAFT_VOCAB` が設定されていればその値を読み、最終的に `max(0, 値)` を `draft_n` にします。環境変数もなければ `draft_n` は `0` です。
- `draft_n == 0` は語彙全体を候補にする動作です。負の CLI 値は、環境変数が設定されていれば環境変数値へのフォールバックを発生させ、そうでなければ 0 に丸められます。
- 明示した 0 以上の CLI 値は環境変数より優先されます。複数回指定した場合は parser の逐次代入により最後の値が残ります。

## 実行時の動作

`--mtp N` が正で、モデルに MTP block があるとき、MTP の最終行を draft として処理する経路から draft head が呼ばれます。`draft_n` が `0` 以下、語彙数以上、または 8 の倍数でない場合は通常の全語彙 head 計算へ戻ります。さらに fast-kernel が無効、head の型・次元が適合しない場合も同じ全語彙経路です。条件を満たす場合は出力行列の先頭 `draft_n` 行だけを計算し、その範囲で argmax して draft token を選びます。

限定は draft proposal にだけ及びます。draft token が検証で不採用になっても、本回答は通常の greedy 結果を維持します。したがって、値が語彙数未満でも最終回答の token ID を切り捨てる指定ではありません。

## 適用条件と副作用

この引数は `strata-engine` の Qwen3.6 parser (`strata` family switch 後または `strata-q36` 実行ファイル) のスコープです。通常の `strata-engine/root` にある別 CLI 文書とは異なる parser 階層です。MTP block と draft 実行が必要で、MTP が無効なら候補計算への効果はありません。値によるファイル変更や永続化は行いません。コードは draft head の候補計算だけを変え、性能上の効果量は保証していません。

## 出力とエラー

値を省略してオプションを末尾に置くと、stderr に `strata-q36: --draft-vocab needs a value` を出して終了コード 2 で終了します。数値として不正な値や範囲外の値に対する専用エラーはなく、`atoi` と上記の分岐・丸めに従います。

## 根拠

- `engine/src/qwen35/q36_engine.cu:5345` — `draft_vocab` の初期値 `-1`。
- `engine/src/qwen35/q36_engine.cu:5350-5353` — 引数値の取得と、省略時の stderr / 終了コード 2。
- `engine/src/qwen35/q36_engine.cu:5373-5380` — `--mtp` と `--draft-vocab` の parser、整数変換。
- `engine/src/qwen35/q36_engine.cu:5556-5559` — モデルに MTP block がある場合の draft 数、`STRATA_Q36_DRAFT_VOCAB` のフォールバック、`draft_n` の非負化。
- `engine/src/qwen35/q36_engine.cu:3054-3077` — draft head の候補範囲、全語彙へ戻る条件、先頭行だけを処理する経路。本回答は検証 window が決めるという説明も含む。
- `engine/src/qwen35/q36_engine.cu:3083-3094` — MTP forward の draft 経路から `head_draft` を呼ぶ条件。
- `docs/cli/README.md:1240-1249` — `strata` / `strata-q36` の Qwen3.6 parser 階層と対象リンク（索引の配置確認用）。

範囲外: 実行バイナリでの help 表示や GPU 実行は行っていません。性能差と、外部環境変数の設定方法はこの parser のソースからは評価していません。
