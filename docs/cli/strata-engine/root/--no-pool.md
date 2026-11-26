# `--no-pool`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（SYCL エンジン） |
| オプション | `--no-pool` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると有効 |

## 役割

CPU expert pool を使わず、GPU 側だけの経路を実行する診断用フラグです。通常の expert pool を用いた生成と同じ結果を得る設定ではありません。`--no-capture` と組み合わせると、CPU expert pool の hook がない `session_token` 経路を明示的に選ぶ条件を満たします。parser は `Options::no_pool` を `false` で初期化し、このフラグを読むと `true` にします（`engine/sycl/src/program/generate.cpp:530,941,1970`）。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens "1,2,3" --no-pool
```

この例は GPU-only の診断経路を指定します。pack と token 入力は `strata generate` の必須入力です（`engine/sycl/src/program/generate.cpp:802-806`）。

## 値と既定値

値は不要です。省略時は `no_pool == false` で、指定時は `true` になります。数値や文字列の validation はありません。同じフラグを複数回指定しても同じ真偽値を代入するだけです。値を続けて書く構文はありません（`engine/sycl/src/program/generate.cpp:530,1970`）。

## 実行時の動作

parser が値を保持し、実行準備時に `pool_fn` と `pool_user` を null にします。また `hit_fn` も null になり、VRAM expert cache の hit 計算 hook は使われません（`engine/sycl/src/program/generate.cpp:5933-5938`）。`session_loop` は GPU の doorbell を待つ一方、pool 関数は null でない場合に限って呼びます（`engine/sycl/src/core/session.cpp:995-1016`）。このため routed expert の CPU 計算を省いた診断経路となり、通常の expert pool を使ったモデル生成と結果が同等であることは保証されません。

実行時には pool worker 数を stderr に出し、フラグ指定時は ` (UNUSED: --no-pool)` を添えます（`engine/sycl/src/program/generate.cpp:5939-5941`）。

## 適用条件と副作用

- `--no-capture` だけを指定し、このフラグを付けない場合、`session_token` には CPU expert pool hook がなく routed experts が寄与しないため、処理は stderr に理由を出して終了コード `2` で拒否されます。`--no-capture --no-pool` はこの拒否条件を満たさず、フラグのコメントもこれを GPU-only floor の明示指定として説明しています（`engine/sycl/src/program/generate.cpp:5970-5984`）。
- remote experts を有効にした場合、expert profile、CUDA0 expert cache、expert pool が必要です。`--no-pool` を併用すると stderr に要件を出して終了コード `2` になります（`engine/sycl/src/program/generate.cpp:5664-5669`）。
- `--dump-routing PATH` との併用は拒否されます。stderr に理由を出して終了コード `2` で戻るため、この分岐では出力ファイルを開きません。pool が読む doorbell 経由で routed IDs を host に渡す仕組みに依存するためです（`engine/sycl/src/program/generate.cpp:5919-5929`）。
- `--no-pool` 単独について、ソース上の追加ファイル書き込み・ネットワーク動作は確認できません。ほかの出力オプションの副作用はそれぞれのオプションに従います。

## 出力とエラー

`--no-pool` 固有の成功時出力は、stderr の worker 数表示に付く ` (UNUSED: --no-pool)` です。上記の `--no-capture` 条件、remote experts、`--dump-routing` との不整合は、いずれも診断を stderr に出して終了コード `2` を返します（`engine/sycl/src/program/generate.cpp:5665-5668,5921-5924,5939-5941,5979-5984`）。未知の引数は別途 `unknown argument` と usage を stderr に出し終了コード `2` です（`engine/sycl/src/program/generate.cpp:2214-2219`）。

## 根拠

- `engine/sycl/src/program/generate.cpp:530,941,1969-1971` — option state の初期値、usage 表示、parser 登録。
- `engine/sycl/src/program/generate.cpp:5664-5669` — remote experts との適用条件と失敗経路。
- `engine/sycl/src/program/generate.cpp:5919-5941` — routing dump の拒否、pool/hit hook の選択、stderr 表示。
- `engine/sycl/src/program/generate.cpp:5970-5984` — `--no-capture` との条件と失敗経路。
- `engine/sycl/src/core/session.cpp:995-1016` — doorbell payload 待機後、pool callback を条件付きで呼ぶ処理。
- 配置と scope は `docs/cli/README.md:1036-1041,1153`、tool ID と parser 所在は `docs/cli/000_cli_tools.md:10` を確認しました。

調査範囲はこの checkout の Strata 所有ソースです。既存バイナリの `--help` は実行していません。オプションの parser と利用箇所はソースで確認しました。
