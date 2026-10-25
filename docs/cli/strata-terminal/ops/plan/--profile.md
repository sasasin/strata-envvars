# `strata ops plan --profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops plan` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前（1〜64文字。小文字英字で始まり、小文字英字・数字・`_`・`-` を使用） |

## 役割

計画対象となる保存済み profile を選びます。`strata ops plan` は、その profile に属する名前付き operator recipe を読み込み、recipe の種類に応じた事前確認を行います。値は profile 名として扱われ、run-config JSON のパスは受け付けません。

## 使い方

```sh
strata ops plan restart-main --profile local
```

`restart-main` は recipe 名、`local` は保存済み profile 名です。`--profile` は `ops` の全サブコマンド parser に登録されていますが、この文書の対象は `plan` スコープです。

## 値と既定値

- 値を1つ取り、省略できません。parser に `required=True` が指定され、既定値はありません。値なしでは `argparse` が usage とエラーを stderr に出し、終了コード 2 で終了します。
- profile 名は `[a-z][a-z0-9_-]{0,63}` に一致する必要があります。保存済み profile が存在しない場合は `strata_control.profiles.load` がエラーにします。
- JSON ファイルのパスらしい値であっても、このコマンドでは保存済み profile 名として検証されます。recipe ディレクトリの解決時に `profiles.load(profile)` が呼ばれます。
- profile は既定の設定場所（POSIX では `$XDG_CONFIG_HOME/strata/profiles`、未設定なら `~/.config/strata/profiles`。Windows では `%APPDATA%/Strata/profiles`）から読みます。`STRATA_PROFILE_DIR` を指定した場合はその場所が使われます。

## 実行時の動作

parser は各 `ops` サブコマンドに `--profile` を必須引数として追加し、`plan` の処理は `recipes.plan(a.profile, a.name)` に渡します。recipe の読み込み時に profile 名と recipe 名の形式を確認し、保存先 `profiles/.ops/<profile>/<recipe>.json` を読みます。ファイルは通常ファイルであること、64 KiB 未満であること、POSIX では所有者限定モードであることを確認し、schema と recipe kind も検証します。

profile が指定する事前確認は recipe kind ごとに異なります。

- `runtime.restart`: 対象 profile の runtime restart 計画を照会します。結果には restart の preflight と recipe の `startup_wait_s` が含まれます。
- `engine.calibrate.measure`: profile を使った calibration preview を行います。preview はエンジンを起動せず、設定ファイルも書かないことを返却データで明示します。
- `components.verify`: profile の run config を解決して component 検査を行います。recipe の `live` が true の場合はホスト GPU の照会も含みます。

いずれの分岐も recipe の実行ではなく、最終結果は `would_execute: false` です。profile revision が preview 中に変わった場合は再試行を促すエラーになります。

`--output` の既定値は `human` ですが、この `plan` 分岐の human 表示も整形済み JSON です。`--output json` または alias の `--json` を付けると、`schema_version`、`ok`、`plan` を含む一行 JSON を出力します。`--quiet` は共通 one-shot parser に登録され、成功時は stdout の plan 表示を抑制します。失敗時に捕捉した表示があれば stderr に出します。

## 適用条件と副作用

profile 名と recipe 名は保存済みファイルの選択に使われ、`--profile` 自体は操作を開始しません。recipe による事前確認は runtime 状態・config・component ファイルを読む場合があります。`components.verify` の `live=true` はホスト GPU 情報を照会します。profile 読み込み時、Windows でユーザー自身のデータ内ファイルへのアクセス拒否を修復できる場合、ACL を修復して再読込します。これを除き、recipe のロードと preview で確認できる範囲では、plan 分岐は recipe の実行・設定変更を行いません。

## 出力とエラー

- `operation.ok` が true なら終了コード 0、false なら operation が返す `exit_code` を使い、未指定の場合は 5 です。calibration と component verification の false 結果はコード上 5、restart preflight は返却値のコード（既定 6）を使います。
- profile／recipe が存在しない、名前・schema が不正、ファイル権限やファイル形式に問題がある場合は例外経路に入り、通常出力では `strata: <message>` を stderr に出します。`ProfileError` の終了コード（多くは 2 または 5）が維持されます。
- `--output json` または `--json` の例外出力は `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` 形式です。recipe の事前確認自体が `ok: false` を返した場合は、例外ではなく plan JSON と該当終了コードを出します。

## 根拠

- `strata_cli/cli.py:255-267` — `ops` のサブコマンド一覧、名前位置引数、`--profile` の必須登録、`--output` の既定値。
- `strata_cli/cli.py:508-515` — `ops` 各 parser に共通する `--json` と `--quiet`。
- `strata_cli/cli.py:2232-2247` — `--json` の適用、`--quiet` の成功時抑制と失敗時の stderr 表示。
- `strata_cli/cli.py:1391-1394,1440-1447` — profile 値を `recipes.plan` に渡す箇所、JSON/human 出力と成功・失敗時の終了コード。
- `strata_control/recipes.py:28-39,62-65,93-114,180-196` — profile／recipe 名の制約、recipe の保存先・読み込み・validation。
- `strata_control/recipes.py:329-360` — recipe kind ごとの preview と profile revision 再確認。
- `strata_control/profiles.py:25,38-45,48-55,150-166` — profile 名の形式、保存場所、未保存 profile と不正 profile のエラー。
- `strata_control/private_files.py:476-484` — ユーザー所有データのアクセス拒否時に Windows ACL を修復して再読込する経路。
- `strata_control/calibration.py:95-111` — calibration preview が engine 起動・設定書き込みを行わないこと。
- `strata_control/runtime.py:734-740` — restart plan の RPC 呼び出し。
- `strata_cli/cli.py:527-542,2166-2188` — エラー出力形式と例外から CLI エラーへの変換。

## 調査範囲

記載は指定 commit のソースに基づきます。異なる OS 上での実ファイル権限や runtime host が不在・応答不能の場合の個別診断文言は、この調査では実行して確認していません。
