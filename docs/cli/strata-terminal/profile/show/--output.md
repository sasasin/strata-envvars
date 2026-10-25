# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile show` |
| オプション | `--output` |
| 別名 | `--json`（同じ JSON 出力を選ぶ one-shot alias） |
| 値 | `human` または `json` |

## 役割

出力形式の選択肢を parser で指定します。既定値は `human` です。ただし現行の `profile show` handler は human 用テキストを渡さず共通出力関数を呼ぶため、`human` を指定した場合もプロフィール情報を整形 JSON として stdout に出します。`json` は schema version と成功状態を含む単一 JSON オブジェクトを出力します。

## 使い方

```sh
strata profile show local
strata profile show local --output json
strata profile show local --json
```

実効設定と起動計画も表示する場合は `--effective` を併用できます。

```sh
strata profile show local --effective --output json
```

## 値と既定値

- 受理値は `human` と `json` のみで、未指定時は `human` です。その他の値は `argparse` が拒否します。
- `--json` は `profile show` を含む one-shot parser 群へ追加されるフラグで、指定時に `output` を `json` に設定します。`--output json` と同じ JSON 出力経路です。
- `human` 時の成功出力は `json.dumps(payload, indent=2, ensure_ascii=False)` による整形 JSON です。これは `profile show` が `_success` に `human=` の文面を渡していないためです。
- `json` 時の成功出力は `schema_version: 1` と `ok: true` に、プロフィールの `profile` と `revision` を加えた JSON オブジェクトです。`--effective` 併用時はさらに `plan` を含みます。

## 実行時の動作

`--output` の値は handler で `machine = (output == "json")` として使われ、プロフィールのロードや実効値自体を変えません。通常の `show` は保存プロフィールと revision を返し、`--effective` がある場合だけ run config を読み込んで launch plan を計算し、結果に加えます。`--effective` は `--output` とは独立した別オプションです。

出力先は stdout で、`--output` にファイルパスを渡す機能はありません。プロフィールの保存値を更新したり、server・engine を起動したりする処理は `show` の handler にありません。ただしプロフィールのロードでは、権限状態によって `read_bytes_repairing` がプロフィールファイルをその場で修復する経路があります。

`--quiet` も同じ one-shot parser 群に追加されます。`--output human` と併用すると成功時の stdout を抑止し、失敗時に捕捉した出力があれば stderr に出します。`--output json` は quiet 時も JSON 出力を維持します。

## 適用条件と副作用

- `--effective` なしでは run config の読込・launch plan の組み立てを行いません。ありの場合はプロフィールが参照する run config の読込・検証、実効設定の合成、engine 引数の組み立てを行いますが、plan を表示するだけで server/engine は起動しません。
- コマンドはプロフィールをロードするため、保存先は `STRATA_PROFILE_DIR` があればその値、なければ Windows では `%APPDATA%/Strata/profiles`（APPDATA 未設定時はユーザーホーム配下）、Unix 系では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` です。
- プロフィールファイルのアクセス権修復が必要な場合、読込時にファイルをインプレース修復します。これは `--output` の副作用ではなく `profile show` 共通のロード処理です。
- `--output json` の JSON 化は `allow_nan=False` です。出力不能な値が発生した場合の個別回復処理は確認できませんでした。

## 出力とエラー

- 成功時は終了コード `0` です。既定の `human` は整形 JSON、`json` は機械処理向け envelope 付き JSON を stdout に書きます。
- `json` 時の `ValueError` 系エラーは `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を stdout に出します。ProfileError 由来の終了コードは例として、未保存プロフィールが `5` です。その他の値エラーは例外の `exit_code` 属性がなければ `2` になります。
- `human` 時のエラーは `strata: <message>` を stderr に書きます。同じ未保存プロフィールの例では終了コード `5` です。
- `--output` に `human` / `json` 以外を指定したときの parser エラーは `argparse` の usage とエラー表示になり、終了コードは `2` です。

## 根拠

- `strata_cli/cli.py:77-80` — `profile show` parser と `--output` の選択値・既定値。
- `strata_cli/cli.py:508-515` — `profile_show` を含む one-shot parser への `--json`・`--quiet` 追加。
- `strata_cli/cli.py:958-968, 1015-1020` — JSON 出力フラグの判定、プロフィール・revision の結果、および `--effective` による plan 追加。
- `strata_cli/cli.py:527-542` — success/error の stdout/stderr、JSON envelope、human 未指定時の整形 JSON。
- `strata_cli/cli.py:2166-2188, 2232-2247` — 例外の JSON / stderr 経路、`--json` の値変換、`--quiet` の出力抑止。
- `strata_control/profiles.py:38-55, 150-166` — プロフィール保存場所、読込、アクセス権修復、未保存時の終了コード、構造検証。
- `strata_control/profiles.py:135-147` および `strata_cli/cli.py:545-547, 782-826` — `--effective` が参照する run config の読込と plan 作成。engine argv は組み立てるが、この経路では engine を起動しない。
