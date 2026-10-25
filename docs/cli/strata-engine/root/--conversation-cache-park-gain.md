# `--conversation-cache-park-gain`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--conversation-cache-park-gain` |
| 別名 | なし |
| 値 | 0 以上 `2,147,483,647` 以下の10進整数（トークン数） |

## 役割

`--serve` の会話キャッシュで、すでに保存済みの同じ会話のコピーを置き換えて保存し直す前に、会話が何トークン進んでいる必要があるかを指定します。しきい値を満たさない切替では、新しいスナップショット作成を見送り、保存済みコピーを残します。既定値 `0` は従来どおり毎回の保存を許可します。

## 使い方

```sh
strata generate --pack PACK --native SHARD --expert-cache auto --serve --spec 4 --prefill 8192 --conversation-cache-park-gain 1024
```

`PACK` と `SHARD` は各入力の例示値です。`--serve` の起動には `--spec`、`--prefill`、fill 可能な `--expert-cache` が必要です。graph hit 経路には `--expert-profile` も必要です。実際の起動には利用環境に合う pack、native shard、serve 設定を指定してください。

## 値と既定値

- 省略時は `0` です。
- 値は符号付き64-bit整数として解析した後、0以上かつ `INT32_MAX` 以下であることを検証します。小数、負数、整数以外の末尾文字、範囲外の値は拒否されます。
- 同じオプションを複数回指定した場合は、parser が各出現を順に処理し、最後に設定された値が残ります。
- 値なしの場合は `--conversation-cache-park-gain needs a value` を標準エラーに出して終了コード `2` で終了します。
- 不正値の場合は `--conversation-cache-park-gain needs a nonnegative integer within range` を標準エラーに出して終了コード `2` で終了します。

## 実行時の動作

この値は `--serve` の会話キャッシュ切替処理で使われます。会話の token 列とチェックポイント列を使い、現会話が保存し直すと置き換え対象になる最長の保存済みコピーの prefix 長を調べます。画像キーと control-vector 状態も照合し、保存済みコピーと同じ会話の継続であることを判定します。

- 値が `0` の場合、または置き換え対象のコピーがない場合は `park_worth` が真となり、既存の保存処理へ進みます。
- 値が `N > 0` でコピーが見つかった場合、現在の token 数が「コピーの prefix token 数 + `N`」以上なら保存処理へ進みます。それ未満なら、その会話の保存をこの切替では試みません。
- 条件未達で保存を見送ったとき、現行コードは `park_current` を呼ばないため、この見送り専用のログは出ません。保存済みコピーはそのまま残ります。
- この判定は `--serve` の要求処理中、会話状態を切り替える経路でのみ使われます。`--serve` なしでは parser は値を受理しますが、この判定箇所は実行されません。

この値だけでは会話キャッシュを有効化しません。serve 側で cache budget が無効、live 状態が不正、または空であれば保存処理は何もせず戻ります。`--prompt-cache 0` では `ConversationCache` の予算が0になります。既定の会話キャッシュ予算は serve 時に空き RAM から決まり、`--conversation-cache-mib 0` は無効化を明示します。また、`--conversation-cache-slots`、`--conversation-cache-min-tokens`、`--conversation-cache-min-free-mib` などの条件が保存可否に影響します。

## 適用条件と副作用

- 保存処理自体は要求の切替時に行い、会話スナップショットをホストメモリへコピーします。このオプションは保存頻度を抑える判断を行いますが、保存済みコピーから再開する際には古い prefix から読み進める範囲が増え得ます。ソースコメントは、最大で指定値分の token を再読するコストを説明しています。
- 借用中の会話では、借用元を guard したうえで保存を試みます。条件未達ならその保存・guard 処理は行われず、pin された sibling 会話も独立した条件で保存を抑止します。
- しきい値を満たしても、最小 token 条件、cache budget、RAM floor、スナップショット検証・保存など別の条件で保存が見送られることがあります。通常の予算・RAM・確保失敗は多くの場合 `stderr` に `skip parking` 等を記録して処理を続けます。
- snapshot save や CUDA stage 同期などのハードエラーでは、要求処理が `stdout` に `ERR <理由>` を出して終了コード `1` で戻る経路があります。しきい値だけでこの失敗経路が発生するものではありません。

## 根拠

- `src/program/generate.cpp:736-740` — 設定フィールド、既定値 `0`、意図のコメント。
- `src/program/generate.cpp:902-904` — help 表示上の `--serve` 専用説明と既定値。
- `src/program/generate.cpp:806-817` — `strata generate` の形式と `--pack` の利用例。
- `src/program/generate.cpp:2416-2421` — 値を要求する parser helper と、値欠落時のエラー・終了コード。
- `src/program/generate.cpp:2641-2661` — 数値変換、範囲検証、エラー処理、設定への代入。
- `src/program/generate.cpp:8345-8359` — `--serve` 起動時に `--spec` と `--prefill` を要求する条件。
- `src/program/generate.cpp:9371-9393` — 会話キャッシュの既定予算決定、`--prompt-cache` および slot 数を含む初期化。
- `src/program/generate.cpp:9470-9494`、`9560-9633` — 保存の早期スキップ、budget/RAM 判定、snapshot 保存、ログと確保失敗時の回復。
- `src/program/generate.cpp:12735-12775` — pin/borrow 条件、park gain の比較、および保存処理を呼ぶ分岐。
- `include/strata/core/conversation_cache.hpp:367-419` — 置き換え対象の定義と token prefix 長の照合。
- `docs/cli/README.md:1128-1153` — `strata-engine` の tool scope と本オプションの索引リンク。

確認した parser は `src/program/generate.cpp` の通常エンジン parser です。別 family の parser や Release 配布物での挙動はこの文書の調査対象に含めていません。
