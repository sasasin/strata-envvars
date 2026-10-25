# `--max-context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` エンジンのトップレベル生成コマンド |
| オプション | `--max-context` |
| 別名 | なし |
| 値 | 整数 `N`。KV/状態の最大セル数（context capacity） |

## 役割

生成セッションが保持できるコンテキストの上限を指定します。prompt と生成分を収容する必要があり、この容量に応じてセッション状態（主に KV）のサイズと、生成が続けられる位置が決まります。モデルが学習した context 長や RoPE scaling の指定そのものではありません（parser と既定値: `src/program/generate.cpp:418-423, 866-875`）。

## 使い方

```sh
strata --pack /path/to/model-pack --tokens 1,2,3 --max-new 128 --max-context 8192
```

`--tokens` にはモデルの語彙範囲にある token ID を指定します。`--pack` は利用するモデル pack のパスです。例の値は構文例であり、モデル・GPU に対する推奨値ではありません。

## 値と既定値

- 省略時は `4096` です（`src/program/generate.cpp:418-423`）。
- 値は `std::atoll` で `int64_t` に読み取られます。値を省略すると `--max-context needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:2416-2421, 2444-2446`）。数値文字列の厳密な全体検査はこの parser にはありません。数値として読み取れず `0` になった値は後段の正数検査で拒否されます。
- 有効な範囲は `1` 以上 `2147483639` 以下です。上限を超えると `strata generate: --max-context must be below 2^31`、0 以下は `strata generate: positive --max-new and --max-context must fit the prompt and generation` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:3302-3310`）。
- 同じオプションを複数回指定した場合、parser は出現ごとに同じフィールドへ代入するため、後の値が残ります（`src/program/generate.cpp:2416-2421, 2444-2446`）。

## 実行時の動作

- 起動時に `--max-new` が正で、`--max-new <= --max-context`、かつ prompt token 数が `--max-context - --max-new` 以下であることを検査します。満たさない場合は上記の正数・収容エラーで終了コード `2` になります（`src/program/generate.cpp:3307-3310`）。後段にも prompt と生成上限を合わせた収容検査があり、失敗時は `--max-context N cannot hold P prompt + M new tokens` を stderr に出して `2` を返します（`src/program/generate.cpp:3970-3973`）。
- `session_bytes` はこの値を使ってセッション arena の必要量を算出し、QSA state と関連 buffer のサイズにも渡します。通常経路ではそのサイズを `cudaMalloc` し、`session_init` に同じ容量を渡します。割当失敗は `session state allocation failed`、初期化失敗は `session_init failed` を stderr に出して終了コード `1` です（`src/core/session.cpp:56-75, 77-109`; `src/program/generate.cpp:5215-5221`）。layer split 時も各 GPU の担当層ごとに同容量を元に状態を確保します（`src/program/generate.cpp:5251-5253`）。
- この容量は VRAM の空き計算にも使われます。expert cache 用の容量が確保できない診断では、セッションが `N` token 分に必要とする MiB とともに、より小さい `--max-context` が対処候補として stderr に表示されます（`src/program/generate.cpp:6182-6202`）。実際に必要なメモリ量はモデル形状、KV 形式、layer 分割などに依存します。
- 生成中は容量端で通常の生成を止め、`strata generate: ran out of context at position ...` を stderr に出して終了コード `2` を返す経路があります（`src/program/generate.cpp:15873-15879`）。連続バッチでは prompt + `max_new` に加えて 8 token の余裕を要求し、満たさない request は `ERR ... exceeds the context ...` を stdout に返してその request を処理しません（`src/program/generate.cpp:12485-12489`）。
- `--kv-grow` を有効にしたときも最大容量そのものは変わりません。コメント上、KV は到達したセルに応じて物理メモリを増やしますが、指定した全セルは引き続き収容可能です（`src/program/generate.cpp:7853-7859, 7885-7891`）。

## 適用条件と副作用

- `--native-flash-attn-short` との併用では `--max-context <= 256` が必須です。超える場合は stderr に要件を出し、終了コード `2` で終了します（`src/program/generate.cpp:3378-3380`）。
- `--rope-scaling` が有効な場合、起動時の診断に指定容量とモデルの学習済み context 長が出ます。容量が学習済み長以下なら extension は不要という注記も出ますが、scaling の設定は角度全体に適用されます。`--max-context` が scaling の方式やモデル側の学習済み長を自動変更する処理は確認できません（`src/program/generate.cpp:3732-3743`）。
- Vision 経路では位置テーブルも `max_context + 64` cells 分作られ、確保・転送に失敗すると `cannot allocate the image position table` を stderr に出して終了コード `1` です（`src/program/generate.cpp:3942-3955`）。
- session の構成には KV 形式なども関係します。たとえば session 設定 fingerprint に `max_context` と KV 設定が記録されるため、session 再利用の同一性にも容量が含まれます（`src/program/generate.cpp:9432-9447`）。

## 出力とエラー

- 値の範囲や prompt/generation 容量の不整合は stderr、終了コード `2` です（`src/program/generate.cpp:3302-3310, 3970-3973`）。
- context を使い切った通常の生成は stderr、終了コード `2` です。serve 互換の起動経路では準備完了時に stdout へ `READY N stop` を出し、context 上限もクライアントに通知します（`src/program/generate.cpp:11166-11169, 15873-15879`）。
- GPU の session allocation/initialization や Vision 位置テーブル確保の失敗は stderr、終了コード `1` です（`src/program/generate.cpp:3947-3955, 5215-5221`）。

## 根拠

- parser と既定値: `src/program/generate.cpp:418-423, 2416-2421, 2444-2446, 866-875`
- 値検査と prompt の収容条件: `src/program/generate.cpp:3302-3310, 3970-3973`
- 容量に基づく session 計算・初期化: `src/core/session.cpp:56-75, 77-109`; `src/program/generate.cpp:5215-5221, 5251-5253`
- context 終端とバッチ request: `src/program/generate.cpp:12485-12489, 15873-15879`
- 他 option・副作用との関係: `src/program/generate.cpp:3378-3380, 3732-3743, 3942-3955, 7853-7891, 9432-9447`

索引の対象は `strata-engine/root` です。同名オプションは別 parser スコープにもありますが、この文書では索引が指定する `src/program/generate.cpp` のトップレベル生成 parser のみを扱います（`docs/cli/README.md:1199, 1339, 1373`）。同一 revision の既存 CLI help は実行しておらず、help に書かれた説明は補助資料として照合していません。
