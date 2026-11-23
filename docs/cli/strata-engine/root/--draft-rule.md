# `strata` `--draft-rule`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--draft-rule` |
| 別名 | なし |
| 値 | `df2`、`mtp`、`learn`（文字列を受け取る） |

## 役割

`--draft auto` で serve モードを起動したとき、リクエストに `draft=` がない場合に DFlash2 と MTP のどちらを使うか決めます。既定値 `df2` は DFlash2 を選びます。`--draft-rule` 単独では `auto` を有効にせず、通常の drafter 選択も変更しません（`engine/src/program/generate.cpp:1190-1192, 1365, 4146, 18878-18882`）。

## 使い方

```sh
strata --serve --draft auto --draft-rule learn --mtp MTP_DIR --draft-model DFLASH2_PACK --spec 6
```

この指定で両方の drafter を使う serve 起動を構成し、各リクエストに `draft=mtp` または `draft=dflash2` がなければ `learn` の選択規則を使います。`--draft auto` は内部で `dflash2` と自動選択フラグに変換されます（`engine/src/program/generate.cpp:4138-4146`）。

## 値と既定値

- 既定値は `df2` です。選択処理では `df2` と `dflash2` が DFlash2、`mtp` が MTP に対応します（`engine/src/program/generate.cpp:1192, 18879-18882`）。
- `learn` はプロンプトの先頭側の token 列から作るキーごとに選択履歴を持ち、初めに DFlash2 と MTP を各 2 回試します。その後は観測済み decode tok/s を比較し、速度差が 4% 未満なら 6 リクエストごと、それ以外は 12 リクエストごとに、優位と判定した側でない drafter も試します（`engine/src/program/generate.cpp:18882-18893`）。
- `learn` の観測値は、生成 token 数が 48 以上で decode 時間が正の場合に限って更新されます。drafter ごとの tok/s を、初回はその値、以降は旧値 0.65・新値 0.35 の重みで平滑化します（`engine/src/program/generate.cpp:23123-23128`）。
- parser は値の文字列をそのまま保存し、`df2|mtp|learn` の検証を行いません（`engine/src/program/generate.cpp:4146`）。選択分岐にも不正値用のエラー経路はありません。値が分岐に一致しない場合、リクエスト開始時の `req_df2 = use_df2` が維持されるため、DFlash2 がロードされていれば DFlash2、それ以外では MTP が選ばれます（`engine/src/program/generate.cpp:18838-18839, 18878-18895`）。値の誤りを検知する用途には使えません。
- 明示的な空文字も parser では受理されますが、選択分岐に一致せず、`use_df2` に基づく初期選択が維持されます（`engine/src/program/generate.cpp:4146, 18838-18839, 18878-18895`）。
- 値を省略した場合は既定値が使われます。値自体を省略した場合は共通の `next()` が標準エラーに `--draft-rule needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3839-3841, 4146`）。複数回指定時は引数を順に読む parser が後の指定で `draft_rule` を再代入します（`engine/src/program/generate.cpp:3837-3842, 4146`）。

## 実行時の動作

serve の各リクエストでは、`draft=` キーがあればその値を `req_draft` に読み込みます。`--draft auto` かつ DFlash2 がロード済みの場合、リクエストの値が空なら `--draft-rule`、値があればリクエスト側の値を優先します。`draft=mtp` は MTP、`draft=dflash2` は DFlash2 を選びます（`engine/src/program/generate.cpp:18768-18779, 18818, 18878-18882`）。

`learn` の履歴キーは prompt token の index 1 から最大 32 までを FNV-1a 形式で畳み込んで作ります。同じキーに属するリクエスト間で、プロセス内の `bandit` map にある要求数・drafter 別の速度と試行回数を共有します。選択した drafter に応じて speculative draft policy を切り替え、MTP 用の verify window は `--draft-mtp-spec` に基づく幅にします（`engine/src/program/generate.cpp:18882-18900, 16305-16309`）。

`--draft auto` では、現在のリクエストに使わない drafter も文脈に追随させる処理があります。リクエストごとの drafter 切替を可能にするため、GPU 上で追加の prefill / context 更新が発生します。`STRATA_DRAFT_KEEP=0` が設定されている場合、この追随処理は抑止されます（`engine/src/program/generate.cpp:16310-16311, 22985-22996`）。

## 適用条件と副作用

- `--draft-rule` が選択に影響するのは `--serve --draft auto` で、かつ DFlash2 がロードされている場合です。`--draft auto` の起動条件として、ソースは `--draft-fallback none` を拒否し、両 drafter を保持する構成を要求しています。また、auto は 1 GPU・1 リクエスト時向けで、layer split または `--batch` との組み合わせは DFlash2 起動時に拒否されます（`engine/src/program/generate.cpp:6473-6475, 8195-8201`）。
- `--draft auto` のほかの起動要件（モデル、backend、native pack 等）は `--draft` 側で判定されます。この文書はそれらの値の仕様を網羅しません（`engine/src/program/generate.cpp:6477-6480, 8195-8203`）。
- `learn` の bandit 履歴はプロセス内の map として宣言され、ファイルへの保存処理は確認できません。再起動後も履歴を維持する動作は確認できません（`engine/src/program/generate.cpp:16308-16309`）。

## 出力とエラー

オプション値の許容語を検証する専用エラーはありません。不正値は上述の通り既定の drafter 選択状態に残ります。値が指定されない場合は parser が標準エラーに不足を報告し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3839-3841, 4146, 18878-18895`）。

## 根拠

- parser の既定値と option 定義: `engine/src/program/generate.cpp:1190-1192, 4138-4146`
- CLI usage と適用条件の説明: `engine/src/program/generate.cpp:1365-1366`
- request の `draft=` 解析と rule の優先順位: `engine/src/program/generate.cpp:18768-18779, 18818, 18878-18900`
- `learn` の試行・選択と速度学習: `engine/src/program/generate.cpp:16308-16309, 18882-18893, 23123-23128`
- 未使用 drafter の追随処理: `engine/src/program/generate.cpp:22985-22996`
- 起動時の auto 制約: `engine/src/program/generate.cpp:6473-6480, 8195-8203`
