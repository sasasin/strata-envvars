# `--conversation-cache-rewind-keep`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、`--serve` モード） |
| オプション | `--conversation-cache-rewind-keep` |
| 別名 | なし |
| 値 | 0 以上 `INT32_MAX` 以下の10進整数 `N`（トークン数） |

## 役割

`--serve` 中、直前まで処理していた同じ会話を、クライアントが返送しなかった回答末尾（たとえばクライアントが取り除いた reasoning）を切り戻して再開する場合に、その末尾が `N` トークン以内なら会話全体の K/V スナップショット保存（park）を省略する。既定値 `0` は常にこの最適化を無効にする。

## 使い方

```sh
strata --serve --pack /path/to/model-pack --conversation-cache-rewind-keep 4096
```

ここで `strata` は `strata-engine` の実行ファイルを指す。サーバーモードで使う値を指定し、実際に省略されるかどうかは各リクエストの会話状態で決まる（`engine/src/program/generate.cpp:1306-1309, 19622-19635`）。

## 値と既定値

- `N` は値必須の10進整数。既定値は `0` で、その場合は park を省略しない（`engine/src/program/generate.cpp:1101-1104, 1306-1309`）。
- parser は整数全体を `std::from_chars` で読み、負数、整数として読めない値、値の末尾に余分な文字がある値、`INT32_MAX` を超える値を拒否する。空文字も整数として読み取れないため拒否される。範囲外・不正値では stderr に `--conversation-cache-rewind-keep needs a nonnegative integer within range` を出し、終了コード `2` で終了する（`engine/src/program/generate.cpp:4082-4092`）。
- 値が省略されて次の argv もない場合は stderr に `--conversation-cache-rewind-keep needs a value` を出し、終了コード `2` で終了する（`engine/src/program/generate.cpp:3839-3841`）。
- 同じオプションを複数回指定した場合、parser は各値を順に同じ設定へ代入するため、最後に指定した値が残る（`engine/src/program/generate.cpp:3837-3842, 4082-4099`）。

## 実行時の動作

値が `0` より大きく、要求が現在の live 会話からの続きではなく、`resume > 0` で live 状態が有効、かつ incoming 会話の復元・borrow・batch slot と lent slot の利用がなく、要求に画像がない場合に判定する。さらに live のトークン数が `resume` より大きく、切り戻される末尾 `live_n - resume` が `N` 以下であり、resume 位置が live 会話の少なくとも半分（`2 * resume >= live_n`）を占め、先頭 `resume` 個のトークンが要求 prompt とすべて一致するときだけ park を省く。末尾の長さは上限 `N` と等しい場合も対象になる。判定 helper は `engine/include/strata/program/conv_cache.hpp:99-113`、serve 経路での適用条件は `engine/src/program/generate.cpp:19615-19630` にある。

この条件に合わない場合は、このオプションによる省略は行わず通常の park 判定へ進む。たとえば、共有しているのが短い system prompt だけの別会話、resume 位置が live の半分未満、resume 以降のトークンが `N` より多い会話、画像を含む要求、incoming / borrow / slot 経路は対象外。省略対象のときは `keep_branch` が park 処理の条件を抑止する（`engine/src/program/generate.cpp:19622-19635, 19730-19755`）。

park は会話の K/V を読み取って保存する処理であり、これを省略しても今回の生成トークンは変わらない。省略した末尾は live 状態から切り戻され、別の要求でその枝を再訪した場合に再度読み込まれる（`engine/include/strata/program/conv_cache.hpp:99-104`）。`--conversation-cache-park-gain` など他の park 判定も存在するが、本オプションの判定は独立して `keep_branch` に反映される（`engine/src/program/generate.cpp:19610-19630`）。

## 適用条件と副作用

- help と実装コメントはいずれも `--serve` 用として説明している。引数 parser 自体は `--serve` の有無でこの値を拒否しないが、実際の rewind 判定・park 制御は serve リクエスト処理内にある（`engine/src/program/generate.cpp:1306-1309, 19615-19635`）。非 serve 実行での有効性は確認できない。
- 対象会話では park 時の K/V コピーがなくなり、そのリクエストで会話 cache への保存を省く。ログには stderr へ `strata serve: conversation cache: park not needed ...` が出る（`engine/src/program/generate.cpp:19631-19635`）。
- この判定は画像要求を除外する。ソース上、OS や GPU backend ごとの値制限は見当たらないが、全 build/backend での実行結果まではこのソース調査だけでは確認していない。

## 出力とエラー

値の欠落・不正値による parse error は終了コード `2`。オプションの条件を満たして park を省いた場合、上記の案内が stderr に出る。通常 park 側で park 処理に失敗すると serve 処理は `ERR <理由>` を stdout に出してコード `1` を返すが、これはオプション固有のエラーではなく、オプションが省略条件を満たさなかった場合などの通常経路である（`engine/src/program/generate.cpp:3839-3841, 4082-4092, 19730-19755`）。

## 根拠

- `engine/src/program/generate.cpp:1101-1104` — 設定値の型と既定値、用途のコメント。
- `engine/src/program/generate.cpp:1306-1309` — engine の usage にある `--serve` 用説明。
- `engine/src/program/generate.cpp:3837-3842, 4082-4099` — 値取得、範囲検証、設定への代入。
- `engine/include/strata/program/conv_cache.hpp:99-113` — suffix 上限・共通 prefix・会話長比率を検証する純粋 helper。
- `engine/src/program/generate.cpp:19615-19635, 19730-19755` — serve 時の適用条件、ログ、park 分岐と失敗経路。
