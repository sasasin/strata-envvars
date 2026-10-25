# `--no-split-rows`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--no-split-rows` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

単一 token の CPU expert pool dispatch で、各 expert の行を pool の複数 thread に分ける既定動作を止めます。無効化すると、各 expert を一つの pool job として処理する `ExpertPool::run` 経路になります。A/B 比較用のフラグとして定義されています。処理時間や性能が改善するという保証はソースから確認できません。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-split-rows
```

`--pack` と `--tokens` はエンジンの使用法に示される必須入力例です。実際のモデルや token ID に合わせて値を指定してください。

## 値と既定値

値を取らず、指定すると真偽値 `no_split_rows` を `true` にします。省略時は `false` であり、`drive.d.split_rows = !o.no_split_rows` により行分割が有効です。同じフラグを複数回指定しても同じ真値を設定するだけです。個別の数値・文字列 validation はありません。

値を続けて書く構文ではありません。parser はこのフラグの後続 argv を消費しないため、後ろに別の未認識文字列を置くと、その文字列が通常の引数として評価され、未知引数エラーになります。

## 実行時の動作

parser は `--no-split-rows` を見つけると `Options::no_split_rows` を設定します。その後、`Drive` の `ExpertDispatch::split_rows` に反転値を渡します。単一 token の `expert_pool_dispatch` は `split_rows` が真なら `ExpertPool::run_split`、偽なら `ExpertPool::run` を呼びます。

既定の `run_split` は複数 expert の行を pool thread に分配して計算します。`run` は通常の `ExpertJob` 一覧を pool に渡し、各 job を処理します。このフラグを指定すると、後者の job 単位の dispatch が選ばれ、expert の行分割を使いません。`run_split` 自身には `n <= 0`、job 数が `kMaxSplit` を超える場合、worker 数が1の場合、または CPU oracle Q8_0 が有効な場合に `run` へ移る fallback もありますが、このオプションは常に直接 `run` を選ぶ設定です。

## 適用条件と副作用

この設定は `expert_pool_dispatch` の単一 token 経路に接続されています。ただし同関数は native pack を拒否し、native pack は verify window 側で複数 token dispatch を使う旨がソースにあります。複数 token の `expert_pool_dispatch_multi` は `ExpertPool::run_split_multi` / `run_split_multi_native` を直接呼び、`split_rows` を参照しません。そのため、このオプションが複数 token の dispatch を切り替える根拠は確認できません。Qwen35 専用 parser での受理有無も、この通常 parser の調査範囲からは確認していません。

このフラグは CPU expert pool の仕事分配方法を変えます。別の環境変数との優先順位や、ファイル・ネットワーク・プロセスへの副作用は parser と使用箇所から確認できません。性能差の計測は行っていません。

## 出力とエラー

フラグ自体の指定による専用メッセージや終了コード変更はありません。認識されない引数が別途渡された場合、parser は stderr に `unknown argument: <引数>` を出し、usage を stderr に表示して `2` を返します。

## 根拠

- `src/program/generate.cpp:639` — `no_split_rows` は `false` 初期化。
- `src/program/generate.cpp:2602` — 値を消費せず、フラグを `true` にする parser 分岐。
- `src/program/generate.cpp:6785` — `ExpertDispatch::split_rows` に反転値を設定。
- `include/strata/core/expert_source.hpp:556-557` — `split_rows` の既定値と役割のコメント。
- `src/core/expert_source.cpp:4632-4657, 4730-4742` — 単一 token dispatch と job 作成後の `run_split` / `run` 分岐。
- `src/kernels/cpu/pool.cpp:1300-1314, 1390-1408` — 行分割 run と通常 run、および run 側の batch 処理。
- `src/program/generate.cpp:2416-2423, 2787-2793` — argv の走査、未知引数の stderr・usage・終了コード。
- `src/core/expert_source.cpp:5128-5135, 5174-5180` — 複数 token dispatch が `split_rows` ではなく `run_split_multi` 系を呼ぶ箇所。
- `src/program/generate.cpp:2393-2407`、`src/core/expert_source.cpp:4648-4653` — Qwen35 family の別実装への振り分け、および単一 token 経路で native pack を拒否する箇所。

調査範囲は上記 revision の checkout にある parser と参照実装です。別 family 専用 parser、各 backend の実測性能、Release 配布バイナリでの動作は確認していません。
