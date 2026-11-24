# `strata components update --model-config`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | run config JSON のファイルパス。値は必須。 |

## 役割

engine の更新時に行う新 engine のテスト起動で、検査対象モデルの run config を指定します。指定しない場合は、対象 engine component に対応するインストール済みモデルから選びます。この指定は通常のモデル起動や更新後の engine 選択を直接変更するものではありません。`strata components update` と `strata update` は共通 parser を使いますが、この文書は索引に従い前者の scope を扱います（`terminal/strata_cli/update_cmd.py:47-55,70-79`）。

## 使い方

```sh
# この run config を、新 engine のテスト起動に使う
strata components update --model-config /path/to/strata-example.json
```

## 値と既定値

Parser は `--model-config` に値を要求し、`RUN_CONFIG.json` を metavar として表示します。既定値は `None` で、parser 自体にはファイル存在・JSON 形式・run config 内容の検証処理がありません。通常の `argparse` の値引数なので複数回指定時は最後の値が残り、空文字列は後段で未指定と同様に扱われます（`terminal/strata_cli/update_cmd.py:54-55,323-325,1365`）。

## 実行時の動作

CLI は受け取った値を `updater.Context.run_config` にそのまま渡します（`terminal/strata_cli/update_cmd.py:323-325`）。新 engine をステージした後のテスト起動で、値があればそのパスを使い、なければ `discover_run_config` が見つけたモデルを使います。既定の探索では必要ファイルが揃い、廃止対象でなく、テスト対象 engine component に一致するモデルを候補にし、保存済み profile が使うモデルを優先します（`terminal/strata_control/updater.py:917-938,1360-1368`）。

明示した config の engine component がテスト対象と異なる場合、そのファイルは使わず、対象 component に一致するインストール済み config を再探索します。適合する config がなければ通常はモデルなしの binary smoke test（engine の `--version` 実行）にフォールバックします（`terminal/strata_control/updater.py:1364-1372`）。一致する config が読める場合も、元ファイルを書き換えて起動するのではなく、stage 配下に一時 sandbox を作り、設定を読み込んで必要なパス・engine・backend・引数などをテスト用に調整したコピーから起動します。テストは localhost の空き port を使い、一 token の生成まで確認して停止します（`terminal/strata_control/updater.py:1373-1439`）。

このオプションが使われるのは実際に新 engine のテスト起動へ進む場合です。`--check` は feed の確認結果を返して終了し、既にローカルにある engine への切替もテスト起動を行いません（`terminal/strata_cli/update_cmd.py:361-372`; `terminal/strata_control/updater.py:1518-1521,1539-1557`）。

## 適用条件と副作用

- `strata components update` の共通 parser はこの option を受け付けます。値の指定だけでは更新を開始せず、テスト起動が発生しない更新経路では参照されません（`terminal/strata_cli/update_cmd.py:70-79,323-325,361-372`）。
- 明示パスが存在しない、読めない、または JSON として不正な場合、パーサ段階では拒否されません。対象 component の不一致と判定されないままテスト開始時に読込が失敗すれば、test-start failure として扱われます。新 engine は切替前にテストされるため、その失敗時は更新 engine を有効化せず旧 engine を維持します（`terminal/strata_control/updater.py:1364-1379,1442-1449,1560-1588`）。
- 設定は一時 sandbox にコピーされ、元の run config を更新する処理はこの経路にはありません。sandbox は終了時に削除され、engine の test-start ログ・records は失敗または成功時に保持される処理があります（`terminal/strata_control/updater.py:1373-1375,1417-1425,1435-1456`）。
- `strata components update` は engine 更新に加えて、導入済みの shape engine と Control も更新対象にします。モデル config がテスト対象 component と合う場合に使われ、異なる場合はその component 用の候補へ切り替わります（`terminal/strata_control/updater.py:2099-2106,2118-2122,1364-1368`）。

## 出力とエラー

テスト起動で明示 config の読込などが失敗すると、更新結果の engine は `failed` となり、失敗理由が結果に含まれます。人間向け表示では engine が変更されなかった旨を表示し、機械出力は JSON/JSONL の選択に従います。CLI の失敗コードは通常 `6`（テスト起動失敗、旧 engine は引き続き使用）です（`terminal/strata_control/updater.py:1442-1449,1571-1588,2123-2129`; `terminal/strata_cli/update_cmd.py:175-190,373-382`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-55` — 共通 option parser の定義、値名と既定値。
- `terminal/strata_cli/update_cmd.py:70-79,323-325` — `components update` への登録と Context への転送。
- `terminal/strata_control/updater.py:917-938,1360-1372` — 既定の config 発見、明示 config の選択・component 不一致時の再探索と binary smoke fallback。
- `terminal/strata_control/updater.py:1373-1439` — sandbox config の生成と test start。
- `terminal/strata_control/updater.py:1442-1449,1560-1588,2123-2129` — test-start failure の変換、更新失敗扱いと結果への格納。
- `terminal/strata_cli/update_cmd.py:361-377` — `--check` の早期終了と update 実行経路。

