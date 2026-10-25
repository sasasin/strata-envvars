# `strata models inspect`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時のリポジトリ状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models inspect` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/models.py`、`strata_control/doctor.py` |
| 位置引数 | `model_id`（セットアップが書き込んだモデル設定名） |

## 役割

ローカルインストール内のモデル実行設定を選び、その設定が参照するエンジン、tokenizer、モデル用コンポーネントなどの存在状態を読み取り専用で調べます。コンポーネントの状態と、エンジン・backend による実行互換性は別に報告されます。設定があることや必要ファイルがそろっていることだけでは、モデルを実際にロードできるとは確認できません。

## 基本的な使い方

```sh
# Strata が見つけるインストールから設定 ID を調べる
strata models inspect qwen_iq3_xxs

# JSON 形式で詳細なコンポーネント報告を得る
strata models inspect qwen_iq3_xxs --output json

# 調べるインストールを明示する
strata models inspect qwen_iq3_xxs --install-dir /absolute/path/to/strata/install --json
```

`model_id` はパスではなく、セットアップ設定の ID です。`--install-dir` を省略すると、Strata 自身の設定・記憶済みのインストール・Desktop アプリの共有インストールなど、既知の場所から設定を探します。明示した場合はそのディレクトリだけが対象です。

## 実行時の動作

1. `model_id` が `[a-z0-9][a-z0-9_-]{0,127}` に一致することを確認し、既知のインストール場所を順に調べます。明示された `--install-dir` は既存の絶対ディレクトリでなければなりません。省略時は `STRATA_INSTALL_DIR` も探索先の指定として使われます。
2. 対象ディレクトリの直下から `strata-<model_id>.json` を選びます。設定を読み、必要なファイルやフォルダー、設定が参照する engine・tokenizer・追加コンポーネントを照合します。調査中に設定内容が変わっていないかも再読込して確認します。
3. 人間向け出力では、モデル ID、コンポーネント状態、engine compatibility が未検証であること、設定ファイルの場所、コンポーネント数と issue 数を表示します。JSON 出力にはモデル要約、設定ファイルの SHA-256、コンポーネント明細、issues が含まれます。

この処理本体はローカルの設定・ファイル状態を読むもので、モデルをロードしたり engine を起動したりしません。`doctor` の標準検査を呼び出し、ライブ GPU 検査引数は有効にしません。GPU driver probe の項目も、外部コマンドの有無を調べるだけで、デバイスや engine の互換性を確かめません。なお CLI 起動時には Windows で新規作成ファイルの所有者・既定 ACL を現在のユーザーにする準備をします。また Windows で Strata のファイルへの権限エラーが発生すると、共通処理が既知のユーザーデータ領域のアクセス権修復を試みてからコマンドを再実行する場合があります。

## 出力と失敗

- 既定の `--output` は `human`、選べる値は `human` と `json` です。`--json` は `--output json` の alias です。
- 成功時の終了コードは `0` です。`--quiet` は one-shot コマンドに追加される共通フラグで、人間向けの標準出力を抑えます。JSON 出力では quiet による抑制は行われません。
- 不正なモデル ID は終了コード `2`、対象設定が見つからない場合や設定を読めない場合は `5`、設定が検査中に変わった場合は `6` になります。human mode では `strata:` 付きのエラーを標準エラーへ、JSON mode では `ok: false` とエラー情報を標準出力へ返します。明示した install directory が存在しない、絶対パスでない場合はコード `5` です。
- エラー内容の詳細や、壊れた設定候補の扱いは失敗箇所により異なります。`inspect` は探索時に読めないディレクトリを飛ばし、その先にも ID がなければ「設定されていない」として扱います。

## 注意点

`component_status: present` は必須コンポーネントが見つかったことを示すにとどまり、実行の成功を保証しません。結果の `execution_compatibility` は `unverified` です。GPU/driver の実動作、モデルのロード、モデルの内容の完全性はこのコマンドの検査範囲外です。外部から入手した設定ファイル自体も変更しませんが、参照先の存在確認は行います。

## 関連文書

- [CLI 索引](../../../README.md) — コマンド階層とこのコマンドで受理されるオプション。
- [`strata models inspect` の利用者向け説明](../../../../TERMINAL.md) — ローカルモデル設定の探索と結果の解釈。
- [`--help`](--help.md)、[`--install-dir`](--install-dir.md)、[`--json`](--json.md)、[`--output`](--output.md)、[`--quiet`](--quiet.md) — 個別オプション。
- [`strata models list`](../list/README.md)、[`strata models import`](../import/README.md) — 関連するモデル確認コマンド。

## 根拠

- Strata `strata_cli/cli.py:141-156` — `models inspect` の登録、位置引数と `--install-dir` / `--output` の parser 定義。
- Strata `strata_cli/cli.py:508-515,550-603` — one-shot コマンドへの `--json` / `--quiet` 追加、`inspect` 呼び出し、human/JSON 成功出力。
- Strata `strata_cli/cli.py:2119-2141,2166-2188,2223-2237,2241-2248` — コマンド dispatch、エラー変換、JSON alias と quiet の処理。
- Strata `strata_cli/cli.py:2085-2104,2217-2225`、`strata_control/private_files.py:349-389,506-565` — Windows での起動時ユーザー既定設定と、権限エラー時のアクセス権修復・再実行。
- Strata `strata_control/models.py:30-35,62-73,88-103,106-129` — ID 形式、install directory の選択、設定ファイルの名前・読込検査。
- Strata `strata_control/models.py:158-182,213-229` — モデル要約、設定選択、コンポーネント検査と設定変更検知。
- Strata `strata_control/discovery.py:1-18,160-203` — 既知の install 場所の順序と read-only 探索。
- Strata `strata_control/doctor.py:1,146-235,238-272` — コンポーネントの読み取り専用検査、実行互換性を保証しない GPU 関連情報。
- Strata `strata_control/profiles.py:30-35,135-147` — 設定読込エラーと終了コード。
- Strata `docs/TERMINAL.md:16-28` — 利用者向けモデルコマンド例と検査結果の解釈。
