# `--output`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` |

## 役割

出力形式を選びます。`json` と `jsonl` は機械向け出力として扱われ、操作の成否を JSON で報告します。加えて、機械向けモードでは、エンジン稼働中に待機するかを端末で尋ねず、待機時間がなければビジーとして失敗します。したがって、既定の `human` から変更すると、表示形式だけでなく対話の有無も変わります。

## 使い方

```sh
# ビルド済みエンジンを追加して選択し、結果を JSON で受け取る
strata components add-build /path/to/build --output json

# 同じ操作を人向け表示で行う（--output の既定値）
strata components add-build /path/to/build
```

どちらの例もビルド済みエンジンをローカル component directory に追加し、利用エンジンとして選択します。`/path/to/build` は `strata` 実行ファイルと、必要なライブラリおよび `BUILD.json` があるビルドフォルダーに置き換えてください。

## 値と既定値

- 省略時は `human` です。
- `human`、`json`、`jsonl` 以外は parser の `choices` により受理されません。
- 別名はありません。parser 登録は共通 option として `strata components add-build` に適用されます。
- ソースでは同じオプションの重複指定を個別処理していません。

## 実行時の動作

- `human` では成功時に追加したバージョン、ローカル build で署名されていないこと、`strata components use newest` でリリース版に戻れることを標準出力へ表示します。
- `json` では成功時に `schema_version: 1`、`ok: true`、`added` の package 情報、およびエンジン切替結果を含む JSON オブジェクトを標準出力へ出します。
- `jsonl` も machine mode として扱われ、成功結果は JSON オブジェクトです。待機が発生する場合は、待機中イベントを JSONL で出した後に成功またはエラーの JSON を出すことがあります。通常の追加処理自体は進捗イベントを生成しません。
- コマンドはまず build を検証し、component directory 配下の staging directory に選ばれたファイルをコピーして manifest を生成・検証し、最終 package directory へ移します。その後 `use_engine` を呼び、選択した package を今後起動時に使う状態へ切り替えます。`--output` はこの追加・切替処理自体を省略しません。
- `--output json` または `jsonl` では、稼働中エンジンを待つかの対話確認は行われません。正の `--wait` を指定すると停止まで待機し、JSONL では待機イベントを出します。待機可能な時間内に停止しなければ busy error になります。`human` で stdin が端末なら `--wait` なしのとき待つかを尋ね、非対話環境では尋ねずに busy error になります。
- `--backend` を指定した場合はその backend のハードウェア情報を選択時の文脈に使います。選んだ backend が複数 GPU の別カードに該当すると、engine 切替時に backend 選択も保存される場合があります。

## 適用条件と副作用

- 入力フォルダーには実行可能な `strata`（Windows は `strata.exe` も可）が必要です。`BUILD.json` の backend 情報がない場合は `--backend` が必要です。指定・検出された backend がホストでサポートされない場合や、検出 GPU と異なる backend の場合は拒否されます。CUDA/HIP で architecture 情報が manifest にない場合はホスト GPU から補完し、補完できず非 CPU backend の architecture が空なら拒否されます。
- 実行ファイルを `--version` 付きで最大10秒実行してバージョンを読み取ります。実行不能、タイムアウト、失敗終了、バージョン番号なしはいずれも追加を拒否します。コピー対象は entrypoint、直下の共有ライブラリ、定義済み vision helper、`BUILD.json` です。
- 同じ version/platform/backend の `-local` package がすでに存在すると、上書きせず拒否します。新規 package は署名なしの `local` manifest と各ファイルの SHA-256 を持ちます。選択後は起動時に通常自動選択されるリリース版から pin されることがあり、`strata components use newest` で戻せます。
- component directory への package 作成と engine 選択状態の更新を行います。ネットワーク取得はありません。`STRATA_REQUIRE_SIGNED_COMPONENTS` が有効な環境では署名のない package の検証に失敗し、追加後の選択は失敗します。この順序では package のコピーが先に完了しているため、選択に失敗しても作成済み package は自動削除されません。

## 出力とエラー

- 成功は終了コード `0` です。
- 入力フォルダー、backend 情報、または architecture 情報の不足、同名 local package の存在などは終了コード `2`。backend がホスト非対応、build 実行・検証失敗、署名要件や engine integrity の問題などは主に終了コード `5`。エンジン稼働中に切替できない場合は終了コード `7` です。
- 人向けの失敗メッセージは `strata: ...` として標準エラーへ出ます。`json` / `jsonl` では `schema_version`、`ok: false`、`error.code`、`error.message` を含む JSON を標準出力へ出します。引数値が `choices` に合わない場合は処理関数に入る前に parser が拒否します。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser における `--output` の選択肢と既定値。
- `terminal/strata_cli/update_cmd.py:95-99` — `add-build` の parser 登録、位置引数 `folder`、共通 option の適用。
- `terminal/strata_cli/cli.py:2210-2212` — `components add-build` を `update_cmd.run` へ振り分ける箇所。
- `terminal/strata_cli/update_cmd.py:117-139` — human / JSON / JSONL の event 出力規則。
- `terminal/strata_cli/update_cmd.py:303-321, 374-386` — machine mode 判定、context 構築、失敗を JSON または標準エラーへ出す経路。
- `terminal/strata_cli/update_cmd.py:425-442` — 稼働確認、build 追加、engine 選択と成功時出力。
- `terminal/strata_cli/update_cmd.py:500-515`、`terminal/strata_control/updater.py:381-392` — 待機確認、待機イベント、待機期限後の busy error。
- `terminal/strata_control/local_engine.py:41-74, 127-178` — entrypoint・バージョン・backend・architecture の検証、コピー・manifest 作成、重複拒否。
- `terminal/strata_control/engine_library.py:211-228, 277-312`、`terminal/strata_control/updater.py:1701-1751` — 稼働中の切替待機、package 検証、engine pin と履歴を含む状態更新。
- `terminal/strata_control/engine_component.py:386-413, 447-474` — `STRATA_REQUIRE_SIGNED_COMPONENTS` の署名要件と package file hash 検証。
