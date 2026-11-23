# `strata components add-build`（Terminal CLI）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| 入口 | Terminal CLI の `strata` 実行ファイル |
| 主な実装 | `terminal/strata_cli/cli.py`、`terminal/strata_cli/update_cmd.py`、`terminal/strata_control/local_engine.py`、`terminal/strata_control/engine_library.py` |

## 役割

`./setup --build` などでこの PC 向けに作った engine のフォルダーを検査し、実行可能性と build 情報を確かめてから、必要な engine ファイルを components store 内のローカル・未署名 package として登録します。登録後は `strata components use` と同じ engine 選択処理を実行し、次回以降に使う engine として選択します。これは署名付き feed から package を取得する更新操作ではありません。ローカル package は登録しただけでは自動選択されず、選択済みの場合にだけ起動対象になります（`terminal/strata_cli/update_cmd.py:95-99,425-441`、`terminal/strata_control/local_engine.py:1-10,127-177`、`terminal/strata_control/engine_component.py:1217-1228`）。

## 基本的な使い方

```sh
# build フォルダーを登録し、利用 engine に選択する
strata components add-build ./build

# build の backend を明示して登録する
strata components add-build --backend cpu ./build

# 自動化から実行し、成功・失敗を JSON で受け取る
strata components add-build --output json ./build

# 標準の per-user store の代わりに指定した store を使う
strata components add-build --components-dir ./strata-components ./build
```

`folder` は engine 実行ファイルと同じ場所にある runtime library、必要な vision helper、`BUILD.json` を含む build フォルダーを指します。例はコマンドの構文を示すもので、`./build` が実際に有効な build であることは保証しません（`terminal/strata_cli/update_cmd.py:95-99`、`terminal/strata_control/local_engine.py:41-46,109-116`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 通常実行 | `strata components add-build ./build` | 検査・登録後、同じ実行中に engine を選択する。成功時は登録先、version、未署名であること、戻し方を表示する。 |
| machine-readable 出力 | `strata components add-build --output json ./build` | 同じ検査・登録・切替を行い、成功時に `schema_version`、`ok`、登録情報を含む JSON を出力する。失敗時も JSON の error object を出力する。`jsonl` も parser が受理する。 |
| serving engine がある場合 | `strata components add-build --wait 30 ./build` | 指定秒数まで停止を待ってから engine を切り替える。待機時間を指定しない対話端末では待つか質問し、machine 出力または非対話では待機せず Busy エラーになる。 |

このコマンドに plan-only / dry-run モードはありません。`--output` は出力形式を変えるだけで、登録や切替を抑止しません（`terminal/strata_cli/update_cmd.py:47-57,425-442,500-515`、`terminal/strata_control/updater.py:381-392`）。

## 主な動作

1. parser は `folder` を必須位置引数として受け取り、`components add-build` 用の共通オプションを追加します（`terminal/strata_cli/update_cmd.py:95-99`）。トップレベル dispatcher はこのサブコマンドを `update_cmd.run` に渡します（`terminal/strata_cli/cli.py:2194-2213`）。
2. 共通処理は `--components-dir` または既定の per-user components directory を選び、`--backend` の指定があればその値を使って hardware 情報を決めます。未指定なら検出結果を使います（`terminal/strata_cli/update_cmd.py:265-280,283-300,303-321`）。
3. build folder を解決し、ディレクトリであること、OS に応じた `strata` / `strata.exe` が存在することを確認します。`BUILD.json` の backend 情報を読み、値がなければ `--backend` の指定を使います。backend が未確定なら拒否し、現在の platform で動かせない backend や検出 hardware と合わない backend も拒否します（`terminal/strata_control/local_engine.py:41-46,77-94,127-145`）。
4. engine を build folder を working directory として起動し、library 探索用環境変数にその folder を加えて `--version` を確認します。10 秒以内に成功終了し、出力から version 番号を読み取れない build は登録されません。CUDA / HIP の architecture 情報は `BUILD.json` を使い、未記載の場合は当該 PC から読める情報を補います。CPU 以外で architecture が決まらない場合は拒否します（`terminal/strata_control/local_engine.py:28,48-74,96-106,145-152`）。
5. 同じ version・platform・backend の local package が既にある場合は上書きせず拒否します。それ以外は components store の `engine` 以下に staging directory を作り、entrypoint、直下の runtime libraries、既知の vision helper、`BUILD.json` をコピーします。コピーしたファイルごとの SHA-256 とサイズを manifest に記録し、署名なし・`local: true` として検証後に最終 directory へ移動します。ネットワークからの取得は行いません（`terminal/strata_control/local_engine.py:30-32,109-116,153-177`）。
6. 登録した folder 名を `use_engine` に渡します。実行中の model / engine があれば指定された待機規則に従い、idle 後に engine の適合性と package を検証し、選択状態を保存します。適合する新しい released engine がある場合も、選んだ local build は pin され、local build が自動で選ばれることはありません（`terminal/strata_cli/update_cmd.py:425-441`、`terminal/strata_control/engine_library.py:211-228,296-312`、`terminal/strata_control/updater.py:1701-1748`、`terminal/strata_control/engine_component.py:1217-1228`）。

