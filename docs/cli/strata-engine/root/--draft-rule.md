# `--draft-rule`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` エンジンの root 引数 |
| オプション | `--draft-rule` |
| 別名 | なし |
| 値 | request の drafter 選択規則。実装上 `df2` / `dflash2`、`mtp`、`learn` を分岐する |

## 役割

`--draft auto` を使う server 起動時に、request が `draft=` を指定しなかったとき、DFlash2 と MTP のどちらで speculative draft を作るか決めます。既定値は `df2`（DFlash2）です。エンジンの usage も `--draft auto` の説明に本オプションと `df2|mtp|learn` を示しています（`src/program/generate.cpp:995-998,1163`）。

## 使い方

ネイティブ pack と MTP データを用意し、serve モードで両方の drafter を有効にする例です。

```sh
strata --serve --draft auto --draft-model /models/dflash2-pack --mtp /models/mtp --spec 6 --draft-rule learn
```

`--draft auto` は内部では DFlash2 を選択しつつ auto mode の印を付けます（`src/program/generate.cpp:3571-3577`）。両方を request ごとに切り替えるモードなので `--draft-fallback none` とは併用できず、指定すると起動処理が status 2 で終了します（`src/program/generate.cpp:5326-5329`）。DFlash2 のロード条件では `--draft-model` 等が確認され、auto は layer split または `--batch` と併用できません（`src/program/generate.cpp:6765-6773`）。

## 値と既定値

- 省略時は `df2` です（`src/program/generate.cpp:997`）。`df2` と `dflash2` は DFlash2、`mtp` は MTP を選びます（`src/program/generate.cpp:15213-15217`）。
- `learn` は prompt ごとに過去の decode 速度を比べて drafter を選びます。分類キーは prompt の token 列の index 1 から最大 32 個で作り（index 0 は含めない）、キーごとに DFlash2 / MTP の速度記録と request 数を保持します。各側をまず 2 件ずつ試し、その後は MTP が明らかに速いとき以外 DFlash2 を優先し、速度差に応じて反対側も 6 件または 12 件ごとに試します（`src/program/generate.cpp:15217-15228`）。
- `learn` の記録更新は正常に完了した request のうち 48 token 以上を生成した場合に限られ、速度は指数平滑（既存値 65%、今回 35%）で保持されます。状態は `DraftBandit` のプロセス内 map で、永続化処理はこの経路にありません（`src/program/generate.cpp:1002-1003,18666-18672`）。
- parser は値をそのまま文字列に保存し、このオプション用の値検証をしません（`src/program/generate.cpp:3579`）。上記以外の値では選択条件に一致せず、request drafter の初期値が DFlash2 のままになります（`src/program/generate.cpp:15190,15213-15217`）。明示的エラーや警告は出ません。
- 複数回指定した場合は parser loop 内で後の値が代入されます。重複指定の拒否処理はありません（`src/program/generate.cpp:3293-3298,3579`）。
- 値がない場合は parser の `next()` が `--draft-rule needs a value` を stderr に出して status 2 で終了します（`src/program/generate.cpp:3295-3297`）。

## 実行時の動作

request 行に `draft=` があれば、その値が `--draft-rule` より優先されます。どちらもない場合に CLI の設定値が選択に使われます（`src/program/generate.cpp:15121,15130-15142,15171,15213-15217`）。request は通常の token 列とともに `draft=mtp` のような key/value を渡す server 入力です。

`learn` の選択は process 内の prompt 別 bandit 状態に基づきます。request ごとに drafter を切り替えるとき、MTP 用の `--draft-mtp-min-p` を明示していて request 自身が `spec_min_p` を設定していない場合は、その値を使います。また auto mode は MTP の窓幅を `--draft-mtp-spec` で制限し、policy 状態も二つの drafter 間で入れ替えます（`src/program/generate.cpp:998-1000,15230-15234`）。

この設定が参照されるのは DFlash2 が実際にロードされ、`--draft auto` が有効な場合だけです。分岐は `use_df2 && o.draft_auto` で囲まれています。単独 `--draft dflash2` や MTP のみの実行ではこの値による request ごとの選択はありません（`src/program/generate.cpp:15211-15214`）。

## 適用条件と副作用

- `--draft auto` は両 drafter を保持して request ごとに選びます。`--draft-fallback none` との併用は拒否されます（`src/program/generate.cpp:995-996,5326-5329`）。
- auto は一枚の GPU・一 request を対象とする条件があり、layer split または `--batch` が有効な場合は DFlash2 のロード条件で不適合理由になります。また DFlash2 は `--pipeline-windows` とも併用できません（`src/program/generate.cpp:6765-6771`）。
- `learn` はプロセス内の計測状態を更新し、request ごとに drafter を選びます。別ファイルの読み書きや追加 process 起動はこのオプションの実装箇所では行いません（`src/program/generate.cpp:1002-1003,15217-15228,18666-18672`）。

## 出力とエラー

`--draft-rule` 固有の通常時ログ、値検証エラー、終了コード変更はありません。値欠落時は parser 共通の status 2 エラーになります（`src/program/generate.cpp:3295-3297`）。`--draft auto` と `--draft-fallback none` の組み合わせは別途 stderr に理由を出し status 2 で終了します（`src/program/generate.cpp:5326-5329`）。

## 根拠

- option の default と auto mode の説明: `src/program/generate.cpp:995-998`。
- CLI usage と parser・引数欠落時の処理: `src/program/generate.cpp:1163,3293-3298,3571-3579`。
- fallback の validation と DFlash2 の適用条件: `src/program/generate.cpp:5326-5333,6765-6773`。
- request key の解析、優先順位と drafter 選択: `src/program/generate.cpp:15121,15130-15142,15171,15211-15234`。
- 学習状態の保持と更新: `src/program/generate.cpp:1002-1003,18666-18676`。
