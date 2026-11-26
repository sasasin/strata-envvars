# `strata generate --top-k`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--top-k` |
| 別名 | なし |
| 値 | `N`（`atoi` で整数化。CLI 側で範囲検証なし） |

## 役割

生成時のサンプリング候補を最大 `N` 個に絞る値を設定します。ただし通常の `strata generate` は既定で greedy であり、`--top-k` 単独ではサンプリングに切り替わりません。`--seed` で sampling を有効にした場合などに、CUDA sampler がこの値を使います。

## 使い方

```sh
# seed による sampling を有効にし、各 token の候補を上位 40 個にする
strata generate --pack pack/full --tokens "1,2,3" --seed 7 --top-k 40
```

## 値と既定値

- 未指定時は `20` です（`Options::top_k`）。
- 引数は `std::atoi` で変換されます。数値でない文字列は `0` になり、数値の後ろに続く非数字は変換対象外です。CLI 側では範囲や変換成否を検証しません。複数回指定すると、引数解析順で最後に代入された値が残ります。
- sampling 時、`1..63` は指定値を使い、`0`、負数、`64` 以上は候補幅 `64` として扱われます。さらに語彙数を超えないよう候補数を制限します。したがって `0` は「フィルター無効」ではなく、sampling sampler では最大幅です。

## 実行時の動作

`--top-k` は `Options::top_k` に格納され、`SamplerParams::top_k` へ渡されます。通常の生成ループは各位置の logits に対して sampler を呼び、選ばれた token を次の入力にします。候補は penalty 適用後の logits 順に選び、同点なら token ID の小さい方を先にします。その後 `top_p`、`min_p`、temperature の順で処理するため、`--top-p` と併用した場合の top-p の母集団も top-k の候補内です。

既定の `greedy=true` では greedy sampler が選ばれ、top-k は結果に使われません。`--seed S` は seed を設定すると同時に `greedy=false` にします。後から `--greedy` を指定すれば再び greedy になります（両フラグの効果は引数順に依存）。temperature が `0` 以下の場合も sampler は greedy 経路を選びます。

`--serve` では通常生成用の `SamplerParams` ではなく、各リクエストから `top_k=N` を読み込んで要求別 sampler を構成します。要求に `top_k=` がないときの要求側既定値は `20` です。このため起動引数の `--top-k` は server のリクエストごとの値を設定するものではありません。

## 適用条件と副作用

候補幅の制限は sampling 経路だけに適用されます。生成結果の token 選択を変える以外に、このオプション固有のファイル・ネットワーク等の副作用は確認できません。sampling 時の起動ログには、実効候補幅（指定値が `1..63` ならその値、それ以外は `64`）が表示されます。greedy 時は `sampling greedy` と表示され、top-k 値は表示されません。

## 出力とエラー

- `--top-k` の値の欠落時は `--top-k needs a value` を stderr に出して終了コード `2` で終了します。
- 不正な数値を専用エラーとして拒否する処理はありません。`atoi` の結果が `0` となり、sampling 経路では候補幅 `64` として扱われます。
- 未知の引数は `unknown argument: ...` と usage を出し、終了コード `2` で終了します。

## 根拠

- `engine/src/program/generate.cpp:756-765` — `Options` の既定値（greedy と top-k）。
- `engine/src/program/generate.cpp:1210-1214,1280-1283` — CLI の usage と sampling 関連引数の説明。
- `engine/src/program/generate.cpp:3842-3849,3881-3885` — 引数値の取得、`--seed` / `--greedy` と `--top-k` の解析。top-k は `atoi` を使い個別 validation を行わない。
- `engine/src/program/generate.cpp:10635-10649,24401-24408` — `Options` から sampler への引き渡し、greedy/sampling のログ、生成ループから sampler を呼ぶ箇所。
- `engine/include/strata/kernels/sampler.hpp:1-6,15-29` — sampler の既定値、sampling chain、各パラメーター。
- `engine/src/kernels/cuda/sampler.cu:337-345,384-395,446-453` — top-k の候補幅と同点規則、top-p 以降の処理順。
- `engine/src/program/generate.cpp:18824-18830,18901-18904,18951-18966,21419` — serve リクエストの `top_k=` 解析、既定値と要求別 sampler の構成・利用。
- `engine/src/program/generate.cpp:3844-3846,4268-4274` — 値欠落と未知引数のエラー処理。