既定 store は Windows では `%LOCALAPPDATA%/Strata/components`、それ以外では `$XDG_DATA_HOME/strata/components`（未設定なら `~/.local/share/strata/components`）です。`STRATA_COMPONENTS_DIR` が設定されている場合はそちらが優先されます（`terminal/strata_control/engine_component.py:179-193`）。

## 注意点

- 成功すると選択状態も変わります。登録後の切替が server 使用中などで失敗すると、登録処理が先に完了しているため local package は store に残る場合があります。切替は稼働中の model が idle になるまで待つか、待機上限後に失敗します（`terminal/strata_cli/update_cmd.py:425-434`、`terminal/strata_control/local_engine.py:153-177`、`terminal/strata_control/engine_library.py:211-228`）。
- 登録された package は未署名です。[`STRATA_REQUIRE_SIGNED_COMPONENTS`](../../../../envvars/STRATA_REQUIRE_SIGNED_COMPONENTS.md) が有効な環境では署名検証で選択が拒否され得ます。package 登録後の切替時にも署名を検証するため、その場合も登録済み package が残る可能性があります（`terminal/strata_control/local_engine.py:166-170`、`terminal/strata_control/engine_component.py:386-405`、`terminal/strata_control/engine_library.py:305-312`）。
- 同じ local package がすでに存在する場合は置換しません。既存 package を削除してから再登録するようエラーになります（`terminal/strata_control/local_engine.py:153-158`）。
- 必要な各 flag の値・既定値は、[CLI 索引](../../../README.md) の `strata components add-build` 節から対応するオプション文書を参照してください。索引は `--json` と `--quiet` も掲載していますが、現行 parser のこのコマンドには登録がなく、共通 parser にあるのは `--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output` です。索引と parser の差異として報告します（`docs/cli/README.md:190-201`、`terminal/strata_cli/update_cmd.py:47-57,95-99`）。索引や他文書はこの依頼の編集対象ではないため変更していません。command parser は `--help`（自動追加）も持ちますが、調査対象 revision の CLI は実行していません。

## オプションの文書

個別オプション文書へのリンクは [CLI 索引の `strata components add-build` 節](../../../README.md) を参照してください。索引記載のうち `--backend`、`--components-dir`、`--feed`、`--force`、`--model-config`、`--output`、`--wait` は現行 parser にあります。一方、索引にある `--json` と `--quiet` はこのコマンドの parser に見つからず、差異があります（`docs/cli/README.md:190-201`、`terminal/strata_cli/update_cmd.py:47-57,95-99`）。parser 共通 option のうち `--feed`、`--force`、`--model-config` は受理されますが、add-build の処理本体は feed 取得や test-start を行わず、`--model-config` も利用しません（`terminal/strata_cli/update_cmd.py:425-442`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:95-99` — サブコマンド登録、位置引数、オプション scope。
- `terminal/strata_cli/cli.py:2194-2213` — `components add-build` の dispatch。
- `terminal/strata_cli/update_cmd.py:283-321,425-442,500-515` — hardware / store の準備、登録・切替の呼出し、成功出力、server 待機分岐。
- `terminal/strata_control/local_engine.py:41-74,77-116,127-177` — build folder の検査、version 起動確認、backend / architecture 判定、コピー・manifest 作成・重複拒否。
- `terminal/strata_control/engine_library.py:202-228,277-312` — 稼働中の model に対する切替制御と engine 選択。
- `terminal/strata_control/updater.py:381-392,1701-1748` — 待機 timeout と engine pin / 選択状態の保存。
- `terminal/strata_control/engine_component.py:179-193,386-405,1217-1228` — store の場所、未署名 package の検証条件、local package の自動選択除外。
- parser 定義上の共通 option と索引上の文書リンクはそれぞれ `terminal/strata_cli/update_cmd.py:47-57`、`docs/cli/README.md:190-201` を確認しました。安全な同一 revision の既存 CLI help は確認していません。
