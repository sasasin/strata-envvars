# `--gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL 版、ルート） |
| オプション | `--gen` |
| 別名 | `-n` |
| 値 | 整数。`std::atoi` で変換する |

## 役割

`--bench` または `--spec-check` が実行する greedy decode の生成トークン数を指定する。通常のモデルロードだけでは生成処理は呼ばれず、この値はベンチマークや speculative decode の一致確認の長さとして使われる（`engine/src/inkling2/sycl/ink_sy_main.cpp:240-264`）。

## 使い方

```sh
# SYCL 版で greedy decode のベンチマークを実行し、生成数を 64 にする
strata-inkling-sycl --model ./model.strata --bench --gen 64

# 通常 decode と D-Spark decode の出力一致を 32 トークン分確認する
strata-inkling-sycl --model ./model.strata --spec-check --gen 32
```

## 値と既定値

- 省略時は `32`（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-105`）。
- `--gen` と `-n` は同じ整数変数に設定される。複数回指定した場合は、引数走査で後に現れた値が残る（同 `:112-145`）。
- 変換は `std::atoi` で、数値形式や範囲を別途検査するコードはない。不正な文字列や値なしの場合、`atoi` に空文字列または数値として読めない文字列が渡り、通常は `0` になる。同 `:114`, `:125`。
- 0 以下も parser では拒否されない。decode 関数は最初に prompt を処理して1トークンを格納してから `size < n_gen` を判定するため、`n_gen <= 0` でも内部の出力列は1トークンになる（同 `:39-53`）。一方、`--bench` の表示値 `decode_toks` は `n_gen - 1` なので負数になり得る（同 `:257-264`）。0 以下の値は通常の利用を想定した検証がありません。

## 実行時の動作

`--gen N` は `n_gen` に設定される。`--bench` は `run_greedy_decode` にこの値を渡し、通常の D-Spark 利用可否を `--no-dspark` で切り替える。`--spec-check` は同じ値で通常経路と D-Spark 経路の両方を呼び出し、各出力トークンを比較して一致数を表示する（`engine/src/inkling2/sycl/ink_sy_main.cpp:236-264`）。生成関数は prompt を一括処理して最初のトークンを得たあと、出力列が `n_gen` に達するまで追加 decode を行う（同 `:31-98`）。従って正の値では prompt に続く出力列の長さを指定し、ベンチマーク表示の `decode_toks` は最初のトークンを除いた `n_gen - 1` として数える。

この CLI では `--gen` 単独で通常のテキスト生成を開始する分岐は確認できない。`--selfcheck` は forward の診断、`--info` はモデル情報表示、`--par-sweep` は固定ステップ数の並列度測定であり、これらの処理に `n_gen` は使われない（同 `:173-180`, `:209-234`, `:267-285`）。

## 適用条件と副作用

`--gen` 自体は生成処理を有効化せず、生成数だけを渡す。生成処理を行うには `--bench` または `--spec-check` が必要で、いずれもモデル読み込みと runner 初期化を経る（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-203`, `:236-264`）。GPU 実行を伴う診断・計測の反復数に影響するが、ファイル出力やモデル設定の書き換えはこのオプションからは確認できない。

`--spec-check` は `run_greedy_decode` の戻り値を呼び出し側で検査せず、`--bench` も同様に戻り値を無視する（同 `:240-241`, `:257-260`）。decode 内部で forward が失敗すると関数は `false` を返す（同 `:41-43`, `:53-80`）が、その後の CLI 出力や終了状態への影響を `--gen` の文書化対象範囲で確定できないため、失敗時の表示は保証できない。

## 出力とエラー

`--bench` は生成数に応じて `[BENCH]` 行の `decode_toks` と `decode_tps` を計算する。`--spec-check` は `parity=<一致数>/<n_gen>` を表示し、差異があれば両方のトークン列を表示して終了コード `3` を返す（`engine/src/inkling2/sycl/ink_sy_main.cpp:243-253`, `:261-264`）。オプション値の validation error や専用の usage/error 表示は実装されていない。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:103-105` — `n_gen` の既定値。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:112-145` — 引数走査、`--gen` / `-n` の登録と `atoi` 変換、値の取得方法。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:31-98` — greedy decode の生成ループ、最初のトークンの処理、失敗時の戻り値。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:236-264` — `--spec-check` と `--bench` での利用、出力・不一致時終了コード。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-203`, `:209-234`, `:267-288` — モデル読込・runner 初期化、および `--gen` を利用しない診断経路。
- `docs/cli/README.md:1572-1590` — `strata-inkling-sycl` のルートスコープと `--gen` / `-n` の索引登録。
