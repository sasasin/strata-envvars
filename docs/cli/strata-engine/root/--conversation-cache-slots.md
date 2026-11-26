# `strata --serve --conversation-cache-slots`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata --serve` |
| オプション | `--conversation-cache-slots` |
| 別名 | なし |
| 値 | 0 以上 `INT32_MAX` 以下の整数。保持できる駐車済み会話数の上限 |

## 役割

`--serve` がリクエスト間にホスト RAM 上へ保持する会話状態の個数上限を指定する。別の会話へ切り替えたときに戻ってくる会話の状態を再利用できるが、この数は同時に処理するリクエスト数ではない。キャッシュ全体の RAM 予算は `--conversation-cache-mib`、各会話状態を保持する前提となるチェックポイント数は `--prompt-cache` が別に制御する（`engine/src/program/generate.cpp:1086-1093`、`engine/include/strata/core/conversation_cache.hpp:302-309`）。

## 使い方

```sh
# serve で、切り替え前の会話状態を最大 8 件まで保持する
strata --serve --model /path/to/model --conversation-cache-slots 8
```

## 値と既定値

- 値は必須。省略時は 4。標準 parser と SYCL parser の双方が `0` から `INT32_MAX` までを受け付ける（`engine/src/program/generate.cpp:1091,4084-4108`、`engine/sycl/src/program/generate.cpp:727,2065-2079`）。
- 負数、整数として解析できない値、範囲外の値は拒否される。parser は stderr に `--conversation-cache-slots needs a nonnegative integer within range` を出して終了コード 2 を返す。値の欠落も同じ終了コード 2 で `--conversation-cache-slots needs a value` を出す（`engine/src/program/generate.cpp:3842-3846,4089-4097`、SYCL 側は `engine/sycl/src/program/generate.cpp:2065-2073`）。
- 同じオプションを複数回指定した場合は、解析のたびに同じ設定値へ代入されるため最後の値が残る（`engine/src/program/generate.cpp:4099-4108`）。
- `0` はキャッシュを無効にする値。`ConversationCache::enabled()` は RAM 予算と slot 数の両方が 0 でない場合にのみ true となる（`engine/include/strata/core/conversation_cache.hpp:302-304`）。

## 実行時の動作

parser は値を検証して `conversation_cache_slots` に格納する。serve 起動時にこの値が `ConversationCache` の slot 上限として渡され、駐車済み会話の件数が上限に達した状態で新しい会話を格納すると、古いものから退避して空きを作る。slot 数だけでなく RAM 予算、pin/guard 中の会話状態も判定され、残す必要のある状態と新しい状態が収まらない場合は新しい駐車が拒否される（`engine/src/program/generate.cpp:13881-13883`、`engine/include/strata/core/conversation_cache.hpp:454-484,633-641`）。

slot 数が 0 の場合、会話キャッシュは無効となる。`--prompt-cache 0` もキャッシュを無効にする。RAM 予算が正のときにどちらかが 0 なら、engine は stderr に無効化の理由を警告する（`engine/src/program/generate.cpp:4761-4763`、SYCL 側 `engine/sycl/src/program/generate.cpp:2251-2253`）。標準 parser では RAM 予算を省略したとき、`--serve`、`--prompt-cache` が正、slot 数が正の場合に限り、モデル読込後の空き RAM から自動算定する経路へ進む。slot を 0 にした場合はその自動算定を行わず、予算を 0 としてキャッシュを無効化する（`engine/src/program/generate.cpp:13849-13883`）。

端末側の serving 実装も、engine 起動引数または engine の `INFO` 行から slot 数を読み、prompt encoder の保持数に使う。正の値なら encoder の `keep` 数をこの値に合わせ、0 または値を読み取れない場合は encoder の既定値を使う（`terminal/serve/server_parts/engines.py:389-399`、`terminal/serve/server.py:4305-4312`）。

SYCL 版もこの値を同じ範囲で検証し、4 を既定値としてキャッシュへ渡す。一方、SYCL 版の `--conversation-cache-mib` は既定で 0（opt-in）であり、標準版の未指定時に行う RAM 予算自動算定とは異なる（`engine/sycl/src/program/generate.cpp:726-728,8136-8138`）。slot 数が正でも RAM 予算が 0 なら会話キャッシュは有効にならない。

## 適用条件と副作用

- この設定の主な適用先は engine の `--serve` モード。保持する会話状態はホスト RAM を使い、件数上限到達時には古い状態が退避される（`engine/src/program/generate.cpp:1293-1296`、`engine/include/strata/core/conversation_cache.hpp:454-484`）。
- 端末サーバーは、engine の slot 数と prompt encoder が保持する prompt 数を揃える。engine の会話 cache と prompt encoder の挙動を連携させる値である（`terminal/serve/server.py:4308-4312`）。
- この値だけでは会話キャッシュは有効にならない。RAM 予算が 0、または `--prompt-cache 0` の場合は engine 側 cache が無効。キャッシュに使えるメモリ量と slot 上限のどちらかが先に制約に達する可能性がある（`engine/include/strata/core/conversation_cache.hpp:302-304,454-484`）。
- cache が保持できる以上の会話を切り替えて利用する場合、退避された会話は再訪時に prompt を読み直す必要がある。ここでは再読込にかかる時間や性能効果は測定していない。

## 出力とエラー

不正値または値の欠落では stderr に parser エラーを出して終了コード 2 となる。`--serve` で RAM 予算が正なのに slot 数が 0 の場合は警告を出し、会話キャッシュを無効にする（`engine/src/program/generate.cpp:3844-3846,4095-4097,4761-4763`）。

## 根拠

- `engine/src/program/generate.cpp:1086-1093,1293-1296`: 既定値と serve 用会話キャッシュの説明。
- `engine/src/program/generate.cpp:3842-3849,4084-4108`: 引数の取得、整数範囲検証、設定代入、欠落値の処理。
- `engine/src/program/generate.cpp:4761-4763,13849-13883`: 無効化警告、RAM 予算の自動算定条件、キャッシュへの slot 数の引き渡し。
- `engine/include/strata/core/conversation_cache.hpp:302-309,454-484,633-641`: cache 有効条件、slot 数を含む空き判定と古い会話の退避、格納の可否。
- `engine/sycl/src/program/generate.cpp:726-728,2065-2079,2251-2253,8136-8138`: SYCL 版の既定値、parser、警告、cache への引き渡し。
- `terminal/serve/server_parts/engines.py:389-399`、`terminal/serve/server.py:4305-4312`: engine slot 数の取得と prompt encoder への反映。

この文書はソース parser と使用箇所を調査したもの。CLI `--help` は実行していない。性能測定、build、GPU 実行は行っていない。
