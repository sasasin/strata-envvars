# `--conversation-cache-min-tokens`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、トップレベル） |
| オプション | `--conversation-cache-min-tokens` |
| 別名 | なし |
| 値 | 0 以上 `INT32_MAX` 以下の整数 token 数 |

## 役割

`--serve` の会話キャッシュで、別のリクエストへ切り替えるときに host memory へ退避する会話の最小 token 数を指定します。短い side request がキャッシュの slot を使い、長い会話を追い出してしまうのを避ける目的のしきい値です。キャッシュの byte budget や slot 数を増減させる設定ではありません。

## 使い方

```sh
strata --pack /path/to/model-pack --serve --conversation-cache-min-tokens 2048
```

`/path/to/model-pack` は実在するモデル pack のパスに置き換えてください。たとえば `2048` なら、現在の live 会話が 2048 token 以上の場合に限り、会話切替時の退避候補になります。

## 値と既定値

- 省略時は `0` です。`0` はどの長さの会話も token 数の条件では除外しません。
- parser は十進整数として値全体を読み、負数、整数以外、範囲外の値を拒否します。上限は `INT32_MAX` です。
- 値がない場合は `--conversation-cache-min-tokens needs a value` を stderr に出して終了コード 2 で終了します。無効値・範囲外値では `--conversation-cache-min-tokens needs a nonnegative integer within range` を stderr に出し、終了コード 2 で終了します。
- 同じオプションを複数回指定した場合、parser は各指定値を順に同じ設定欄へ代入するため、最後に解析された値が残ります。

## 実行時の動作

parser は値を `Options::conversation_cache_min_tokens` に格納し、serve の会話キャッシュ生成時に `ConversationCache` へ渡します。キャッシュは `live.size()`（現在の live 会話が保持する token 数）をしきい値と比較し、`min_tokens <= 0` または `tokens >= min_tokens` のときだけ退避対象とします。

しきい値判定は会話切替時の退避処理内で行われます。閾値未満なら `skip parking` を stderr に出し、正常なスキップとして戻ります。この判定が先に行われるため、その経路では現在の会話を snapshot 化せず、後続の budget / RAM admission による slot 追い出し処理にも進みません。

## 適用条件と副作用

- オプションは engine parser で受理されますが、効果は `--serve` の会話キャッシュ経路に限られます。serve ではない通常生成の動作を変更しません。
- 会話キャッシュが有効で、live 会話があり、リクエスト切替時の制御フローが `park_current` を呼ぶ場合に判定されます。キャッシュは byte budget が 0、slot 数が 0、または `--prompt-cache 0` のとき無効です。
- 判定対象は切替直前の live 会話です。しきい値未満でのスキップはエラーではありませんが、その会話の state はキャッシュに退避されず、後のリクエストで再利用できません。
- `--conversation-cache-park-gain` も指定した場合、会話切替側の park-gain 条件が先に `park_current` を呼ぶか決めます。park-gain 条件で呼び出し自体が見送られた場合、この option の比較や `skip parking` ログは発生しません。
- 閾値以上でも snapshot が byte budget や RAM floor に収まらない場合など、別の条件で退避がスキップされることがあります。この option はそうした制約を緩和しません。

## 出力とエラー

閾値未満のときは stderr に `strata serve: conversation cache: skip parking (<実 token 数> tokens, below the <設定値> minimum; parked=<現在の退避数>)` を出力します。戻り値は非エラーの成功扱いで、serve を終了しません。parser validation の失敗は終了コード 2 です。

## 根拠

- `src/program/generate.cpp:732-735` — 既定値 0 と option の意図。
- `src/program/generate.cpp:900-901` — 組み込み usage 表示での `--serve` 説明と既定値。
- `src/program/generate.cpp:2416-2421` — 引数走査と値の欠落時の終了経路。
- `src/program/generate.cpp:2641-2661` — parser の受理、整数変換、範囲 validation、設定欄への代入。
- `src/program/generate.cpp:2787-2792` — 不明な引数を stderr に出し usage 表示後終了コード 2 とする経路。
- `src/program/generate.cpp:9373-9393` — serve 会話キャッシュの有効条件に関わる自動 budget 設定と、`--prompt-cache`・budget・slots・最小 token 数の接続。
- `src/program/generate.cpp:9470-9488` — live state がある場合の退避処理、しきい値判定、スキップ時の stderr 出力。
- `include/strata/core/conversation_cache.hpp:210-217` — 比較規則と 0 の扱い。
- `src/program/generate.cpp:12740-12774` — park-gain 条件との相互作用、会話切替時の `park_current` 呼び出し。

調査範囲は上記 checkout のソースです。同一 revision の既存 CLI バイナリを特定できなかったため `--help` は実行していません。usage 文はソース内の表示定義を確認しました。Release 配布物や各 platform のビルド済み実行ファイルでの差異は確認していません。
