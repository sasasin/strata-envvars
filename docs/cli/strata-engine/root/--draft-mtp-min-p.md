# `strata --draft-mtp-min-p`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` のリクエスト処理を含む） |
| オプション | `--draft-mtp-min-p` |
| 別名 | なし |
| 値 | `P`（数値。parser で `[0, 1]` に clamp） |

## 役割

`--draft auto` でサーバーを動かすとき、MTP が選ばれたリクエストに適用する draft 確率の下限を指定します。MTP が提案した token の確率が下限を下回ると、その先の提案を verify window に含めません。`--draft auto` のリクエストが DFlash2 を選ぶ場合にはこの値は使われません（`engine/src/program/generate.cpp:18876-18899,21852-21859`）。

## 使い方

```sh
strata --serve --pack /models/pack --native /models/model.gguf \
  --mtp /models/mtp --draft-model /models/dflash2-pack \
  --spec 8 --draft auto --draft-mtp-min-p 0.2
```

上の例では、`draft=mtp` のリクエストに対する下限を `0.2` にします。実際のモデルファイルと pack のパスに置き換えてください。`--draft auto` は serve 用で、MTP と DFlash2 の両方を読み込み、リクエストごとに使う drafter を選ぶモードです（`engine/src/program/generate.cpp:1365-1366,8195-8202`）。

## 値と既定値

- オプションを省略したときの内部値は `-1.0` です。この sentinel により、MTP リクエストでは通常の `--spec-min-p` の値を引き継ぎます。`--spec-min-p` 自体の既定値は `0.0` です（`engine/src/program/generate.cpp:1063,1193-1195,18753-18757`）。
- 指定値は `std::atof` で数値化され、`0.0` から `1.0` に clamp されます。範囲外の数値は端点に補正されます。数値として解釈できない文字列は `atof` により `0` となり、値エラーにはなりません（`engine/src/program/generate.cpp:4147-4149`）。
- 明示した `0` は既定値 sentinel ではなく、閾値を無効にする値です。閾値判定は `req_spec_min_p > 0.0` の場合だけ行われます（`engine/src/program/generate.cpp:18895,21853-21859`）。
- 同じオプションを複数回指定した場合、引数を順に処理して値を代入するため、最後の指定が残ります（`engine/src/program/generate.cpp:3837-3842,4148`）。値が省略されて引数末尾に達すると、標準エラーに `--draft-mtp-min-p needs a value` と出して終了コード `2` で終了します（`engine/src/program/generate.cpp:3839-3842,4148`）。

## 実行時の動作

`--draft auto` は parser 内部で DFlash2 選択と auto モードの印に変換されます。serve の各リクエストでは `draft=mtp|dflash2`、または `--draft-rule` の値（既定 `df2`）を使って drafter を選びます。auto モードで DFlash2 が利用可能な場合に、選択結果が MTP で、かつリクエストに `spec_min_p=...` がないとき、このオプションの値がそのリクエストの `req_spec_min_p` に設定されます（`engine/src/program/generate.cpp:1190-1195,4138-4148,18753-18757,18876-18899`）。

リクエストの `spec_min_p=...` は `[0,1]` に clamp され、指定有無も記録されます。そのキーがある場合は `--draft-mtp-min-p` が上書きしません（`engine/src/program/generate.cpp:18816-18819,18895`）。最終的な `req_spec_min_p` は MTP の draft 確率に対して順に比較され、下限未満になった位置で MTP の提案 window を短くします（`engine/src/program/generate.cpp:21852-21859,22108,22125`）。

この値が参照されるのは `use_df2 && o.draft_auto` の分岐内です。DFlash2 が起動できず `use_df2` が false になった場合は MTP fallback に移りますが、このオプションは fallback 時の request threshold には設定されません。`--draft auto` の両 drafter モードは layer split または `--batch` と併用できず、起動時に拒否されます（`engine/src/program/generate.cpp:8195-8202,18876-18895`）。

## 適用条件と副作用

- `--serve --draft auto` の serve リクエストで、DFlash2 が利用可能であり、そのリクエストが MTP を選択したときに適用されます。リクエスト指定 `draft=mtp`、または `--draft-rule mtp` などで MTP を選択できます（`engine/src/program/generate.cpp:1365-1366,18876-18895`）。
- 通常の `--draft mtp` モードや、serve でない実行経路には、この option の個別値を反映する参照がありません（option 値の参照は `engine/src/program/generate.cpp:18895`）。
- 値によるファイル操作や追加の外部プロセス起動はありません。実行時にリクエストごとの確率下限として参照されます（`engine/src/program/generate.cpp:18895,21852-21859`）。

## 出力とエラー

この値に固有の警告・エラー出力は確認できません。引数値の字句検証はなく、数値変換後の clamp が行われます。末尾で値が欠けている場合の診断と終了コードは「値と既定値」を参照してください（`engine/src/program/generate.cpp:3839-3842,4148`）。

## 根拠

- `engine/src/program/generate.cpp:1193-1195` — 既定値、sentinel、option の用途。
- `engine/src/program/generate.cpp:1365-1366` — help の説明と `--draft auto` の serve 専用スコープ。
- `engine/src/program/generate.cpp:3837-3842,4147-4149` — 引数取得、値の変換・範囲補正、値不足時のエラー。
- `engine/src/program/generate.cpp:18753-18757,18816-18819,18876-18899` — request threshold の初期値、request 指定、drafter 選択と CLI 値の適用条件。
- `engine/src/program/generate.cpp:21852-21859,22108,22125` — MTP の draft 確率による window 幅の決定。
- `engine/src/program/generate.cpp:8195-8202` — auto モードの起動条件と非対応条件。
