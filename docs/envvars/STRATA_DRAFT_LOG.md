# `STRATA_DRAFT_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバー要求ループが、DFlash2 drafter を利用する構成で、要求ごとの drafter 名・生成 token 数・round 数・時間を stderr に記録する診断フラグです。生成処理や drafter の選択を切り替える変数ではありません。値を読む箇所は `engine/src/program/generate.cpp` のサーバーループにある `draft_log` 初期化だけで、実際の出力は要求終了時の `draft_log && use_df2` が成立した場合に限られます（`engine/src/program/generate.cpp:16416`, `23226-23239`）。

完全一致検索では、この読み取り箇所のほかに `terminal/data/settings-register.json:7622-7650` の登録情報があります。登録情報は実行時の値読み取りではありません。

## 値と判定

`std::getenv(...) != nullptr` のみで判定し、値を parse しません。未設定ならフラグは false、何らかの値が設定されていれば true です。明示的な空文字も「設定あり」として有効です。したがって `0`、`false`、`0anything`、空白だけ、大文字小文字を問わず、すべて設定済みとして扱います。数値変換・文字列比較・値域検査・clamp はありません（`engine/src/program/generate.cpp:16416`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全 build | ログフラグ false | 空文字を含む、環境変数が存在するすべての値 | なし（値による無効判定なし） |

ただしログ出力には別途 `use_df2` が true である必要があります。`STRATA_HAVE_DFLASH2` がない build では `use_df2` は定数 false なので、環境変数を設定しても出力されません（`engine/src/program/generate.cpp:8151-8158`, `23236-23239`）。

## 有効になる条件

- 環境変数はサーバーループで初めて評価される時点までに設定されている必要があります。
- 要求ループの実行中に DFlash2 が有効 (`use_df2 == true`) である必要があります。DFlash2 が build に含まれ、起動時に `--draft dflash2` の条件を満たして読み込まれ、サーバーループで drafter の bind・prepare・tap reserve が成功することが必要です。セットアップに失敗し MTP fallback へ切り替わる場合、または DFlash2 非対応 build ではこのログは出ません（`engine/src/program/generate.cpp:8151-8158`, `8266-8326`, `13584-13610`, `23236-23239`）。
- `--draft auto` で要求ごとに MTP が選ばれた場合も、DFlash2 自体が有効ならログ対象です。`req_df2` に応じて `drafter=mtp` または `drafter=dflash2` と表示します（`engine/src/program/generate.cpp:18944-19005`, `23236-23239`）。
- `STRATA_DRAFT_LOG` は CLI 引数や他の環境変数によって値を上書きされません。`STRATA_DRAFT_KEEP=0`（空文字も `atoi` では 0）などは auto モードの idle drafter upkeep を変え、ログ中の `keep_ms` に影響しますが、ログの有効・無効条件ではありません（`engine/src/program/generate.cpp:16416-16418`, `23089-23103`）。

## 実行時の詳細

`draft_log` は block-scope `static const bool` です。サーバーループがこの宣言に初めて到達したときに一度だけ環境を読み、それ以降の要求ではキャッシュ値を使います。その後に環境を変更しても反映されません（`engine/src/program/generate.cpp:16397-16418`）。

`GEN` / `GENI` 等の要求処理後、upkeep の同期が成功し、要求の decode 時間を確定した後にログ判定を行います。ログは `use_df2` が true のとき、`STRATA_DRAFT_LOG` が設定済みであれば一要求につき一行です。要求の構文・入力検証で早期に `continue` する経路や、upkeep エラーで `return` する経路ではこの出力位置に到達しません（`engine/src/program/generate.cpp:18808-18819`, `18974-19017`, `23218-23239`）。

`tokens` は `produced_n`、`rounds` は要求開始時からの round 増分、`decode_ms` は要求内の `d0` から upkeep 同期完了までの経過時間です。`keep_ms` は `--draft auto` で要求に使わない側の drafter を追いつかせる処理にかかった時間で、その処理が動かない要求では初期値 0 のままです。末尾の `keep_ms / round` は要求中に round があった場合だけ計算され、round が 0 なら 0.0 を出します（`engine/src/program/generate.cpp:21755-21779`, `23089-23103`, `23226-23239`）。

## ログと測定値

ログは stderr に次の書式で出ます（実際には `%` 指定子が値に置き換わります）。連番はこのログを出した要求ごとに増えます。

```text
strata draft: request %lld drafter=%s window<=%d tokens=%lld rounds=%lld decode_ms=%.1f keep_ms=%.1f (%.3f per round)
```

この文書では測定結果を記載しません。ソースにはログの項目と計算式はありますが、条件をそろえた測定値は確認できません（`engine/src/program/generate.cpp:23236-23239`）。

## 根拠

- `engine/src/program/generate.cpp:16397-16418` — サーバーループとフラグの static 初期化。
- `engine/src/program/generate.cpp:8151-8158` — DFlash2 compile macro による `use_df2` の定義。
- `engine/src/program/generate.cpp:8266-8326`, `13584-13610` — DFlash2 の起動条件、失敗時の fallback。
- `engine/src/program/generate.cpp:18808-18819`, `18974-19017` — 要求認識・入力検証。
- `engine/src/program/generate.cpp:18944-19005` — `--draft auto` の要求単位の drafter 選択。
- `engine/src/program/generate.cpp:21755-21779`, `23089-23103`, `23218-23239` — 時間・counter とログ出力。
- `terminal/data/settings-register.json:7622-7650` — 候補一覧の登録情報（コードによる実行時読み取り箇所ではない）。
