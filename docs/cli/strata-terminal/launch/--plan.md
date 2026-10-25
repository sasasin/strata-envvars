# `strata launch --plan`

`strata launch` が選択した設定で行う処理の概要を表示し、起動せずに終了するフラグです。引数値は取りません。既定値は無効（指定なし）です。

```sh
strata launch --plan --model q2_0
strata launch --plan --preset "IQ3_XXS 128K" --output json
```

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。対象 checkout の作業状態は `## main...origin/main` で、未コミット変更は表示されませんでした。

## 値と適用範囲

- `strata launch` の parser にある真偽値オプションです。`--plan` 自体に値、別名、追加 validation はありません（`strata_cli/launch/cmd.py:75-82,127-140`）。
- `--preset` とそのほかの launch 設定フラグを通常どおり取り込み、プリセットの内容にコマンドライン指定を重ねます（`strata_cli/launch/cmd.py:197-281`）。`--model` はカタログで解決され、`--model-path` は既存ファイルの指定です。
- 実行時に `--plan` が有効なら TUI を開かず、選択のための質問を避けます。また、モデルなどの選択肢がなくても plan 分岐へ進めます（`strata_cli/launch/cmd.py:688-710`）。モデルが未指定なら通常の既定値選択が試みられ、適合候補がなければエラーになります（`strata_cli/launch/cmd.py:302-355`）。
- 管理オプション `--list-presets`、`--delete-preset`、`--stop`、`--status`、`--show-key` は plan 分岐より先に処理されます。併用時は該当する管理処理が優先され、plan は出力されません（`strata_cli/launch/cmd.py:643-677,733-760`）。

## 表示と処理

plan はプロファイル名、key を伏せた設定、警告、同等の起動 flags、実行段階、モデル情報、ダウンロード見積もり、drafting の選択をまとめます。DeepSeek-V4.1-Flash の場合は GPU/RAM/SSD 上の配置見積もりも含みます（`strata_cli/launch/runner.py:1827-1849,1985-2009`）。ダウンロード量の見積もりには不足しているモデル関連ファイル、必要に応じて draft layer・picture reader、engine の利用可能性などが反映されます（`strata_cli/launch/runner.py:1702-1784`）。見積もり処理が失敗した場合は、その部分を「算定できなかった」とする plan を返す経路があります（`strata_cli/launch/runner.py:1837-1841`）。

- 通常の人間向け出力ではモデル、context、pictures、並列数、ダウンロード、drafting、tuning、共有方式と port、警告などを表示し、最後に `Nothing was changed.` と出して終了コード 0 を返します（`strata_cli/launch/cmd.py:733-760`）。
- `--output json` を併用すると、成功時は `schema_version: 1`、`ok: true`、`plan` を含む JSON を stdout に出します。設定内の API key は `set` または `null` に置き換えられます（`strata_cli/launch/cmd.py:634,733-738`; `strata_cli/launch/settings.py:114-118`）。失敗時は `ok: false` と error を含む JSON です（`strata_cli/launch/cmd.py:636-641`）。`--output` の有効値は `human` / `json`、既定値は `human` です（`strata_cli/launch/cmd.py:140`）。
- `--plan` は通常起動の `runner.run()` に進まず、実行段階の計画生成後に return します。そのためこの分岐では engine/model のダウンロード、設定保存、tuning、server 起動は行いません（`strata_cli/launch/cmd.py:733-760,784-792`; 通常起動処理: `strata_cli/launch/runner.py:2011-2025`）。`--save-preset` を一緒に指定しても、保存処理より前に return するためプリセットは保存されません（`strata_cli/launch/cmd.py:733-760,788-792`）。
- `--move-data` を明示していても plan 分岐では移動処理に到達しません。移動選択の値は plan に渡されますが、`Runner.plan()` はそれを実行しません（`strata_cli/launch/cmd.py:504-526,731-735`; `strata_cli/launch/runner.py:1827-1849`）。

## 検証、失敗、副作用

`--plan` に固有の値検証はありませんが、ほかの指定は通常どおり検証されます。たとえば model 名はカタログで解決され、data directory は使用可能性を確認し、API key 環境変数は空・未設定なら失敗し、`--gpu` と `--gpu-roles` は同時指定できません（`strata_cli/launch/cmd.py:197-247,258-268`）。`--context`、`--port`、`--parallel` などもそれぞれ parser の型変換・範囲検証を受けます（`strata_cli/launch/cmd.py:48-72,94-100`）。既定値適用後に error level の notice があれば plan 出力前に終了します（`strata_cli/launch/cmd.py:721-725`）。

指定された `--model-path` が存在しない、またはモデルとして使えない場合は plan 作成前に失敗します（`strata_cli/launch/cmd.py:717-720`; `strata_cli/launch/runner.py:1149-1173`）。引数・設定の `ValueError` やプリセットエラーも失敗経路です。人間向け出力ではエラーを stderr に表示し、通常のエラーコードは 2、launch error では内容に応じたコード（例: model path の不正は 2 または 5）を返します。JSON 出力では同じ失敗を error object にします（`strata_cli/launch/cmd.py:636-641,832-838`; `strata_cli/launch/runner.py:1162-1173`）。

「何も変更しない」は launch の永続的な設定・ダウンロード・server を開始しない意味です。調査した経路では、plan より前に `Catalog` が installation root に `mkdir(parents=True, exist_ok=True)` を行うため、ディレクトリがなければ作成され得ます（`strata_cli/launch/catalog.py:223-249`）。また、共有アクセス用 key の既定値生成や `--new-key` による key 生成は plan 前にメモリ上で起こり得ますが、plan 分岐では保存されず、JSON の設定出力でも値は伏せられます（`strata_cli/launch/cmd.py:721-737`; 既定 key: `strata_cli/launch/cmd.py:341-350`）。plan はハードウェア、ディスク、モデルファイル、既存設定などを読み取って見積もるため、結果は実際の起動時点の状態と異なる可能性があります。

## 根拠

- `strata_cli/launch/cmd.py:75-82,127-140` — launch parser、`--plan` の宣言、`--output` の選択肢と既定値。
- `strata_cli/launch/cmd.py:197-281,302-355` — preset/引数の合成、入力検証、既定値と warning/error の適用。
- `strata_cli/launch/cmd.py:630-641,679-760,784-792,832-838` — Catalog 初期化後の plan 分岐、出力形式、早期 return、失敗経路と通常起動後の保存処理。
- `strata_cli/launch/runner.py:1149-1173,1702-1784,1827-1862,2011-2025` — model path 検査、ダウンロード見積もり、plan の内容、通常の実行処理。
- `strata_cli/launch/catalog.py:220-251` — Catalog が installation root を作成してから catalog を初期化する処理。
- `strata_cli/launch/settings.py:114-118,173-207` — key を含めない設定表現、access/port/parallel の notice 検証。

## 関連文書

- [`strata launch` コマンド概要](README.md)
- [CLI オプション索引](../../README.md)
- [調査基準](../../001_investigation.md)
