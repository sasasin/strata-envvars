# `--conversation-cache-park-gain`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（root scope） |
| オプション | `--conversation-cache-park-gain` |
| 別名 | なし |
| 値 | 0 以上 `2147483647` 以下の10進整数 `N`（トークン数） |

## 役割

`--serve` 時の会話キャッシュで、同じ会話を再 park する条件を設定します。既存 snapshot を置き換えるとき、会話がその snapshot より少なくとも `N` token 伸びていなければ park を見送ります。snapshot は会話全体のコピーであり、次のターンで直ちに superseded されるコピーを繰り返し作るのを避けるためのしきい値です（`engine/src/program/generate.cpp:1098-1102,19712-19720`）。

## 使い方

```sh
strata generate --serve --conversation-cache-park-gain 1024 --pack ./model.gguf
```

この例は通常の `strata generate` 経路で、既存 snapshot から会話が 1024 token 以上進んだ場合に park を許可します。`--serve` とモデル指定を含みます。

## 値と既定値

- 値は必須です。省略時は `--conversation-cache-park-gain needs a value` を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:3844-3846,4089`）。
- `std::from_chars` で値全体を10進整数として読み、`0..2147483647` の範囲を検証します。負数、小数、範囲外、数値以外や末尾に余分な文字がある値は `--conversation-cache-park-gain needs a nonnegative integer within range` を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:4090-4097`）。
- 既定値は `0` です。0 では park-gain 判定による抑止はなく、従来どおり各切替機会で park します（`engine/src/program/generate.cpp:1102,1305-1307,19716-19720`）。
- 同じ引数を複数回指定すると parser のループがその都度値を代入するため、最後に指定した値が残ります（`engine/src/program/generate.cpp:3842-3848,4102`）。

## 実行時の動作

`--serve` のリクエスト処理で、値が正の場合に `ConversationCache::parked_prefix_tokens()` を呼び、現在の live 会話が置き換えることになる既存 parked entry の最長 prefix 長を取得します。既存 entry がなければ 0 です。同じ control-vector 状態の entry を対象にし、既存 checkpoint または live prefix の一致関係から判定します（`engine/src/program/generate.cpp:19712-19720`; `engine/include/strata/core/conversation_cache.hpp:612-630`）。

判定式は、値が 0 以下、該当 entry がない、または `live token 数 >= 既存 prefix 長 + N` のいずれかなら park を許可します。条件を満たさない場合は `park_worth` が false になり、その後の通常 park、borrow 時の park、可能な host K/V exchange が抑止されます（`engine/src/program/generate.cpp:19716-19720,19760-19764,19836-19859`）。たとえば値が 1024 で、置き換え対象の prefix が 10,000 token なら、live 会話が 11,024 token に達するまではこの理由で再 park しません。

これは cache の有効化や容量を設定するオプションではありません。`--serve` が必要で、会話 cache 自体も有効である必要があります。cache は budget が 0 または slot 数が 0 の場合に無効です。budget 未指定時は `--serve` かつ `--prompt-cache > 0` などの条件で自動設定され、`--prompt-cache 0` では無効になります（`engine/src/program/generate.cpp:1102,13847-13890`; `engine/include/strata/core/conversation_cache.hpp:302-309`）。非 serve 実行では serve の会話 cache 処理が適用されません。また、Qwen3.6-35B-A3B (`qwen35moe`) はモデル family 判定後に別 parser へ分岐します。この family の `--serve` parser は本 option を認識せず、値とともに「not an option of this engine」と stderr に出して無視します。したがって本 option は通常の `generate.cpp` parser が処理するモデル経路に適用されます（`engine/src/program/generate.cpp:3808-3818`; `engine/src/qwen35/q36_engine.cu:5339-5362,5405-5411`）。

## 適用条件と副作用

- `--conversation-cache-min-tokens` の長さ条件、cache budget・slot 制限、RAM admission などの既存 park 条件も別途適用されます。このオプションはそれらの条件を緩和せず、置き換えられる snapshot を再保存するか追加で判定します (`engine/src/program/generate.cpp:19716-19720`; `engine/include/strata/core/conversation_cache.hpp:302-309`).
- threshold に達せず park を見送った場合、古い snapshot はその時点では保持されます。これにより、次の request が既存 prefix を再利用できます。閾値判定そのものはエラーではなく、ここでは専用の警告やログ出力を行いません（`engine/src/program/generate.cpp:19712-19720,19836-19859`）。
- 値は起動時に parser で読み、serve 処理の判定に使います。実行中に更新する経路は確認できません（`engine/src/program/generate.cpp:3842-3848,4102,19716-19720`）。

## 出力とエラー

範囲外・不正値・値の欠落は stderr と終了コード 2 で拒否されます。閾値に達しないための park 抑止は通常の分岐であり、単独ではエラー出力を生みません。実際に park が試みられた場合の skip や失敗は RAM・snapshot など別条件に依存します（`engine/src/program/generate.cpp:3844-3846,4095-4097,19836-19861`）。

## 根拠

- parser の option value、整数変換、範囲検証、代入: `engine/src/program/generate.cpp:3842-3848,4084-4107`
- option の既定値と help 記述: `engine/src/program/generate.cpp:1098-1102,1305-1307`
- park 判定と呼び出し側の適用条件: `engine/src/program/generate.cpp:19712-19720,19760-19764,19836-19859`
- superseded entry の prefix 長判定: `engine/include/strata/core/conversation_cache.hpp:612-630`
- cache の enabled 判定と最小 token 条件: `engine/include/strata/core/conversation_cache.hpp:302-309`
- Qwen3.6 family への分岐と同 family の serve parser における未対応 option の扱い: `engine/src/program/generate.cpp:3808-3818`; `engine/src/qwen35/q36_engine.cu:5339-5362,5405-5411`
