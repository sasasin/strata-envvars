# `--drafting`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--drafting` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` |

## 役割

生成時に先読みする drafter の選択を指定します。選択は起動設定の `drafting` として保存され、server が engine 起動時に適用します。モデルが DeepSeek で複数ファイル構成の場合は、この選択表示より DSpark が使われます（`strata_cli/launch/runner.py:1851-1855`）。

## 使い方

```sh
strata launch --model q2_0 --drafting mtp --plan
```

`--plan` は選択結果を表示し、変更や取得を行いません。実起動時は `--plan` を外します（`strata_cli/launch/cmd.py:138-140`, `strata_cli/launch/cmd.py:733-760`）。

## 値と既定値

- `auto`: `strata_control/drafting.py` の GPU architecture クラス別推奨表から選びます。判定は最初に表に一致したカードの architecture を使い、未知・空の architecture は `other` です（`strata_control/drafting.py:58-79`）。この revision の全推奨行は MTP のため、現状の `auto` は MTP を選びます（同 `:50-56`）。
- `mtp`: engine 標準の MTP drafter を使います。
- `dflash2`: DFlash2 drafter を要求します。現 revision では serve 時の適用が無効なため、後述のとおり MTP にフォールバックします。
- `off`: draft layer を無効にします。
- 省略時: 新規設定では `LaunchSettings.drafting` は `None` で、`drafting` module の既定 `auto` として扱われます。プリセットを指定した場合は、プリセット値が残ります。コマンドライン指定はプリセット値を上書きします（`strata_cli/launch/settings.py:77-95`, `strata_cli/launch/cmd.py:197-203,234-235`, `strata_control/drafting.py:23-25,136-139`）。

parser は前後空白を除き小文字化してから候補と照合します。従って大文字・前後空白を含む表記も同じ値に正規化されます。候補外の値は `argparse.ArgumentTypeError` となり、選択肢を含む usage error で終了します（`strata_cli/launch/cmd.py:37-45,104-107`）。

## 実行時の動作

値を指定すると `settings_from_args` が設定オブジェクトへ反映します。起動設定生成時は値を run config の `drafting` に保存し、server が各 engine 起動時に `drafting.apply` を呼んで engine 引数を調整します（`strata_cli/launch/cmd.py:234-235`, `strata_cli/launch/runner.py:371-407`, `serve/server.py:3086-3096`）。`--save-preset NAME` を併用すれば選択はプリセットに保存され、既存プリセットを `--preset` で指定しただけならフラグの変更はその起動分のみです（`strata_cli/launch/cmd.py:788-792`）。

`off` は run config の `mtp` を false にし、draft-layer helper で `--mtp` 引数を除去します。`--mtp off` も同じく draft layer を切ります。一方、明示的な `--drafting mtp` / `dflash2` は、保存設定に `mtp: false` があっても server 側で true に戻します（`strata_cli/launch/runner.py:392-407`, `strata_control/drafting.py:215-230`, `serve/server.py:3097-3102`）。

### 現 revision の DFlash2 制約

`strata_control/drafting.py` は `ENGINE_SERVES_DFLASH2 = False` と定義しています。このため `dflash2` を指定しても、対象 family の場合は「この mode では DFlash2 は利用不可」、対象外 family の場合は「Qwen3.8-Flash-Next 専用」という理由を記録し、MTP を使います。`auto` も現在の推奨表では MTP です（`strata_control/drafting.py:50-56,141-155,162-176`）。engine 引数として `--draft dflash2 --draft-model ...` を付ける経路はフラグが有効な場合の実装としてありますが、この revision の serve 選択からは到達しません（同 `:172-176`）。

Runner の不足 drafter 取得も `needs_pack` が true のときだけ行われ、同関数も `ENGINE_SERVES_DFLASH2` を条件に含めます。したがって現 revision でこの option を指定したことによる DFlash2 取得・pack 作成は発生しません（`strata_cli/launch/runner.py:1212-1233,1730-1737`, `strata_control/drafting.py:179-184`）。これは parser の help が記す「DFlash2 は一度 1.2 GB を取得し、不適用時は MTP」という説明のうち、取得部分が現行 serve 条件と一致しないことを示します（parser help: `strata_cli/launch/cmd.py:104-107`; 実装条件: `strata_control/drafting.py:141-146,172-184`）。

## 適用条件と副作用

- DFlash2 の対応 family は `qwen` と `gyro`、モデル名 fallback 判定は Qwen3.8-Flash-Next 系に限られます。ただし family が与えられる Terminal 起動では family で判定されます（`strata_control/drafting.py:102-111`）。現 revision では serve 非対応判定が優先され、DFlash2 は起動されません。
- `--plan` は推奨・選択結果だけを表示し、設定変更や download をしません（`strata_cli/launch/runner.py:1851-1862`, `strata_cli/launch/cmd.py:733-760`）。
- 実起動では run config が launch 用の JSON ファイルとして書かれます（`strata_cli/launch/runner.py:1235-1244`）。`--save-preset` を使う場合はプリセットの保存も行います（`strata_cli/launch/cmd.py:788-792`）。
- engine の `/metrics` に記録された実 drafter が要求と異なる場合、Runner は起動後に理由を通知します。通知取得は best effort で、接続に失敗した場合は追加表示しません（`strata_cli/launch/runner.py:1660-1672`; 状態構築: `serve/server.py:1128`, `strata_control/drafting.py:280-290`）。

## 出力とエラー

- 不正な値は parser の usage error になります。値を取らない `--drafting` や後続値の欠落も parser で拒否されます（`strata_cli/launch/cmd.py:104-107`; parser 登録と parse: `strata_cli/cli.py:2223-2231`）。
- `--drafting dflash2` が現 revision で適用できない場合、server は `[strata] drafting: ...` を標準出力へ出し、engine の `/metrics` にも理由を載せます。起動自体は MTP で続行します（`serve/server.py:3088-3096`, `strata_control/drafting.py:162-176,280-290`）。
- `--plan` の人間向け表示には選択された drafter と fallback 理由が含まれます。JSON 出力では計画データの `drafting` に入ります（`strata_cli/launch/cmd.py:733-759`, `strata_cli/launch/runner.py:1846-1860`）。

## 根拠

- parser、値検証、help: `strata_cli/launch/cmd.py:37-45,75-107`
- CLI 値から設定への反映、plan・起動・preset 保存: `strata_cli/launch/cmd.py:197-235,733-760,784-800`
- 値の既定、推奨表、DFlash2 の判定・fallback: `strata_cli/launch/settings.py:77-95`, `strata_control/drafting.py:23-30,50-79,136-184,215-230`
- 起動 config と MTP 相互作用: `strata_cli/launch/runner.py:371-407,1212-1244`
- server の各起動への適用、通知: `serve/server.py:3086-3102`; `strata_cli/launch/runner.py:1660-1672`
- 実行計画での適用結果: `strata_cli/launch/runner.py:1851-1862`
