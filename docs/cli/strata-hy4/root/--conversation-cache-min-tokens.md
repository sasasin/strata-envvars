# `strata-hy4 --conversation-cache-min-tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root。CUDA/HIP 版） |
| オプション | `--conversation-cache-min-tokens` |
| 別名 | なし |
| 値 | 整数として `atoi` で読み取る。cache 有効化時に実効下限 64 tokens へ補正される |

## 役割

`--serve` で使う SSD 会話キャッシュにおいて、ディスク退避の対象にする会話長の下限を指定する。短い会話を cache slot に保存しないようにし、別リクエストのために長い会話を退避する場面で、短い会話の保存がその領域を使うのを避ける。設定値が実際に効くのは `--conversation-cache-dir` で cache を初期化できた場合に限る。(`engine/src/hy4flash/run/hy4_main.hip.cpp:357-359, 444-447`; `engine/src/hy4flash/run/hy4_serve.hip.h:50-52, 365-367, 475-477`)

## 使い方

```sh
# CUDA/HIP 版で serve と SSD 会話キャッシュを使い、1024 tokens 以上の会話を退避対象にする
strata-hy4 --serve --native ./model.strata \
  --conversation-cache-dir ./conversation-cache \
  --conversation-cache-min-tokens 1024
```

キャッシュディレクトリには会話状態ファイルが作成される。既存の cache を使う場合を含め、指定先のデータを保持・管理できるディレクトリを指定する。(`engine/src/hy4flash/run/hy4_convcache.h:77-80, 191-219`)

## 値と既定値

- 既定値は `1024` tokens。parser の変数初期値と `ServeOpts` の初期値の双方が 1024。(`engine/src/hy4flash/run/hy4_main.hip.cpp:357-359`; `engine/src/hy4flash/run/hy4_serve.hip.h:49-52`)
- parser は値を `atoi` で変換し、非負整数かどうかの厳密な validation はしない。したがって不正な文字列を拒否するエラー経路はこのオプションにはない。(`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 445-447`)
- cache 初期化時に `std::max(64, min_tok)` が適用される。指定値が 64 未満（負数や 0 を含む）なら実効値は 64 tokens となり、0 で下限判定を無効化することはできない。(`engine/src/hy4flash/run/hy4_convcache.h:71-75`)
- 同じオプションを複数回指定した場合、引数を左から読む parser が `cc_min` を都度代入するため、最後に指定した値が渡される。(`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 445-447, 555-568`)

## 実行時の動作

`--serve` の起動時に parser の `cc_min` が `ServeOpts::cc_min` へコピーされる。`cc_dir` が空でなければ `ConvCache::init` に渡り、ここで実効値の下限が 64 に設定される。(`engine/src/hy4flash/run/hy4_main.hip.cpp:555-568`; `engine/src/hy4flash/run/hy4_serve.hip.h:50-52, 365-367`; `engine/src/hy4flash/run/hy4_convcache.h:71-75`)

キャッシュが有効な serve では、dirty な会話を次の会話へ切り替える際、現在の forward 位置 `fwd` が実効下限以上で、かつ既存 cache entry が要求される場合か同じ会話を継続している場合でなければ、`cc.park` を呼ぶ。`park` 自身も `fwd < min_tokens` なら保存を行わない。serve 終了時にも dirty な会話を同じ下限で判定して保存する。(`engine/src/hy4flash/run/hy4_serve.hip.h:475-477, 607`; `engine/src/hy4flash/run/hy4_convcache.h:165-166`)

`cc.park` は GPU 状態と token 列を cache ファイルへ書き、書き込み失敗時は stderr に `[convcache] ...` を出して `false` を返す。cache の合計が `--conversation-cache-gib` の予算を超えると、最も古い entry を削除して予算内に収める。(`engine/src/hy4flash/run/hy4_convcache.h:165-219, 318-327`)

## 適用条件と副作用

- この設定が参照されるのは `strata-hy4` の CUDA/HIP `--serve` 実装。`--serve` なしの通常推論経路では `cc_min` は使われない。parser は通常経路でも引数を受理するが、その経路での効果はない。(`engine/src/hy4flash/run/hy4_main.hip.cpp:444-447, 543-568`)
- `--conversation-cache-dir` が空なら cache 初期化自体が呼ばれず、この値による退避もない。ディレクトリ作成、モデルファイルの照会など cache 初期化が失敗した場合は stderr に `[convcache] off: cannot use <dir>` を出し、cache は無効のまま serve を続ける。(`engine/src/hy4flash/run/hy4_serve.hip.h:365-367`; `engine/src/hy4flash/run/hy4_convcache.h:71-103`)
- Metal 版と SYCL 版は別 parser・別スコープとして索引化されており、この文書の対象外。README の CUDA/HIP root 節にこのオプションが掲載されている。(`docs/cli/README.md:1277-1288`; `docs/cli/000_cli_tools.md:11`)

## 出力とエラー

- オプション名の後に値がない場合、parser の `nxt()` が stdout に `ERR --conversation-cache-min-tokens needs a value` を出し、終了コード 2 で終了する。(`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383, 447`)
- cache 初期化に失敗すると stderr に `[convcache] off: cannot use <dir>` を出す。個別の退避書き込み失敗は stderr に `[convcache] cannot write ...` または `[convcache] writing ... failed` を出すが、`park` は失敗を返すだけで、この経路で serve を終了させない。(`engine/src/hy4flash/run/hy4_serve.hip.h:365-367`; `engine/src/hy4flash/run/hy4_convcache.h:195-219`)

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:357-359, 375-384, 444-447, 543-568` — CUDA/HIP root parser の既定値・値変換と serve 設定への受け渡し。
- `engine/src/hy4flash/run/hy4_serve.hip.h:49-52, 365-370, 475-477, 607` — serve 側の設定、cache の有効化、切替時と終了時の退避条件。
- `engine/src/hy4flash/run/hy4_convcache.h:71-103, 165-166, 191-219, 318-327` — 下限補正、退避条件、ファイル書き込み・失敗・容量超過時の削除。
- `docs/cli/README.md:1277-1288` と `docs/cli/000_cli_tools.md:11` — 対象ツール・コマンド階層と parser の索引。実装の挙動根拠には使っていない。
