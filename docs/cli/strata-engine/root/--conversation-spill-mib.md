# `strata --conversation-spill-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（トップレベルのエンジン引数） |
| オプション | `--conversation-spill-mib` |
| 別名 | なし |
| 値 | 10 進整数 `N`（MiB）、`0` 以上 `8796093022207` 以下 |

## 役割

`--serve` の会話キャッシュで、RAM tier から退避した会話を保存する SSD tier の容量上限を指定します。`0` は SSD tier を無効にします。省略時はディスク空き容量を基に上限を決めます。

## 使い方

```sh
strata --serve --pack /path/to/data/packs/model --conversation-spill-mib 8192
```

この例では SSD tier の予算を最大 8192 MiB にします。実際の上限は `--session-min-free-mib` が確保する空き容量にも制限されます。

## 値と既定値

- 値は符号なしの 10 進整数として解釈されます。parser は `std::from_chars` で値全体を読み取り、`0` 以上 `INT64_MAX / 1048576` 以下であることを検証します。したがって、負数、整数でない文字列、範囲外の値は受け付けません（`engine/src/program/generate.cpp:4079-4093`）。
- 既定値は内部で `-1` です。これは自動予算を選ぶ未指定状態で、明示できる CLI 値ではありません（`engine/src/program/generate.cpp:1110-1120`）。
- 同じオプションを複数回指定した場合、parser は各値を順に代入するため、最後に指定した値が使われます（`engine/src/program/generate.cpp:3837-3842,4079-4101`）。値がない場合は stderr に `--conversation-spill-mib needs a value` を出し、終了コード 2 で終了します。無効値・範囲外の場合は stderr に `--conversation-spill-mib needs a nonnegative integer within range` を出し、終了コード 2 です（`engine/src/program/generate.cpp:3839-3841,4090-4093`）。

## 実行時の動作

会話キャッシュが有効で、layer split がなく、値が `0` でない場合に SSD tier の初期化を試みます。値 `N > 0` の容量は `N MiB` とディスク空き容量から `--session-min-free-mib` の確保分を引いた値の小さい方です（`engine/src/program/generate.cpp:13965-13986`）。

値を省略したときの既定予算は、ディスク空き容量の 4 分の 1、32 GiB、空き容量から確保分を引いた値の最小です。確保分は `--session-min-free-mib`（既定 4096 MiB）で、tier がその空き容量を使い切らないようにします（`engine/src/program/generate.cpp:1108-1113,13981-13986`、`engine/include/strata/core/conversation_spill.hpp:57-64`）。

SSD tier は会話キャッシュそのものを有効にしません。会話キャッシュが無効なら `conversations.enabled()` が偽となり、SSD tier の初期化ブロックには入りません（`engine/src/program/generate.cpp:13802-13804,13965`）。また、予算 `0` は初期化をスキップします。tier が動作している場合も、RAM に収まる会話はディスクへ書かれず、RAM tier からの退避など必要な場合に保存対象になります（`engine/src/program/generate.cpp:13956-13965,14017-14028`）。保存した会話は、後続リクエストの prompt により適合する場合に読み戻されます（`engine/src/program/generate.cpp:19447-19473`）。

## 適用条件と副作用

- 既定の保存先は `--pack` が `<data>/packs/<tag>` にある場合の `<data>/conversation-spill` です。これに当てはまらず `--conversation-spill-dir` も空なら tier は有効化されません（`engine/src/program/generate.cpp:1110-1114,13965-13978`）。
- 保存先ディレクトリを作成し、そのファイルシステムの空き容量を調べます。指定予算または自動予算が 64 MiB 未満なら tier は無効になります。したがって、小さい正の値を指定しても、実効予算が 64 MiB 未満になると利用されません（`engine/src/program/generate.cpp:13979-13987`）。
- 会話データを保存先へ書き込み、容量上限に達すると tier 内のデータが容量管理の対象になります。永続化の選択は `--conversation-spill-persist`、保存先は `--conversation-spill-dir` で別途制御されます（`engine/src/program/generate.cpp:1110-1119,14001-14013`）。
- parser は `--serve` の有無にかかわらずこの引数を受理しますが、SSD tier 初期化コードは会話キャッシュを使う serve 経路にあります。このオプション単独で通常の生成実行に SSD tier が追加される根拠は確認できません（`engine/src/program/generate.cpp:4079-4101,13773-13804,13965`）。

## 出力とエラー

初期化できると stderr に tier の保存先と容量を表示します。保存先を決められない、ディスク情報を読めない、容量が不足する、または tier を開けない場合は stderr に `no SSD tier: ...` と理由を出します（`engine/src/program/generate.cpp:13974-14012`）。これらの初期化失敗経路では同箇所に明示的なプロセス終了はなく、tier を無効のまま処理を続けます。

個々の書き込みが失敗した場合は stderr に `could not spill ...` を出します。会話の読み戻しに失敗した場合は stderr に理由を出し、その prompt を読み直します（`engine/src/program/generate.cpp:14048-14073,19447-19490`）。

## 根拠

- parser の値取得、10 進整数の検証、フィールドへの代入: `engine/src/program/generate.cpp:3837-3842,4079-4105`。
- 既定値、`--session-min-free-mib` との関係: `engine/src/program/generate.cpp:1108-1120`。
- 会話キャッシュ構築と SSD tier の適用条件、保存先・容量決定・初期化結果: `engine/src/program/generate.cpp:13773-13804,13956-14013`。
- 自動予算の計算: `engine/include/strata/core/conversation_spill.hpp:57-64`。
- 書き込み・読み戻しと失敗時の扱い: `engine/src/program/generate.cpp:14017-14073,19447-19490`。
