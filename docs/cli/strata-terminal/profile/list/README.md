# `strata profile list`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile list` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |
| 位置引数 | なし |

## 役割

ユーザー設定ディレクトリに保存された serving profile を列挙します。各 profile は setup が作る run config と分けて保存される serving 設定です。通常の表示では profile ID と revision を表示し、profile を読み込めない場合はその理由を表示します。JSON 出力では source config のパスも含む profile 情報を返します。

このコマンドは profile の一覧確認用です。作成・編集には [`strata profile create`](../create/README.md) などを使い、profile の内容確認には [`strata profile show`](../show/README.md) を参照してください。関連コマンドの索引は [`docs/cli/README.md`](../../../README.md) にあります。

## 使い方

```sh
# profile ID と revision を人向けに表示
strata profile list

# profile の内容を JSON で取得
strata profile list --output json

# --json は --output json の別表記
strata profile list --json
```

profile の一覧が空なら人向け出力は `No saved profiles` です。

## 実行時の動作

- `--output` は `human` または `json` を取り、省略時は `human` です。`--json` は同じ one-shot parser 群へ登録される別表記で、指定すると `--output json` として処理されます。`--quiet` もこのコマンドで受理され、人向け出力を抑制します（JSON 出力は抑制されません）。
- 一覧の保存先は `STRATA_PROFILE_DIR` があればそのディレクトリ、なければ Windows では `%APPDATA%\Strata\profiles`（`APPDATA` 未設定時はホーム配下の `AppData\Roaming\Strata\profiles`）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）です。
- 保存先ディレクトリが存在しなければ空の一覧を返します。存在する場合は名前順に `*.json` を走査します。ファイル名の stem が小文字英字で始まり、小文字英数字・`_`・`-` のみからなる最大64文字の profile ID に合わないファイルは一覧から除外されます。
- 各 profile を読み込み、妥当なら ID、SHA-256 の先頭16桁からなる revision、source config パスを一覧項目に含めます。profile として読めないものは ID とエラー文字列を含む項目になります。profile の妥当性確認には schema version、ファイル名と ID の一致、絶対パス形式の source config、override 値の検査が含まれます。
- 人向け出力は各項目を `ID  revision` の形で改行表示し、エラー項目では revision の代わりにエラーを表示します。JSON 出力は `schema_version: 1`、`ok: true`、`profiles` を含む一つの JSON オブジェクトです。

## 適用条件と副作用

profile の一覧処理自体はサーバーを起動せず、profile 内容や run config を書き換えません。ただし各ファイル読込時にアクセス拒否となった場合、Windows では対象がユーザー所有の Strata データ領域内ならアクセス権を一度修復して再読込します。この修復経路ではファイルの所有者や ACL を変更することがあります。通常の読込で権限エラーがなければ修復は行われません。

## 出力とエラー

- 正常終了は終了コード `0` です。空の一覧も正常終了です。
- 不正・破損・読込不能な profile は通常、一覧全体を失敗させず項目ごとの `error` として返します。
- 一覧取得で処理されない `OSError` などが発生した場合、共通エラー処理が人向けなら stderr に `strata: ...` を出し、JSON モードなら `ok: false` と `error` を含む JSON を出します。ファイル操作エラーの終了コードは `6` です。profile の読込時に `ProfileError` 化されるエラーは項目内に記録されるため、これとは異なります。

## 根拠

- `strata_cli/cli.py:69-76` — `profile list` と `--output` の parser 定義。
- `strata_cli/cli.py:508-515,2232-2237` — `--json` / `--quiet` の追加と JSON 別表記の処理。
- `strata_cli/cli.py:958-967,527-542` — 一覧結果の取得、人向け表示、JSON 成功出力。
- `strata_cli/cli.py:2119-2128,2166-2183` — profile コマンドへの dispatch と `ValueError` / `OSError` のエラー出力・終了コード処理。
- `strata_control/profiles.py:25,38-55,120-132,150-182` — ID 規則、保存先、profile 読込・検証、一覧対象と項目形式。
- `strata_control/private_files.py:442-484` — Windows のユーザー領域でアクセス拒否時に ACL を修復して再試行する処理。
- `docs/TERMINAL.md:46-59` — profile の役割と関連する CLI 利用例。

調査範囲はこの checkout の指定 commit に含まれる POSIX/Windows 共通の Python CLI ソースです。別途ビルド済み配布物や Windows 実機での動作は確認していません。
