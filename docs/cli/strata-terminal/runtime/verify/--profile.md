# `strata runtime verify --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み profile 名。必須。小文字 `a-z` で始まり、その後は `a-z`、`0-9`、`_`、`-` を使用でき、全体で最大 64 文字。 |

## 役割

検証対象となる、Strata が起動・管理しているローカル runtime を profile 名で指定する。指定した profile の revision を operation journal に記録し、その profile に結び付いた ready instance に対して検証を依頼する。run config のパスを指定するオプションではない。

## 使い方

```sh
# 保存済み profile `local` の runtime を検証する
strata runtime verify --profile local

# profile の runtime 状態と検証時の効果を表示する（検証要求は送らない）
strata runtime verify --profile local --plan

# 未ロードの場合にモデルをロードしてから生成確認を行う
strata runtime verify --profile local --load
```

## 値と既定値

`--profile` は必須引数で、parser 上の既定値はない。profile 名は runtime 操作の入口で検査され、`[a-z][a-z0-9_-]{0,63}` に一致しない値は拒否される。絶対パス、`/` または `\` を含む値、`.json` ファイル名は profile 名として受け付けない。通常の検証実行では profile が保存されていないとエラーになる。`--plan` 経路は profile ファイルを読まず runtime 状態を参照する。parser に重複指定時の独自処理はない。

profile の保存場所は `STRATA_PROFILE_DIR` があればその値、Windows では `%APPDATA%/Strata/profiles`（未設定時はユーザーホーム配下）、その他の環境では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）である。これは `--profile` の値の解釈を変えるものではなく、profile を検索するディレクトリを選ぶ。

## 実行時の動作

parser は `--profile` を必須文字列として受け取り、`_runtime` から `management.runtime_action` に渡す。そこで保存済み profile 名として検査した後、通常実行では profile の revision を読み、`runtime.verify` の operation として journal に記録してから owner runtime に要求する。したがって、実際の検証にはその profile で起動済みの、ready な管理対象 instance が必要。

検証は owner runtime が ready record と実プロセスの対応を確認し、API の telemetry から instance ID、launch attestation、model ID を照合する。その後、モデルがロード済みなら chat completions API に `max_tokens: 1` の生成 probe を送り、応答に少なくとも 1 completion token があるか確認する。モデルが未ロードで `--load` を指定していない場合は生成要求をせず、API identity と launch attestation の確認結果を返して `readiness_state: unloaded` とする。`--load` は未ロードモデルをロードして生成確認を行う指定である。

`--plan` を付けると、ready 状態と owner/instance ID、model state、および `--load` ならロードを試みるかを表示する。計画経路では owner runtime の status を参照するが、明示的な `runtime.verify` 要求や generation probe は実行しない。計画で表示した ID を実行時に固定したい場合は `--if-owner-id` と `--if-instance-id` を両方指定する。片方だけの指定は拒否され、plan と同時に指定することもできない。

profile の読込処理は通常のユーザー権限では読み取りを行う。昇格実行でアクセス保護が崩れた profile は、権限修復のため一度そのファイルを書き換える場合がある。通常実行ではさらに journal に operation の開始・完了結果が保存される。検証自体は server の起動・停止や profile 設定の変更を行わないが、`--load` によるモデルロードと generation probe は runtime/API に処理を発生させる。

## 適用条件と副作用

- 値は保存済み profile の名前に限られる。通常の検証では profile 名から run config と revision を読み、指定 profile の owner-controlled runtime を対象にする。`--plan` は profile ファイルを読まず、指定名の runtime 状態を確認する。
- `--plan` は実行前の状態確認用で、通常の検証や probe を行わない。実行時には runtime が ready でなければ失敗する。
- `--load` なしでは、未ロードモデルをロードしない。`--load` がある場合は検証中にモデルをロードし、生成要求を行う。
- `--wait` は既定 300 秒で、実行経路では有限秒数の 1〜600 秒に制限される。`--wait` は別オプションであり、`--profile` の値には影響しない。
- `--if-owner-id` と `--if-instance-id` は計画後の owner/instance 入替を検出するための対であり、profile 名そのものの validation とは別の実行前提条件。

## 出力とエラー

通常の human 出力では profile 名、runtime state、instance/API URL、launch 確認、generation readiness を表示する。`--output json` では結果を JSON で出力する。失敗した `start` / `restart` / `verify` では、取得できる場合に engine log の場所と末尾も stderr に表示する。

引数欠落や parser の不正引数は argparse の usage error（終了コード 2）。不正な profile 名は `ProfileError` として通常は終了コード 2、未保存 profile はコード 5、管理 runtime がない／停止中はコード 3、runtime が ready でない・ID が計画後に変化した・検証に失敗した場合は主にコード 6 となる。owner runtime との待機期限切れはコード 8 で、結果が不明な場合がある。

## 根拠

- `terminal/strata_cli/cli.py:244-253` — `runtime verify` parser、`--profile` 必須、`--wait` の既定値、`--load`、`--plan`、owner/instance 前提条件。
- `terminal/strata_cli/cli.py:1401-1443` — parser 値を runtime action に渡し、plan / human / JSON の結果と終了コードを処理する。
- `terminal/strata_control/management.py:193-205,243-278` — profile 名検証、plan 時の状態確認、通常実行時の revision 読込・journal 記録・runtime 呼出し。
- `terminal/strata_control/runtime.py:122-125,880-892,1390-1426` — profile 名形式、verify の範囲検証と owner RPC、ready instance と ID の検査。
- `terminal/strata_control/profiles.py:25-50,153-173,400-406` — profile 名の正規表現、profile 読込・未保存エラー、名前と JSON パスの解決境界。
- `terminal/strata_control/profiles.py:38-45,153-173` — profile 保存ディレクトリの選択と読込時のファイルアクセス。
- `terminal/strata_control/readiness.py:96-156` — API identity / launch attestation / model の照合、未ロード時の扱い、1 token generation probe。
- `terminal/strata_control/journal.py:381-398,407-410` — 直接 operation の開始・完了記録と verify 結果の保存。
- `terminal/strata_control/runtime.py:448-484` — owner runtime がない場合、接続失敗、待機 timeout、制御応答のエラー処理。

調査範囲は上記 checkout の CLI parser と Strata 所有の Python 実装。外部 API/server の内部挙動や、各モデルでのロード・生成時間は確認しておらず、ここでは断定しない。
