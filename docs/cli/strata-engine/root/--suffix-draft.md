# `--suffix-draft`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。トップレベル） |
| オプション | `--suffix-draft` |
| 別名 | なし |
| 値 | 整数 `N`。照合する文脈の最小一致長を指定する。既定値は `3`。 |

## 役割

生成中の文脈末尾が、それ以前の文脈と一致したとき、以前の一致箇所に続く token を speculative verification 用の候補として提案します。コード編集や引用など、既出テキストの続きを生成する場面で候補になり得ます。候補を使うかは一致長だけでは決まらず、ドラフトの受理状況と検証窓の測定コストを使う `DraftPolicy` が選びます。

## 使い方

```sh
# prompt lookup を無効化し、MTP のドラフトだけで生成する
strata --pack MODEL --suffix-draft 0

# 既定値（3 token 以上の一致）で一度の生成を行う
strata --pack MODEL --suffix-draft 3

# server モードでも同じ設定を使う
strata --pack MODEL --serve --suffix-draft 3
```

`MODEL` は利用するモデル pack のパスに置き換えます。

## 値と既定値

- 省略時は `3` です。parser は `std::atoi` で値を整数化し、`std::max(0, ...)` により負数を `0` にします。`0` は suffix drafting を無効にします。parser に正の上限値チェックはありません。`engine/src/program/generate.cpp:1156-1160,4121`。
- parser は非数値の文字列を個別に拒否せず、`atoi` の結果を使います。先頭を数値として読めない値は `0` となり無効化と同じ扱いです。値を省略すると `next` が stderr に `--suffix-draft needs a value` を出し、終了コード `2` で終了します。`engine/src/program/generate.cpp:3844-3846,4121`。
- 重複指定は parser が順に代入するため、最後に指定した値が残ります。`engine/src/program/generate.cpp:3842-3848,4121`。
- 実際の matcher は最小一致長を少なくとも `3` にします。そのため `N=1` や `N=2` でも 1〜2 token の一致だけでは提案しません。構築時の `max_match` は `max(N, 64)` です。`engine/src/program/generate.cpp:16410`, `engine/src/spec/suffix_drafter.cpp:18-24,64-81`。

## 実行時の動作

`--suffix-draft` が正で、`--spec` が `2` 以上、かつ `--mtp-max-t` が `0` の場合、エンジンは MTP の窓を元の `--spec` に保ちつつ、検証窓の `--spec` を最大 2 token、上限 8 まで広げます。`--mtp-max-t` を明示した場合はこの自動設定を行いません。`--lookup-max-t` が有効なら、その値とビルドの上限に応じてさらに lookup 窓の上限を設定します。窓の実際の幅や利用可能な graph は build・実行条件に依存します。`engine/src/program/generate.cpp:5033-5039,5079-5098`。

生成時には prompt と、確定した生成 token を履歴へ追加します。履歴末尾と同じ trigram を持つ過去位置を候補にし、その位置から遡って最長一致を探します。一致長が `N` 以上なら、その直後の token 列を最大要求数まで提案します。候補がない、一致が短い、または提案長が 0 の場合は提案しません。`engine/src/spec/suffix_drafter.cpp:51-61,64-85`。

提示した token 列はそのまま出力に確定するのではなく、通常の verifier の候補です。`DraftPolicy::choose` は lookup と MTP の期待受理 token 数を窓コストで割って比較し、lookup 側が margin を超えた場合などに lookup 窓を選びます。MTP の決定的な経路では先頭候補が MTP の先頭予測と一致することも条件です。確率的 MTP の経路にはその一致条件を課さず policy で選ぶ分岐があります。したがって `N` を下げても毎回 lookup が使われるわけではありません。`engine/src/spec/draft_policy.cpp:577-615`, `engine/src/program/generate.cpp:22712-22735`。

`--suffix-draft 0` は suffix 候補の使用条件を無効にします。ただし `--lookup-chain` は別の opt-in 経路であり、suffix drafting を `0` にしても `--lookup-chain` 自体が無効になるとは限りません。`engine/src/program/generate.cpp:1163-1165,21665-21672,22073-22079`。

## 適用条件と副作用

この値はモデルやファイルを変更せず、生成中の token 履歴と検証窓に作用します。MTP／speculative generation が使われる経路で、最初の窓を過ぎてから suffix 候補を調べます。server では request の token history から候補を作ります。履歴の token index と固定サイズ hash table を保持するため、プロセス内で CPU 側のメモリを使います。`engine/src/program/generate.cpp:21665-21669,22714-22735,24903-24907`, `engine/src/spec/suffix_drafter.cpp:18-24,51-61`。

候補の採用は verifier の窓サイズにも影響し、その窓用 graph が実行環境で利用できない場合は `--lookup-max-t` 経路で適合する幅を求めます。source ではビルド別の verify 上限を使って窓を制限し、`--spec` が範囲外なら `strata generate: --spec ...` を stderr に出して終了コード `1` で終了します。`engine/src/program/generate.cpp:5079-5098,22737-22741`。

## 出力とエラー

`--suffix-draft` 専用の値範囲エラーはありません。値の欠落は parser で stderr と終了コード `2`、不正な数値表記は `atoi` による変換後の値（通常は `0`）として処理されます。正の値で実行した場合、生成終了時に suffix draft の窓数と受理数を表示します。通常生成では stdout、server では stderr です。server 起動時の `INFO` 行にも設定値を含めます。`engine/src/program/generate.cpp:3844-3846,4121,16200-16213,23924,25272-25274`。

## 根拠

- `engine/src/program/generate.cpp:1156-1162,1343-1345,4121` — 既定値、help 表示、parser と近接する MTP／lookup options。
- `engine/src/program/generate.cpp:5033-5039,5079-5098` — 既定の窓拡張、`--lookup-max-t` との相互作用、窓上限と失敗経路。
- `engine/src/program/generate.cpp:21665-21669,22073-22086,22712-22735,24903-24907,25272-25274` — server／単発生成での履歴登録、候補採用条件、統計出力。
- `engine/src/spec/suffix_drafter.cpp:18-24,51-85` — matcher の下限、履歴 index、最長一致探索、提案 token の取得。
- `engine/src/spec/draft_policy.cpp:577-615` — MTP と lookup の選択条件。
