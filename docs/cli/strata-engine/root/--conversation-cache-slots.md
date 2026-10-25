# `--conversation-cache-slots`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--conversation-cache-slots` |
| 別名 | なし |
| 値 | 0 以上 `INT32_MAX` 以下の10進整数 |

## 役割

`--serve` 中に RAM へ退避しておく会話スナップショットの最大件数を指定する。各スナップショットは会話長にかかわらず1 slot を使い、件数上限と `--conversation-cache-mib` の容量上限の両方が適用される。既定値は4。

## 使い方

```sh
strata --serve --native /path/to/model.gguf --conversation-cache-slots 8
```

## 値と既定値

- 値は `std::from_chars` で整数として読み、負数、上限超過、整数でない値、値の一部しか読めない文字列は拒否する。値を省略すると `--conversation-cache-slots needs a value` を stderr に出して終了コード2で終了する。範囲外・不正値では `%s needs a nonnegative integer within range` を stderr に出し、終了コード2で終了する（`src/program/generate.cpp:2418-2421,2641-2653`）。
- 未指定時は4。重複指定は個別に拒否されず、引数処理で後に出た値が設定値になる（`src/program/generate.cpp:730,2641-2662`）。
- `0` は有効値だが、会話キャッシュを無効にする。正数に最小値・推奨値の規定はソース上にない。

## 実行時の動作

エンジンの `--serve` 経路では `ConversationCache` に slot 数として渡される。キャッシュは RAM 予算が0または slot 数が0なら無効となるため、`--conversation-cache-slots 0` は `--conversation-cache-mib` が正数でも退避を止める。RAM 予算を明示しない場合の自動算定も、serve・`--prompt-cache > 0`・slot 数 > 0 が条件であり、slot 数0なら予算を0にする（`src/program/generate.cpp:9373-9393`; `include/strata/core/conversation_cache.hpp:210-217`）。

スナップショットを格納するとき、slot 上限に達していれば空きを作るため最も古い退避会話から削除する。RAM 容量上限も同時に確認し、slot 上限内でも容量不足なら保存できない。pinned な共有 prefix や、借用中に保護されている会話は退避対象から除外され、空きを作れなければ新しい会話の退避を見送る（`include/strata/core/conversation_cache.hpp:245-248,313-350,422-430`）。このため値は保持件数の上限であり、保存成功件数を保証しない。

このキャッシュは会話の切替・巻き戻し時に現在の状態を保存し、次のリクエストで一致する会話状態を再利用するためのもの。`--serve` を使わない通常生成では退避会話を扱う serve 経路に入らず、この値に対応する実行時効果はない（serve 初期化と利用箇所: `src/program/generate.cpp:9360-9393,9468-9490,9622-9627`）。`--prompt-cache 0` もキャッシュを止める条件で、`--serve` 中に容量が正数なら無効化の警告が stderr に出る（`src/program/generate.cpp:2956-2958`）。

## 適用条件と副作用

- キャッシュはホスト RAM 上に会話状態を保持する。slot 数を増やすと最大保持数は増える一方、実際の保存量は `--conversation-cache-mib` など他の制限に従う。各会話の退避ではスナップショットのコピー等が行われる（`src/program/generate.cpp:9470-9479,9622-9627`）。
- `--prompt-cache` が0なら、slot 数が正でも会話キャッシュは無効となる。`--conversation-cache-mib 0` でも無効。`--conversation-cache-mib` 未指定時の RAM 自動算定は、空き RAM と `--conversation-cache-min-free-mib` に基づく（`src/program/generate.cpp:9373-9393`）。
- 1 GPU への layer split (`--split-device 0`) と、正の RAM 予算・正の slot 数・有効な prompt cache を同時に指定すると、会話退避をサポートしないとして stderr にエラーを出し、終了コード2となる。slot 数を0にする経路ではこのチェックは発火しない（`src/program/generate.cpp:3004-3009`）。
- Qwen3.6 family は `--native` の family switch から別 parser へ渡される。そちらは `--conversation-cache-slots` を実装しておらず、`--serve` より後にこの引数を読むと値とともに「not an option of this engine」と stderr に警告して無視し、`--serve` より前に置くと未知引数として終了コード2になる（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3748-3757,3782-3795`）。したがってこのオプションの通常の効果は標準エンジン parser の serve 経路に限られる。

## 出力とエラー

serve で有効な RAM 予算のもと slot 数0を指定すると、conversation caching が `--conversation-cache-slots 0` によって無効になる旨を stderr に警告する。退避時は保存・見送りの状態、現在件数、使用 byte 数、eviction 数などを stderr に記録する（`src/program/generate.cpp:2956-2958,9622-9627`）。

## 根拠

- parser の既定値、help 表示、整数 validation と格納: `src/program/generate.cpp:730,891-896,2418-2421,2641-2662`
- 0 の無効化、1 GPU split 制約: `src/program/generate.cpp:2956-2958,2999-3009`
- 自動 RAM 予算と cache 初期化: `src/program/generate.cpp:9373-9393`
- slot 上限、RAM 上限、古い会話の eviction: `include/strata/core/conversation_cache.hpp:210-217,245-248,313-350,422-430`
- serve での会話退避と出力: `src/program/generate.cpp:9468-9490,9622-9627`
- Qwen3.6 family dispatch と別 parser の扱い: `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3748-3757,3782-3795`

索引上の配置と scope: [`docs/cli/README.md`](../../README.md) の `strata-engine` root。調査基準: [`001_investigation.md`](../../001_investigation.md)。
