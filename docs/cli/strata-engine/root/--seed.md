# `--seed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--seed` |
| 別名 | なし |
| 値 | `S`。符号付き整数変換を経て 64-bit seed として使用 |

## 役割

通常の `strata generate` 経路でサンプリングを有効にし、Philox サンプラーへ seed を渡します。既定は argmax（greedy）です。ヘルプも `--seed S` を「この Philox seed で sampling を有効化」と説明しています（`src/program/generate.cpp:878-880`）。

この説明は `src/program/generate.cpp` の通常経路に適用されます。Qwen3.6 モデルはモデル family 判定後、通常 parser より先に専用エンジンへ分岐します。その専用 parser は `--seed` を実装していません（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3795`）。そのため Qwen3.6 では通常の `--seed` と同じ効果は確認できません。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --seed 42
```

`--tokens` は事前 token 化済みの prompt です。コマンド形式はエンジンの usage に記載されています（`src/program/generate.cpp:806-812`）。サンプリング設定を追加する場合の例:

```sh
strata generate --pack pack/full --tokens "1,2,3" --seed 42 --temperature 0.8 --top-k 20 --top-p 0.95
```

## 値と既定値

- `--seed` の後に値が必要です。値が欠けると `--seed needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2421`）。
- 値は `std::atoll` で読み、結果を `uint64_t` に変換します。seed 自体に専用の範囲検証はありません（`src/program/generate.cpp:2456`）。したがって、数値として解釈できない文字列は `atoll` の結果 0 になり、負数は unsigned 変換されます。これらを拒否する検証は確認できません。
- 省略時は `o.seed = 0` ですが `o.greedy = true` のため、既定では seed によるサンプリングをしません（`src/program/generate.cpp:418-427`）。
- 同じオプションを複数回指定した場合、parser は各指定を順に処理して値を上書きします。最後の `--seed` が seed 値を決めます（`src/program/generate.cpp:2416-2417,2456`）。

## 実行時の動作

通常経路では `--seed S` が `o.seed` を設定し、同時に `o.greedy = false` にします（`src/program/generate.cpp:2455-2457`）。後続または先行する `--greedy` は greedy を true に戻すため、両方を指定した場合は引数順が有効状態を決めます。たとえば `--seed 42 --greedy` は greedy、`--greedy --seed 42` は sampling です（同所）。

設定値は `SamplerParams` に渡されます（`src/program/generate.cpp:7043-7048`）。非 serve の起動では stderr に sampling 設定（temperature、top-k、top-p、seed）が表示されます。ただし `--greedy` が有効、または temperature が 0 以下なら `sampling greedy` と表示されます（`src/program/generate.cpp:7049-7057`）。温度、top-k、top-p は別オプションで、seed だけではその値を変更しません。temperature は有限かつ 0 以上、top-p は `(0,1]`、top-k は 0 以上である必要があり、違反すると `invalid sampling or resource parameter` を stderr に出して終了コード 2 になります（`src/program/generate.cpp:3352-3359`）。

通常の逐次生成では生成位置 `pos` をサンプラーの counter として使い、seed と位置に基づく Philox draw を行います（`src/program/generate.cpp:16034-16044`、`src/kernels/cuda/sampler.cu:56-60,427`）。投機的 decode が有効な場合も同じ `SamplerParams` が verifier に渡されます（`src/program/generate.cpp:16167-16169`）。同じモデル・入力・実行条件で seed を固定した場合のサンプリング再現を意図した実装ですが、異なる backend や実行条件をまたぐ全文生成の一致まではここでは保証しません。

## 適用条件と副作用

- sampling は `--seed` で有効になりますが、`--greedy` による上書き、または `--temperature 0` により実際の選択は greedy になります（`src/program/generate.cpp:2455-2459,7051-7057`）。
- `--serve` では起動時の CLI sampling 設定を通常の生成に使わず、各リクエストの sampling 設定を使います（`src/program/generate.cpp:7049-7051`）。テキスト要求の `seed=N` は別途 request parser で受け取り、0 または省略時には `steady_clock` の時刻値が seed として使われます（`src/program/generate.cpp:12294-12300,12349,13933-13945`）。したがって起動時 `--seed` は serve リクエストの seed 指定にはなりません。
- Qwen3.6 の専用 parser は `--serve` 以外では未知引数に usage を出して終了コード 2 とします。serve 起動時は専用 parser にない `--seed` を「not an option of this engine」と stderr に警告して、その値も読み飛ばします（`src/qwen35/q36_engine.cu:3782-3795`）。
- seed はモデル状態やファイルを変更する引数ではありません。サンプリング選択に渡される値です（`src/program/generate.cpp:7043-7048,16034-16044`）。

## 出力とエラー

- 値なし: `--seed needs a value`、終了コード 2（`src/program/generate.cpp:2418-2421`）。
- 非対応の未知引数: `unknown argument: ...` と usage を stderr に出し、終了コード 2（`src/program/generate.cpp:2787-2792`）。
- 不正な sampling/resource 値: `invalid sampling or resource parameter`、終了コード 2（`src/program/generate.cpp:3352-3359`）。この検証は seed 自体の形式を検査しません。
- 通常経路の sampling 状態は stderr に表示されます。serve では起動時の sampling 状態表示を行わず、リクエストごとに sampling 設定します（`src/program/generate.cpp:7049-7057,13933-13953`）。

## 根拠

- `src/program/generate.cpp:418-427` — 通常 parser の `Options` 既定値。
- `src/program/generate.cpp:806-812,878-880` — usage と option の説明。
- `src/program/generate.cpp:2393-2407,2416-2421,2455-2459` — Qwen3.6 への先行分岐、通常 parser、値変換、greedy との順序相互作用。
- `src/program/generate.cpp:3352-3359,7043-7057,16034-16044` — sampling 値 validation、SamplerParams 設定、通常生成での seed 使用。
- `src/program/generate.cpp:12294-12300,12325-12349,13933-13953` — serve request の seed parser と既定処理。
- `src/kernels/cuda/sampler.cu:56-60,427` — Philox seed/counter を用いる sampling draw。
- `src/qwen35/q36_engine.cu:3742-3795` — Qwen3.6 専用 parser の受理・未知引数処理。
