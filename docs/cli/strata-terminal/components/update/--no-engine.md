# `strata components update --no-engine`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--no-engine` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`）。省略時 `False` |

## 役割

この更新実行で Strata エンジンと、インストール済みのモデル形状別エンジンを更新対象から外します。Control の更新は別の選択なので、`--no-control` も付けなければ Control は引き続き更新対象です。

## 使い方

```sh
# エンジンを更新せず、Control は通常どおり更新対象にする
strata components update --no-engine
```

## 値と既定値

値や引数は不要です。parser は `action="store_true"` で登録し、既定値を明示していないため、未指定時は偽、指定時は真になります。値の範囲や値自体の validation はありません。同じ parser への重複指定も argparse の真偽フラグとして扱われます。`strata components update` と `strata update` の両方に同じフラグが別々に登録されていますが、この文書の対象は前者です（`terminal/strata_cli/update_cmd.py:70-79`）。

## 実行時の動作

`strata components update` は共通の更新処理へ進み、CLI は `engine=not a.no_engine` としてフラグを渡します（`terminal/strata_cli/update_cmd.py:370-377`）。偽（未指定）なら通常エンジン更新を組み立て、真ならそれを省きます（`terminal/strata_control/updater.py:2109-2122`）。同じ真偽値はモデル形状別エンジンの更新ステップにも渡され、真ならそのステップ一覧は空になります（`terminal/strata_control/updater.py:2099-2106`）。

エンジン更新を省いても、更新フィードの読み込み・署名確認・状態保存は行われます。`--check` を指定した場合は通常の実更新経路に入らず `updater.check()` を呼びます。この確認処理には `--no-engine` の値が渡されないため、エンジンの更新候補もレポートされます（`terminal/strata_cli/update_cmd.py:355-367`、`terminal/strata_control/updater.py:778-789`）。

## 適用条件と副作用

- 実更新時のみ、Strata エンジンとモデル形状別エンジンの更新ステップが省かれます。Control は `--no-control` が別途指定されない限り対象に残り、`--app` があればアプリのインストーラー取得も対象です（`terminal/strata_control/updater.py:2118-2122`）。
- `--no-engine` だけではフィード取得や状態ファイルへの書き込みを止めません。更新処理はフィードを開いて状態を保存し、終了時にも確認情報を保存します（`terminal/strata_control/updater.py:2112-2118`、`terminal/strata_control/updater.py:2132-2137`）。
- 読み込み中モデルへの確認・待機判定で比較する予定変更からもエンジンは除かれます。Control の更新が予定されていればモデル状態に応じた待機・確認・拒否処理は残ります（`terminal/strata_control/updater.py:2066-2096`）。
- `--yes`、`--stop-model`、`--start-again` は別のモデル停止・再開制御であり、`--no-engine` によって有効化・無効化されるものではありません（`terminal/strata_cli/update_cmd.py:67-79`、`terminal/strata_cli/update_cmd.py:418-421`）。

## 出力とエラー

このフラグ自体の専用出力や validation error はありません。実更新では省かれたエンジンの結果行は生成されず、実行されたコンポーネントの結果が通常の human / JSON / JSONL 出力経路へ渡されます（`terminal/strata_control/updater.py:2119-2129`、`terminal/strata_cli/update_cmd.py:371-377`）。フィード取得・署名・更新拒否など実行経路の失敗は共通処理で報告され、CLI は各例外に対応する終了コードを返します（`terminal/strata_cli/update_cmd.py:378-390`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:70-79` — `components update` parser と各フラグの登録。
- `terminal/strata_cli/update_cmd.py:370-377` — `--no-engine` の反転と更新関数への引き渡し。
- `terminal/strata_control/updater.py:2066-2096` — 更新予定の組み立てと、稼働中モデルに対する判定。
- `terminal/strata_control/updater.py:2099-2129` — エンジン／形状別エンジン／Control／アプリの各更新ステップの選択・実行。
- `terminal/strata_control/updater.py:778-789` — `--check` が各コンポーネントの候補を確認して状態を保存する処理。
- `terminal/strata_control/updater.py:451-470`、`terminal/strata_control/updater.py:2112-2118`、`terminal/strata_control/updater.py:2132-2137` — フィードを読み状態に記録する経路と更新後の状態保存。
- `terminal/strata_cli/update_cmd.py:418-421` — `--yes` / `--stop-model` / `--start-again` からモデルゲートを構成する処理。
