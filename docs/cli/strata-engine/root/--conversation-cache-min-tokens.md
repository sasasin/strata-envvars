# `strata --conversation-cache-min-tokens`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--conversation-cache-min-tokens` |
| 別名 | なし |
| 値 | 0〜`INT32_MAX` の非負十進整数 `N`（トークン数） |

## 役割

`--serve` で会話キャッシュへ会話を退避（park）するとき、退避対象の最小トークン数を指定します。短い補助リクエストが会話キャッシュの slot を消費し、長い会話を追い出してしまう状況を避けるための足切りです。既定値 `0` は長さにかかわらず退避を許可します（`engine/src/program/generate.cpp:1094-1097,1303-1304`）。

## 使い方

```sh
# serve で、2048 トークン以上の会話だけを会話キャッシュへ退避する
strata --serve --conversation-cache-min-tokens 2048 MODEL.gguf
```

`MODEL.gguf` は利用するモデルファイルに置き換えてください。エンジンの使用法は `strata` の引数 parser に属し、この option は `--serve` 用として help に記載されています（`engine/src/program/generate.cpp:1208-1311`）。

## 値と既定値

- 値は必須です。parser は次の argv 要素を取り、欠けていれば stderr に `--conversation-cache-min-tokens needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3847,4084-4090`）。
- 空文字列、負数、整数でない文字列、範囲外の値、数値の後ろに余分な文字がある値は拒否されます。エラー時は stderr に `--conversation-cache-min-tokens needs a nonnegative integer within range` を出し、終了コード 2 を返します（`engine/src/program/generate.cpp:4090-4097`）。範囲はこの parser 分岐の上限選択で `INT32_MAX` です（同:4092-4094）。
- 既定値は `0` です。`ConversationCache::wants()` は最小値が 0 以下なら任意の長さを受け入れ、それ以外は `tokens >= min_tokens` のときに受け入れます（`engine/src/program/generate.cpp:1094-1097`; `engine/include/strata/core/conversation_cache.hpp:302-309`）。
- 同じ option を複数回指定した場合は、引数列を順に解析して都度同じ設定値へ代入するため、最後に指定した値が残ります（`engine/src/program/generate.cpp:3842-3847,4099-4102`）。

## 実行時の動作

parser は値を `int64_t` に変換した後 `Options::conversation_cache_min_tokens` に保存し、serve 時に `ConversationCache` のコンストラクターへ渡します（`engine/src/program/generate.cpp:1097,4089-4102,13881-13883`）。park 処理は対象会話の `src.ids.size()` を `ConversationCache::wants()` に渡すため、会話がちょうど `N` トークンなら対象となり、`N` 未満なら退避を飛ばします（`engine/src/program/generate.cpp:14262-14270`; `engine/include/strata/core/conversation_cache.hpp:302-309`）。

閾値未満のときは stderr にトークン数・閾値・現在の退避件数を出し、`true` を返します。これはエラーではなく、会話の snapshot 作成、cache slot の消費、後続の容量確保や古い会話の eviction に進まない通常の skip 経路です（`engine/src/program/generate.cpp:14262-14270`）。

## 適用条件と副作用

- この値は parser では `--serve` の有無にかかわらず受理されますが、実際に制御するのは serve の会話退避処理です（help の説明: `engine/src/program/generate.cpp:1303-1304`; serve の `park_source`: 同:14253-14270）。
- 閾値はキャッシュを有効化しません。`ConversationCache::enabled()` は予算と slot 数がともに非ゼロの場合に有効となり、会話 cache の生成時には prompt cache が有効な場合に予算が渡されます（`engine/include/strata/core/conversation_cache.hpp:302-304`; `engine/src/program/generate.cpp:13881-13883`）。`--prompt-cache 0` または `--conversation-cache-slots 0` では conversation caching が無効になる警告経路があり（同:4761-4763）、予算を `--conversation-cache-mib 0` にすると cache は無効です（同:13849-13852,13877-13883）。
- 閾値以上の会話はこの閾値を通過するだけで、実際の退避はさらに予算・空き RAM 等の判定を受けます。これらの判定で退避を見送る場合もあります（`engine/src/program/generate.cpp:14367-14393`）。
- 受理した閾値が serve 起動時の `INFO` 行に `conversation_cache_min_tokens` として出力されます（`engine/src/program/generate.cpp:16200-16217`）。ファイル作成や値の永続化はこの option 自体では行いません。

## 出力とエラー

不正値は stderr に範囲エラーを出して終了コード 2 になります（`engine/src/program/generate.cpp:4095-4097`）。閾値未満の会話はエラーにせず、stderr に `strata serve: conversation cache: skip parking (...)` を出します（同:14266-14270）。serve 起動時には設定値を含む `INFO` 行も stdout に出ます（同:16200-16217）。

## 根拠

- `engine/src/program/generate.cpp:1094-1097,1303-1304` — serve 用設定の既定値と help 表記。
- `engine/src/program/generate.cpp:3842-3847,4084-4102` — 値の取得、整数変換・範囲検証、設定への代入。
- `engine/include/strata/core/conversation_cache.hpp:302-309` — キャッシュの閾値判定と境界（`N` を含む）。
- `engine/src/program/generate.cpp:13881-13883,14253-14270` — 設定の cache への引き渡し、park 時の token 数判定と非エラー skip。
- `engine/src/program/generate.cpp:4761-4763,13849-13883,14367-14393,16200-16217` — cache の適用条件、追加の退避判定、起動時の値出力。
