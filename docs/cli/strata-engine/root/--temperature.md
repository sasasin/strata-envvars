# `--temperature`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（CMake で生成する推論エンジン） |
| オプション | `--temperature` |
| 別名 | なし |
| 値 | 数値文字列を `std::atof` で `float` に変換 |

## 役割

通常の推論 engine の token sampling 温度を設定します。sampling 経路では top-k / top-p で候補を絞った後、候補 logits を温度でスケールして次 token を選びます。ただし、温度を指定しただけでは sampling は有効になりません。`--seed` などで greedy を解除する必要があります（`src/program/generate.cpp:423-427,2455-2459,7043-7057`; `src/kernels/cuda/sampler.cu:383-417`）。

## 使い方

モデル pack と prompt token ID を指定する通常生成の例です。値は実行環境に合う正の温度に置き換えます。

```sh
strata --pack MODEL_PACK --tokens 1,2,3 --seed 42 --temperature 0.7
```

`--seed` は sampling を有効にします。`--temperature` を指定しても `--seed` を省略すると、初期値の greedy が有効なままです（`src/program/generate.cpp:423-427,2455-2459`）。

## 値と既定値

- 値を1つ取ります。`std::atof` で `float` に変換し、重複指定は拒否されず後の値が使われます（`src/program/generate.cpp:2416-2422,2459`）。
- 省略時の値は `1.0f` です。値は有限で `0` 以上でなければならず、負数、NaN、正負の無限大などは sampling/resource parameter の共通検証で拒否されます。検証失敗時は stderr に `strata generate: invalid sampling or resource parameter` を出して終了コード 2 です（`src/program/generate.cpp:427,3352-3359`）。
- `atof` による変換のため、整数専用の形式ではありません。個別の厳密な数値文字列検査はありません。値を省略した場合は stderr に `--temperature needs a value` を出し、終了コード 2 で終了します（`src/program/generate.cpp:2418-2420,2459`）。

## 実行時の動作

通常生成では `Options` の greedy 状態、seed、top-k、top-p、温度が sampler parameter に渡されます。初期状態は `greedy=true`、`seed=0`、`top_k=20`、`top_p=0.95`、`temperature=1.0` です。`--seed S` は seed を設定して同時に greedy を解除し、`--greedy` は greedy を有効にします。引数を左から読むため、両方を指定した場合は後に現れた方が greedy 状態を決めます（`src/program/generate.cpp:418-427,2416-2422,2455-2459,7043-7048`）。

sampler は `greedy` が有効、または温度が `0` 以下の場合に argmax 経路を選びます。したがって正の温度でも `--seed` より後に `--greedy` を置くと greedy のままです。温度 `0` は受理されますが greedy になります。sampled 経路では top-k、top-p の候補選別後に温度を適用し、Philox seed と token position の counter で抽選します（`src/kernels/cuda/sampler.cu:383-417,1252-1275`; `src/program/generate.cpp:16034-16044`）。

`--serve` では起動時の `--temperature` を各 request の sampling に使いません。`GEN` / `GENI` request の `temperature=F` が request 用温度で、未指定時は `0.0f`（greedy）です。root オプションの値を request に設定する処理は確認できません（`src/program/generate.cpp:7049-7057,12294-12300,12325-12343,13933-13946`）。

## 適用条件と副作用

- `--native` または `--model` が Qwen3.6-35B-A3B の GGUF を指す場合、通常 parser より前に `src/qwen35` の専用実装へ切り替わります。その専用 parser は通常の非 serve 実行で `--temperature` を受け付けず、usage を stderr に出して終了コード 2 になります。serve mode が `--temperature` より前に処理されていれば、知らない `--` option として警告して値を読み飛ばします。Qwen3.6 request の温度は request key 側で別途処理されます（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3735-3759,3782-3795,3013-3016,3464`）。
- この option 自体がファイルやネットワークを変更する処理はありません。非 serve 実行では、実際の sampler 設定に応じて stderr に `strata generate: sampling greedy` または温度・top-k・top-p・seed を含む状態行を出します（`src/program/generate.cpp:7049-7057`）。
- sampler の起動に失敗すると stderr に `sample_tokens launch: ...` を出し、終了コード 1 で終了します。これは温度専用の検証経路ではありません（`src/kernels/cuda/sampler.cu:1291-1295`）。

## 根拠

- `src/program/generate.cpp:418-427` — engine option の初期値。
- `src/program/generate.cpp:2393-2407` — Qwen3.6-35B-A3B への parser 前振り分け。
- `src/program/generate.cpp:2416-2422,2455-2459,2787-2793` — 値の取得、逐次 parsing、greedy / seed との相互作用、未知 option の失敗経路。
- `src/program/generate.cpp:3352-3359` — 温度を含む有限値・範囲 validation とエラー終了コード。
- `src/program/generate.cpp:7043-7057` — sampler への設定反映と stderr 状態表示。
- `src/program/generate.cpp:12294-12300,12325-12343,13933-13946` — serve request の温度既定値、request key の parsing、request sampler の設定。
- `src/program/generate.cpp:16034-16044,16166-16170` — 通常生成と verifier sampling での適用。
- `src/kernels/cuda/sampler.cu:383-417,1240-1295` — 候補選別後の温度適用、greedy / sampled 経路選択、kernel 起動失敗。
- `src/qwen35/q36_engine.cu:3735-3759,3782-3795` — 専用 parser での非 serve unknown option と serve 時の無視。
