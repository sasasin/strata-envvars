# `strata serve --batch-groups`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--batch-groups` |
| 別名 | なし |
| 値 | `auto` または 1〜1024 の整数。`strata serve` がこの範囲を検証する |

## 役割

複数の GPU にモデル層を分割し、エンジンが複数の会話スロットを扱うときに、スロットをいくつのグループに分けて GPU 段階間のパイプラインに流すかを指定します。これは `strata serve` の起動時オプションで、保存済み run config 自体は変更しません。省略時の解決はエンジンに委ねられます。

## 使い方

```sh
strata serve --profile ./strata-model.json --batch-groups auto --plan
```

`--profile` にはセットアップ済みモデルの run config、または参照可能な保存 profile を指定します。`--plan` を付けるとサーバーを起動せず、解決済みの設定とエンジン引数を確認できます。

## 値と既定値

- `auto` はエンジンに自動選択を明示的に要求します。
- `1` はグループを一つにし、グループ間のパイプラインを使わない指定です。
- `2` 以上は要求するグループ数です。エンジンは各グループのスロット数が均等になる必要があるため、後述の条件を満たさない場合は一つへ補正します。
- `strata serve` では省略時の parser 値は `None` です。CLI 指定、保存 profile の override、run config の `batch_groups` の順に値が選ばれ、どれにも値がなければ未指定のままです。したがって省略は明示的な `auto` と同一ではありません。
- 数値は `strata serve` で `1..1024` に制限されます。`auto` 以外の小数、0、負数、非数値、1024 超は拒否されます。値を複数回書いた場合、Python parser が最後に受け取った値を保持します。

## 実行時の動作

`strata serve` は実効値を検証し、必要なら `--batch-groups VALUE` を server 起動引数とエンジン引数へ反映します。`--plan` の出力には `effective` / `origin`、`server_argv`、資格情報を伏せた `engine_argv` が含まれます。明示値はこの起動だけに適用され、保存 profile や run config を書き換えません。

ネイティブエンジンでは `--batch-groups auto` は layer split の段数と `--batch` のスロット数に基づき、GPU 段数以下でスロット数を割り切れる最大のグループ数を選びます。数値を指定した場合はその数を要求します。複数グループのパイプラインは、`--batch` が有効で、layer split があり、グループ数がスロット数を割り切る場合に実行されます。実行経路では各グループが `--batch / groups` 個のスロットを持ち、GPU 段階を順に通ります。

グループ数を指定しない場合、layer split と `--batch >= 2` があるとエンジンの既定は自動選択です。ただし現在の実装では、既定の自動選択は `--batch-mtp` や `--adapt-async 1` が必要とするシリアル経路に譲ることがあります。また NVIDIA ビルドでちょうど2段の layer split の場合、既定の自動選択はシリアルの方が速いという分岐を持ちます。明示的な `--batch-groups auto` または数値指定は「グループ数を指定した」状態となり、この既定の譲歩分岐を通りません。`--batch-groups 1` は明示的にシリアルを選びます。

## 適用条件と副作用

- `--batch-groups > 1` は layer split と `--batch` の両方が必要です。エンジンは layer split がない場合、または `--batch` を割り切れない場合に警告を stderr に出し、1 グループへ補正します。
- スロット確保後に実際に収まる `--batch` 数が変わった場合も、自動グループ数は再解決されます。割り切れなくなった要求数は1へ補正されます。
- パイプライン経路では `--batch-mtp` のスロット単位ドラフトと batch adaptive tier（`--adapt-async 1`）は動きません。明示的な複数グループと `--batch-mtp` が重なると、エンジンは MTP draft が走らない旨を警告します。ドラフト領域の VRAM は確保されたままの場合があります。
- 要求した値は最終的な実行値の保証ではありません。エンジンが起動時にグループ数を補正することがあります。自動選択や補正理由はエンジンの stderr に出力され、起動ログおよび `--plan` の `notes` で確認できます。
- 同時に保存 run config の `args` に `--batch-groups` が含まれる場合、`strata serve --batch-groups`（または profile/config 由来の `batch_groups` override）は競合エラーになります。保存 run config の値を使う場合はこの CLI オプションを重ねて指定しないでください。

## 出力とエラー

CLI は無効な値を `strata: batch_groups must be auto or in 1..1024` などのエラーとして stderr（JSON 出力では error オブジェクト）に出し、通常は終了コード 2 で終了します。`--output jsonl` では failed イベントを stdout に出します。run config 引数との競合も終了コード 2 のエラーです。

エンジン側で `auto` が解決された場合は、グループ数、またはシリアル経路を選んだ理由が stderr に出ます。明示グループ数が layer split 条件や割り切り条件を満たさない場合は警告を出して一つへ戻します。サーバーやエンジンの起動失敗は個別の serve 起動エラー経路となり、このオプション固有のエラーとは区別されます。

## 根拠

- `strata_cli/cli.py:46-55` — `serve` parser 定義。`--batch-groups` は値を取り、デフォルトなし（`None`）。
- `strata_cli/cli.py:745-779` — CLI・保存 profile・run config の優先順位、実効値検証、run config 引数との競合。
- `strata_cli/cli.py:782-826, 915-941` — server/engine 引数への反映、plan 出力、入力値の検証とエラー処理。
- `strata_control/profiles.py:80-87, 98-117` — `auto` または正整数の変換と `1..1024` の範囲検証。
- `serve/server.py:3077-3085` — run config の engine args を組み立てる入口。
- `src/program/generate.cpp:2612-2617` — ネイティブ engine parser。`auto` または `atoi` による整数変換。
- `include/strata/program/batch_groups.hpp:3-11, 41-67` — 自動グループ数、未指定時の既定、MTP/adaptive/NVIDIA 2段時のシリアル分岐。
- `src/program/generate.cpp:5280-5297, 5357-5385` — 適用条件、auto 解決メッセージ、無効条件での警告と1グループへの補正。
- `src/program/generate.cpp:11739-11754, 11766-11772` — パイプライン経路、MTP 警告、グループ当たりのスロット数と終了経路。

調査範囲は上記 commit の checkout に含まれる Terminal CLI とネイティブ engine のソースです。バイナリの `--help` 実行、build、GPU 実行、性能測定は行っていません。性能上の優位性はここでは保証しません。
