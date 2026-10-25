# `--max-new`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの通常 parser。通常生成は `strata generate` として案内される） |
| オプション | `--max-new` |
| 別名 | なし |
| 値 | 生成する新規トークン数 `N`（整数） |

## 役割

通常 parser で、プロンプトの後に生成する新規トークン数の上限を指定します。指定数に達する前でも、`--stop-eos` が有効で生成した token ID が EOS ID に一致すれば生成を終えます。トークン数は生成ループで確認され、通常生成・投機生成のどちらも上限まで出力したところで止まります（`src/program/generate.cpp:16076-16083`、`src/program/generate.cpp:16531-16533`、`src/program/generate.cpp:16680-16693`）。

## 使い方

```sh
strata --tokens-file prompt.tokens --max-new 64
```

エンジンの usage は `strata generate --pack DIR --tokens ... [options]` の形で案内され、`--max-new N` を「生成する tokens」と説明しています。プロンプトは `--tokens` または `--tokens-file` で事前トークン化した ID を渡します（`src/program/generate.cpp:806-812`、`src/program/generate.cpp:865`、`src/program/generate.cpp:2426-2444`）。

## 値と既定値

- 通常 parser の初期値は `16` です（`src/program/generate.cpp:418-423`）。
- 値は `std::atoll` で読み取られます。専用の重複指定チェックはなく、引数走査中に後から指定した値が同じフィールドを更新します（`src/program/generate.cpp:2416-2421`、`src/program/generate.cpp:2444`）。
- 通常 parser では `N > 0`、`N <= --max-context`、かつ prompt token 数が `--max-context - N` 以下であることが必要です。違反時は stderr に `positive --max-new and --max-context must fit the prompt and generation` を出し、終了コード `2` で終了します（`src/program/generate.cpp:3302-3310`）。後段にも prompt と生成数の合計を確認する検査があります（`src/program/generate.cpp:3970-3974`）。
- `--max-context` の既定値は `4096` です（`src/program/generate.cpp:421-423`）。そのため、既定値の `--max-new 16` は prompt と合わせて context に収まる必要があります。

## 実行時の動作

通常生成では、prompt 最終位置から予測した token を最初の生成 token として数え、その後の token も含めて `N` 個まで保持します。標準出力の生成列が `N` 個に達するとループを終えます。`--stop-eos` を併用した場合は、EOS ID を出力した時点でも先に終了できます（`src/program/generate.cpp:16076-16083`）。投機生成では残りの上限を超えない範囲で候補 token を追加し、上限到達後は次の投機 window を開始しません（`src/program/generate.cpp:16531-16533`、`src/program/generate.cpp:16680-16693`）。

`--logits-stride` を `1` より大きくする場合は、`--max-new 1` と `--dump-logits` の両方が必要です。条件違反は stderr のエラーとなり、終了コード `2` です（`src/program/generate.cpp:3286-3289`）。

`--serve` では、`--tokens` がなければエンジン起動処理が内部 prompt と `max_new = 1` を設定します。その後の各要求は `GEN <max_new> ...` 行で個別の生成上限を指定するため、起動時の `--max-new` は要求ごとの上限として使われません（`src/program/generate.cpp:3168-3173`、`src/program/generate.cpp:12287-12296`）。要求値は正数である必要があり、prompt と上限の合計に 8 token の余裕を加えた値が `--max-context` を超えると、stdout に `ERR prompt ... exceeds the context ...` を返してその要求を拒否します（`src/program/generate.cpp:12383-12388`、`src/program/generate.cpp:12485-12488`）。

## 適用条件と副作用

この説明は通常 parser の値規則です。Qwen3.6 アーキテクチャを持つモデルでは、モデル header を読んで `src/qwen35/q36_engine.cu` の専用 parser に分岐します（`src/program/generate.cpp:2393-2407`）。その parser は `--max-new` を `int` の `n_gen` に `std::atoi` で代入し、既定値を `64` とします。同じ実行内で後続の `--n` があれば同じ値を更新し、`--force` の非空値があれば生成数を forced token 数 + 1 に置き換えます（`src/qwen35/q36_engine.cu:3735-3738`、`src/qwen35/q36_engine.cu:3748-3760`、`src/qwen35/q36_engine.cu:3916-3918`）。この family 専用 parser の詳細は [`strata-engine` Qwen3.6 の `--max-new`](../qwen36/--max-new.md) を参照してください。

ソース上、このオプション自体は生成 token 数を制御します。ファイルやネットワークへの副作用は確認できません。生成処理は GPU 推論を行いますが、ここでは実行・性能測定をしていません。

## 出力とエラー

通常 parser では値の欠落時に `--max-new needs a value` を stderr に出して終了コード `2`、値や prompt/context 条件の不適合時にも stderr の診断と終了コード `2` になります（`src/program/generate.cpp:2418-2421`、`src/program/generate.cpp:3307-3310`）。`--serve` 中の不正な要求はプロセス全体を終了せず、stdout に `ERR bad request: max_new` または context 超過を示す `ERR` 行を返して次の入力を処理します（`src/program/generate.cpp:12383-12388`、`src/program/generate.cpp:12485-12489`）。

## 根拠と調査範囲

- 通常 parser の既定値、値取得、usage: `src/program/generate.cpp:418-423`、`src/program/generate.cpp:806-812`、`src/program/generate.cpp:865`、`src/program/generate.cpp:2416-2445`
- 通常 parser の検証と相互作用: `src/program/generate.cpp:3286-3310`、`src/program/generate.cpp:3970-3974`
- 生成上限と EOS 条件: `src/program/generate.cpp:16076-16083`、`src/program/generate.cpp:16531-16533`、`src/program/generate.cpp:16680-16693`
- `--serve` の起動時補正と要求ごとの値: `src/program/generate.cpp:3168-3173`、`src/program/generate.cpp:12287-12296`、`src/program/generate.cpp:12383-12388`、`src/program/generate.cpp:12485-12489`
- Qwen3.6 への分岐・専用 parser: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3760`、`src/qwen35/q36_engine.cu:3916-3918`

調査は上記 commit の checkout の parser、実使用箇所、family 分岐に基づきます。Release 配布物や実行バイナリの `--help` との照合は行っていません。
