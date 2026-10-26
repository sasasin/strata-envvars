# `--model-config`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。Strata checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | run config JSON ファイルへのパス（`RUN_CONFIG.json`） |

## 役割

ローカルの engine package を導入する前のテスト起動で使うモデルの run config を指定します。検証対象の engine が指定モデルを読み込み、1 token の生成確認まで通るかを調べます。これは導入後に通常起動で使うモデルの選択・保存ではありません。

## 使い方

```sh
strata components install-file ./strata-engine.tar.gz --model-config ./models/run.json
```

`install-file` は engine package のファイルを位置引数に取り、`--model-config` は共通 parser から登録されます（`strata_cli/update_cmd.py:30-39,59-62`）。

## 値と既定値

- 値は parser で型変換されない文字列です。既定値は `None` で、parser 定義には独自のパス検査・JSON 検査がありません（`strata_cli/update_cmd.py:37-38`）。
- 省略時は、利用可能なインストール済みモデルの run config を検出します。保存済み profile が参照するモデルを優先し、同順位では model ID 順に選びます（`strata_control/updater.py:707-723`）。
- 空文字列を渡した場合も値の真偽判定により省略時と同じ検出経路になります。非空の相対パスはプロセスの作業ディレクトリ基準で読み込まれます（`strata_control/updater.py:878-890`）。
- run config は UTF-8 BOM 付き UTF-8 または UTF-8 の JSON として読み込み、object であること、`args` が文字列配列であること、`exe` と `tokenizer` が空でない文字列であることを検証します（`strata_control/profiles.py:135-147`）。ただしテスト用 config の作成時に `exe` は置換されるため、指定 config の `exe` の値自体は起動対象 engine の選択には使われません（`strata_control/updater.py:890-907`）。

## 実行時の動作

CLI は `a.model_config` を `Context.run_config` に渡し、`install_engine_file()` が検証済み package を共通の test-start 処理へ進めます（`strata_cli/update_cmd.py:193-195,208-217`; `strata_control/updater.py:1088-1092,1138-1145,994-1006`）。明示した非空の値が優先されます。値がなければ検出したインストール済みモデルを使い、モデルを検出できなければ新 engine の `--version` 実行だけを行う簡易確認になります（`strata_control/updater.py:878-886`）。

モデルを使う確認では、Strata は指定 config を読み込んでテスト用コピーを作ります。コピー上で `exe` を Strata engine component 参照に、`backend` を検証対象 engine の family に置き換え、`lib_dirs` を削除し、host を `127.0.0.1`、port を空きポート、log を一時 sandbox 内のファイルに設定します。`args` が文字列配列なら、確認負荷を軽くするため最大 context を 4096 に制限し、KV residency と vision reader の指定を除去します（`strata_control/updater.py:848-875,887-900`）。指定した元ファイルはこの処理では書き換えません。

検証は一時 profile/runtime/component 配下で行い、engine が ready になった後に必要なら生成確認を実行します。成功後はテスト runtime を停止し、一時 sandbox を削除します。検証成功後に engine が切り替わり、既存 engine は前バージョンとして保持されます（`strata_control/updater.py:878-881,901-934,994-1006,1023-1077`）。`--force` は同じ parser の別 option で、古い package や以前失敗した version の再試行条件に関係しますが、テストに使う config の選択規則は変えません（`strata_cli/update_cmd.py:36-38,193-195`; `strata_control/updater.py:1138-1145`）。

## 適用条件と副作用

- `--model-config` が使われるのは engine の test start 時です。ローカル package の形式・署名・全ファイル整合性・この PC との適合性確認はその前段で行われ、`--model-config` がこれらの判定を変更する処理はありません（`strata_control/updater.py:1088-1091,1102-1132`）。
- 指定 config の読み込みやテスト起動に失敗すると、新 engine は切り替わりません。非 busy の test-start 失敗は version と失敗理由を更新 state/history に記録します（`strata_control/updater.py:994-1022`）。
- engine が serving 中なら、`--wait` が有効な場合を除き install を拒否します。test start 中にも再確認し、他の engine が起動していた場合は switch を止めます（`strata_cli/update_cmd.py:34-35,208-212`; `strata_control/updater.py:1023-1024`）。
- インストール対象 archive はローカルに残されます。展開・テスト用 staging は処理後に削除され、成功時は選択 engine を有効にして旧版を保持します（`strata_control/updater.py:1088-1091,1142-1148,1056-1077`）。

## 出力とエラー

- 成功時は human 出力なら engine の更新結果、`--output json` または `--output jsonl` なら成功 JSON を stdout に出します（`strata_cli/update_cmd.py:39,208-217`）。
- 指定ファイルの不存在、読取不能、壊れた JSON、必須フィールド不備、またはモデルの起動・生成確認失敗は test-start failure として扱われ、通常は exit code `6` です。更新 state に失敗情報と履歴を記録し、現在の engine は維持します（`strata_control/profiles.py:135-147,236-249`; `strata_control/updater.py:85-86,121-128,890-907,923-927,1013-1022`; `strata_cli/update_cmd.py:246-247`）。
- option 自体の parser validation はないため、エラーは実際にテスト config を読む段階で発生します。machine output では共通 failure handler がエラー JSON を stdout に出します。human output では `strata: ...` を stderr に出します（`strata_cli/update_cmd.py:178-183,246-247`）。

## 根拠

- parser と共通 scope: `strata_cli/update_cmd.py:30-39,59-62`
- CLI から context への値の受け渡し、install-file 分岐、出力と失敗処理: `strata_cli/update_cmd.py:174-217,246-255`
- 既定 config の検出: `strata_control/updater.py:707-723`
- test start 用 config の加工、隔離、成功・失敗処理: `strata_control/updater.py:848-875,878-934`
- run config の形式検証: `strata_control/profiles.py:135-147,236-249`
- test start から切替までの処理: `strata_control/updater.py:994-1077`
- ローカル package 導入と `--model-config` による test start 呼び出し: `strata_control/updater.py:1088-1148`
