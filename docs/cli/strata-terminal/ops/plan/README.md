# `strata ops plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops plan` |
| 位置引数 | `name`（保存済み recipe 名） |
| 必須オプション | `--profile PROFILE` |
| 出力 | `--output human\|json`（既定値 `human`）。`--json` は parser help 上で別名と説明される |

## 役割

指定した profile の保存済み operator recipe を読み、recipe 種別に応じて実行前検査を行い、予定される処理とその実行時の効果を表示します。plan 自体は recipe を実行せず、返却データでも `would_execute` は `false` です。recipe の実行は別コマンド `strata ops run` で明示します。

## 使い方

`strata ops init` で用意される標準 recipe 名を使う例です。profile `four-gpu` が存在し、recipe が初期化済みであることを前提とします。

```sh
# runtime restart recipe の内容と preflight を JSON で確認
strata ops plan restart --profile four-gpu --output json

# component 検査 recipe を確認
strata ops plan check --profile four-gpu

# calibration measurement recipe を確認
strata ops plan calibrate --profile four-gpu --output json
```

recipe 名は任意の保存済み recipe に置き換えられます。作成・初期化・編集・実行については [`strata ops`](../README.md) と [Terminal CLI の operator recipe 手順](../../../../../docs/TERMINAL.md#owner-editable-operation-recipes)を参照してください。

## 主な動作

recipe は profile に結び付いた型付き JSON で、対応する種別は `runtime.restart`、`engine.calibrate.measure`、`components.verify` です。plan は recipe と revision を読み、種別ごとの preflight を含む結果を構成します。

| recipe 種別 | plan が行う確認 | `run` した場合に予定される効果 |
| --- | --- | --- |
| `runtime.restart` | 管理中 runtime の状態と候補 profile / source を確認 | 現在の instance を drain し、新しい instance を起動。activation 失敗時は前の起動状態へ rollback を試みる |
| `engine.calibrate.measure` | config と component の検査、calibration tool の有無などを確認 | decode sweep 用に engine を起動し、新しい report を作成。run config は変更せず、毎回 `--exclusive` が必要 |
| `components.verify` | profile の component ファイルを検査。recipe の `live=true` なら host GPU 情報も問い合わせる | component を読み取って検査し、ファイルは書き込まない |

この表の run 時効果は plan の出力に記録される予定内容です。plan 自身が runtime を drain / start したり、calibration を測定したり、report を書いたりするわけではありません。calibration の report を tuning に適用する処理も別操作です。

## 出力とオプション

- `--output human`（既定）では整形した JSON plan を標準出力へ出します。`--output json` では `schema_version`、全体の `ok`、`plan` を含む一行 JSON を出します。
- `--json` は parser help で `--output json` の alias と説明されていますが、plan の成功経路は `a.output` だけを見て `a.json` を参照しません。そのため `--json` 単独では機械出力の envelope に切り替わらず、既定の整形 JSON plan が出ます。機械出力には `--output json` を指定してください。共通エラー経路では `--json` が JSON error の選択に使われるため、成功時と失敗時で形式が異なる場合があります。
- `--quiet` は one-shot command parser 群に共通で追加されており、このコマンドでも受理されます。しかし `_ops` の plan 分岐は `a.quiet` を参照せず、plan JSON を常に出力します。したがって `--quiet` は plan 出力を抑制しません。
- 有効な plan は終了コード `0`、preflight が `ok: false` の場合は plan 内の `exit_code`（runtime restart は通常 `6`、calibration / components は `5`）を返します。recipe や profile の読取・検証エラーは CLI の共通 error handler が stderr または JSON error として返します。

個別の option 文書は [CLI 索引](../../../README.md)の `strata ops plan` 節を参照してください。

## 適用条件と注意点

- `--profile` は必須です。`name` と profile ID は小文字英数字、`_`、`-` のみで指定します。recipe がない場合は `strata ops init --profile PROFILE` の案内付きで失敗します。
- recipe は profile の `.ops/<profile>/<name>.json` から読み込まれ、通常ファイルであること、64 KiB 以下であること、schema / ID / 種別 / typed parameters が有効であることを検証します。POSIX では recipe ファイルと関連ディレクトリに owner-only の権限も要求します。
- restart plan は管理中で ready 状態の runtime host が必要です。ローカルの owner control transport で状態・候補設定を照会します。稼働 runtime がない、host に接続できない、または source 変更の許可が不足する場合は plan が不成功になります。plan 結果の `would_drain` と `would_start` は `false` です。
- calibration plan は設定・component を検査しますが、測定 engine は開始しません。Terminal archive に calibration 用の `setup.py` と `tools/calibrate.py` がなく、`STRATA_INSTALL_DIR` にも full Strata folder がない環境では、tool unavailable と報告されることがあります。
- component recipe の既定値 `live` は `false` です。`true` の場合は GPU inventory の live probe を含みます。
- profile が preflight 中に変わった場合は再試行を求めて終了します。plan と後続 run の間の recipe / profile 変更を防ぐには、run 側で preview から得た revision 条件を指定してください。

## 関連文書

- [`strata ops` コマンド概要](../README.md)
- [CLI 索引と `strata ops plan` options](../../../README.md)
- [Terminal CLI operator recipe の利用手順](../../../../../docs/TERMINAL.md#owner-editable-operation-recipes)

## 根拠

- Strata `strata_cli/cli.py:255-290` — `ops plan` の階層、必須の `name` / `--profile`、出力形式。
- Strata `strata_cli/cli.py:508-516` — `--json` alias と `--quiet` の one-shot parser への追加。
- Strata `strata_cli/cli.py:1391-1447` — ops dispatch、plan 出力形式、終了コード。plan 分岐が `quiet` と `json` flag を参照しないことも確認。
- Strata `strata_cli/cli.py:2160-2183` — `ValueError` / `OSError` の共通エラー出力・終了コード経路。
- Strata `strata_control/recipes.py:28-58,93-114,180-196` — 種別、recipe / profile ID、型と値、保存ファイルの読込・検証。
- Strata `strata_control/recipes.py:329-360` — 種別ごとの preflight、実行効果の記録、preview 中の profile revision 再確認、`would_execute: false`。
- Strata `strata_control/runtime.py:402-425,734-740,1132-1164` — restart plan のローカル host RPC、ready 状態条件、drain / start を行わない preview。
- Strata `strata_control/calibration.py:95-111` — calibration preview が engine 起動・config 書込を行わないこと。
- Strata `strata_control/doctor.py:146-220` — component 検査と live GPU probe の条件。
- Strata `docs/TERMINAL.md:96-122` — operator recipe の利用例と plan / run の役割。
- 補助確認: 対象 checkout の `python strata.py ops plan --help`。parser 定義と一致し、ビルドやテストは実行していません。
