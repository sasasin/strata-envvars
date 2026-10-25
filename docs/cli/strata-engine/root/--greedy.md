# `--greedy`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（CMake で生成する推論エンジン） |
| オプション | `--greedy` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

次トークンを argmax で選ぶ greedy sampling を指定します。通常の `strata` エンジンでは既定です。`--seed` はサンプリングを有効にするため、明示的に greedy に戻す場合は `--seed` より後に `--greedy` を置きます（`src/program/generate.cpp:423,2455-2459`）。

## 使い方

トークン ID 列を入力する通常生成の例です。`MODEL_PACK` はモデルパックのパス、`IDS` はカンマ区切りの prompt token ID に置き換えます。

```sh
strata --pack MODEL_PACK --tokens IDS --greedy
```

`--tokens` と `--tokens-file` はどちらも prompt 入力ですが、同時には指定できません（`src/program/generate.cpp:2427-2443`）。

## 値と既定値

`--greedy` 自体は値を受け取りません。`Options::greedy` は初期値 `true` です。引数列を左から解析し、`--greedy` は `true` に、`--seed S` は seed を設定して `false` にします。そのため両方を指定した場合は後に現れた方が greedy フラグを決めます。繰り返し指定も拒否されず、フラグを再設定します（`src/program/generate.cpp:418-427,2416-2422,2455-2459`）。

## 実行時の動作

通常生成では `Options::greedy` が `SamplerParams::greedy` に渡されます。`--greedy` が有効、または `--temperature` が `0` 以下なら、sampler は greedy 経路を選び、非 greedy sampling 用の top-k/top-p/seed 抽選経路には進みません。正の temperature で `--seed` により greedy が無効なら sampling 経路が使われます。top-k と top-p はそれぞれ既定値 20 と 0.95 です（`src/program/generate.cpp:423-427,2455-2459,7043-7057`; `src/kernels/cuda/sampler.cu:1252-1275`）。

greedy の場合、非 serve 実行では stderr に `strata generate: sampling greedy` と表示します。serve モードではこの起動時 sampling 表示を行わず、リクエストごとの sampling 設定を扱うコードコメントがあります（`src/program/generate.cpp:7049-7057,12323-12325,13933-13942`）。

## 適用条件と副作用

Qwen3.6-35B-A3B のモデルは、条件付きで通常 parser より前に `src/qwen35` 実装へ振り分けられます。その経路でも `--greedy` は受理されますが、parser の該当分岐は何もせず、`--tokens` は元から greedy decode なので指定による追加効果はありません（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3735-3759`）。この専用 parser に渡るオプションの受理範囲は通常 parser と異なります。

このフラグ自体のファイル・ネットワーク変更はありません。GPU sampler の実装では greedy 条件を満たすと greedy kernel 経路を選びます。CUDA 以外の backend における kernel の詳細はここでは確認していません（`src/kernels/cuda/sampler.cu:1239-1264`）。

## 出力とエラー

`--greedy` は単独では validation error を発生させません。値を続けて渡す形式ではなく、後続の余分な引数は通常 parser で未知引数となり、stderr に `unknown argument: ...` と usage を出して終了コード 2 になります。値を要する別オプションで値が欠けた場合も parser は stderr に `... needs a value` を出して終了コード 2 で終了します（`src/program/generate.cpp:2416-2423,2787-2793`）。

## 根拠

- `src/program/generate.cpp:418-427` — 既定値を含む `Options` の定義。
- `src/program/generate.cpp:2393-2407` — Qwen3.6-35B-A3B 用の parser 前振り分け。
- `src/program/generate.cpp:2416-2423,2455-2459,2787-2793` — 引数の逐次解析、`--greedy` / `--seed` の相互作用、未知引数・値不足の失敗経路。
- `src/program/generate.cpp:7043-7057` — sampler 設定への反映と sampling 状態の stderr 表示。
- `src/kernels/cuda/sampler.cu:1239-1275` — CUDA sampler の greedy / sampling 経路選択。
- `src/qwen35/q36_engine.cu:3735-3759` — 専用 parser における `--greedy` の受理（no-op）。
