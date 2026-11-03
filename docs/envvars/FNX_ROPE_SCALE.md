# `FNX_ROPE_SCALE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の Flash-Next engine で Rotary Position Embedding (RoPE) に YaRN scaling を指定します。設定値 `S > 1` はモデルの訓練済み長を基準に回転周波数を YaRN で補間し、対応可能な context 上限を拡張します。`1` は環境変数が設定された profile を残したまま scaling を無効にする値です。

対象は `src/split` の sFNX engine（Flash-Next）で、通常の Strata engine 全般に適用される設定ではありません。sFNX は CUDA または HIP でビルドされ、候補一覧にある読み取りはこの engine と CUDA 用 `split_fnx_run` にあります（`src/split/CMakeLists.txt:65-80,92-120,153-165`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | engine では `FNX_ROPE_SCALE` 由来の scaling は指定しない。モデル自身の GGUF YaRN 設定があればそちらを使う。モデルにも YaRN がなければ unscaled。 |
| 空文字 | 無効。数値として parse できず、`FNX_ROPE_SCALE: '' is not a number` の例外になる。 |
| 数値として `1` | scaling off。`1`, `1.0`, `1e0` など、parse 後に double として厳密に `1.0` となる表記が該当。 |
| 数値として `1` より大きい有限値 | YaRN scale として受理。上限 clamp はない。 |
| その他 | 拒否。数値でない値は `... is not a number`、数値でも `1` 以下なら `FNX_ROPE_SCALE: want 1 (off) or a scale above 1, got ...` になる。 |

`env_num()` は全体を `strtod` で parse し、有限値であること、変換範囲外でないこと、末尾まで消費したことを確認します。先頭・末尾の空白、空文字、`inf` / `nan`、16進表記（`x` / `X` を含む）は受け付けません。符号、少数、指数表記は条件を満たせば parse されます。負値・ゼロ・`1` 未満は parse 自体に成功しても範囲判定で拒否されます（`src/split/src/env.hpp:24-30,42-49`, `src/split/src/engine_common.cu:1001-1008`）。

## 有効になる条件

- `FNX_ROPE_SCALE` が未設定で、GGUF に YaRN factor `> 1` がある場合は、モデル自身の scaling が採用されます。環境変数を unset せず `1` を指定するとモデルの YaRN と不一致になるため拒否されます。
- GGUF に YaRN factor `> 1` がある状態で環境値を設定する場合、その数値はモデル factor と一致しなければ拒否されます。環境値でモデル設定を上書きする優先順位ではありません。
- GGUF にモデル YaRN がない場合、unset または `1` は unscaled、`> 1` は環境指定の YaRN です。モデルの訓練済み長 `context_length` は必須で、scale が有効な場合でも最大 context は `max(context_length, original_context_length × S)` です。`--max-context`（既定 `262144`）がこの上限を越えると起動時に拒否されます。
- 別環境変数 `FNX_YARN_ORIG_CTX` は scale の基準長に関係します。scale が無効なのにこれを設定すると拒否されます。モデルが `original_context_length` を持つ場合はその値と一致が必要です。モデルに値がなければ、指定値は訓練済み長以下である必要があります（`src/split/src/engine.cu:41-53`, `src/split/src/rope.hpp:82-113`, `src/split/tools/sfnx.cpp:65-68,85-95`）。
- CLI `--rope-scale S` は同じ設定を指定する alias です。既に環境変数があれば引数文字列と環境値を文字列として比較し、異なる場合は拒否します（数値として等価な `2` と `2.0` も不一致）。未設定なら `setenv()` で環境に設定した後、通常の値検査を行います（`src/split/tools/sfnx.cpp:91-104`）。

## 実行時の詳細

`sfnx` は引数解析時に `rope_scale()` を呼び、モデル読込前に値の形式と `>1` / `1` の条件を検査します。Engine の構築時にも環境値を読み、GGUF の `context_length` と YaRN metadata を合わせて scaling と context 上限を決めます。YaRN が選ばれると `yarn_rope()` が回転周波数の補間帯、逆 scale、`mscale` を計算し、Engine の rotary 定数に設定します。これは graph capture より前であり、リクエストごとではありません。Engine 構築後にプロセス環境を変更しても、その Engine の rotary 設定や context 上限は変わりません。`rope_scale()` 自体は static cache を持たず、呼ぶたびに `getenv()` を評価します（`src/split/tools/sfnx.cpp:103-104,1055-1059`, `src/split/src/engine.cu:37-60`, `src/split/src/engine_common.cu:1001-1008`, `src/split/src/rope.hpp:41-66`）。

有効な scale では stderr に `fnx: rope scaling YaRN x...` が出ます。環境指定による scaling で `--max-context` が訓練済み長以内でも、全 position の rotary が変わるという note が出ます。無効値は引数解析時に `sfnx: ...` を stderr に出して exit status 2。モデルとの不一致や context 超過など Engine 構築時の失敗は stdout の `ERR ...` と stderr の `sfnx: failed: ...` を出し、status 1 で終了します（`src/split/src/engine.cu:49-60`, `src/split/tools/sfnx.cpp:1030-1035,1040-1062`）。

同梱の CUDA 用 `split_fnx_run` は `rope_scale()` の値を run identity に含め、設定値がある場合は scale 別の参照ファイル名を選びます。参照ファイルがないときは、生成例として表示するコマンド文字列に `FNX_ROPE_SCALE` と `FNX_YARN_ORIG_CTX` の代入を付けます（このツール自身がそのコマンドを実行したり、子プロセスへ値を渡したりする処理ではありません）。Strata 側で確認できるのは診断用の記録と表示までで、外部参照実装の挙動はここでは扱いません（`src/split/tools/fnx_run.cpp:398-418,831-871`）。

## 根拠

- 数値変換と unset fallback: `src/split/src/env.hpp:24-49`。
- `FNX_ROPE_SCALE` 固有の unset / `1` / `>1` 判定と例外: `src/split/src/engine_common.cu:1001-1008`。
- Engine 初期化、モデル metadata との選択、context 上限と成功ログ: `src/split/src/engine.cu:37-60`。
- モデル YaRN と環境値の優先・一致規則、original length と context limit: `src/split/src/rope.hpp:69-113`。
- YaRN 周波数・band・mscale の計算: `src/split/src/rope.hpp:41-66`。
- CLI alias、早期検査、Engine 構築と失敗出力: `src/split/tools/sfnx.cpp:91-104,1030-1062`。
- 診断ツールでの読み取り・記録・参照生成 command 組み立て: `src/split/tools/fnx_run.cpp:398-418,831-871`。
