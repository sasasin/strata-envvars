# `strata doctor --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存 profile 名、または run config JSON のパス（文字列）。省略可能。 |

## 役割

モデル固有の engine、tokenizer、run config が参照する component を調べる対象 profile / config を選びます。保存 profile を指定した場合も、doctor が診断するのはその profile の `source_config` です。profile の serving overrides を実行設定へ適用する機能ではありません（`terminal/strata_cli/cli.py:1062-1067`、`terminal/strata_control/profiles.py:400-406`、`terminal/strata_control/doctor.py:297-315`）。

## 使い方

```sh
# 保存済み profile の source config を診断
strata doctor --profile local

# 明示した run config JSON を診断
strata doctor --profile ./configs/model.json

# profile を指定せず、CLI 自体などの基本項目を確認
strata doctor
```

## 値と既定値

- 値を一つ取ります。parser は型・選択肢を指定せず、`required` でもありません（`terminal/strata_cli/cli.py:130-134`）。このオプション自体に既定 profile はなく、省略すると profile/config を選択しない経路になります。
- 値が `.json` で終わる（大文字小文字を問わない）、絶対パスである、または `/`・`\\` を含む場合、明示 config path として扱います。`~` を展開して絶対パス化し、profile 名にはフォールバックしません。したがって相対 JSON パスは実行時の作業ディレクトリ基準です（`terminal/strata_control/profiles.py:400-405`）。
- それ以外の値は保存 profile ID として解釈されます。ID は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です（`terminal/strata_control/profiles.py:25,48-55`）。
- 明示 config は `args` が文字列配列であり、`exe` と `tokenizer` が空でない文字列である必要があります。読めない JSON、形式不正、必須項目の欠落は拒否されます（`terminal/strata_control/profiles.py:135-150`）。保存 profile は schema version 1、profile ID、絶対 `source_config`、対応 override を検証します（`terminal/strata_control/profiles.py:120-132`）。

## 実行時の動作

`strata doctor` は `--profile` があれば `profiles.resolve()` で値を解決し、その path と保存 profile ID を `inspect_components()` に渡します。保存 profile の場合、run config は profile の `source_config` から読み込まれます。profile の `overrides` は doctor の component 検査には渡されず、検査対象の engine / tokenizer / 引数で指定された component の所在・状態を調べます（`terminal/strata_cli/cli.py:1062-1067`、`terminal/strata_control/profiles.py:400-406`、`terminal/strata_control/doctor.py:297-318,348-399`）。

省略時はモデル固有検査を行わず、`terminal_cli` と任意の monitor dependency を報告します。通常は `ok: true` で終了しますが、`--live` も指定して profile を省略した場合は live probe 用 profile がないエラーを含み、終了コード5になります（`terminal/strata_control/doctor.py:302-311`）。

## 適用条件と副作用

- 保存 profile 名が未保存、または profile の内容・schema が不正なら失敗します。profile 読み込みは最大1 MiBのファイルを対象とします（`terminal/strata_control/profiles.py:153-173`）。
- 明示 config path の読み込みでは JSON を読み、Strata 管理下の component path を現在のインストール先へ再解決することがあります。診断は engine を起動せず、component の取得や run config の書き換えも行いません（`terminal/strata_control/profiles.py:135-150`、`terminal/strata_control/doctor.py:121-149,297-318`）。
- 保存 profile を読む際、Windows でアクセス拒否が起き、対象がユーザー領域にある場合は、`read_bytes_repairing()` がアクセス権を修復して再読込する経路があります。この場合は profile ファイルのアクセス権が変わる可能性があります（`terminal/strata_control/profiles.py:153-160`、`terminal/strata_control/private_files.py:479-487`）。
- `--live` を併用すると、対象 run config の GPU 選択とホストの NVIDIA GPU を比較します。NVIDIA の場合は `nvidia-smi` を最大5秒で実行します。これは engine の実行互換性や topology の確認ではありません（`terminal/strata_control/doctor.py:269-294,406-409`）。

## 出力とエラー

- 診断結果が問題なしなら終了コード0、必須 component の不足・無効など error severity の issue があれば5です。`--output json` では `{schema_version, ok, report}` の JSON を stdout に出します。通常表示では component 状態と issue を行ごとに stdout へ出します（`terminal/strata_cli/cli.py:1068-1084`、`terminal/strata_control/doctor.py:396-410`）。
- 保存 profile がない場合や profile/config の内容が不正な場合、CLI はエラーを stderr に出し、通常は終了コード2を返します。読み込み I/O エラーは profile reader が終了コード5を設定する場合があります。`--output json` では共通エラー形式 `{schema_version, ok: false, error}` を stdout に出します（`terminal/strata_control/profiles.py:135-150,153-173`、`terminal/strata_cli/cli.py:558-563,2248-2265`）。

## 根拠

- `terminal/strata_cli/cli.py:130-134` — `doctor` parser における `--profile` の値と optional 性。
- `terminal/strata_cli/cli.py:1062-1084` — 値の解決、inspect 呼び出し、出力形式、終了コード。
- `terminal/strata_control/profiles.py:25,48-55,120-150,153-173,400-406` — profile ID・schema・run config の検証と name/path の解決。
- `terminal/strata_control/doctor.py:297-318,348-410` — profile/config を使う component 検査と `ok` 判定。
- `terminal/strata_control/doctor.py:269-294,406-409` — live GPU probe の条件と範囲。
- `terminal/strata_control/private_files.py:479-487` — 保存 profile のアクセス拒否時に行う読み込み修復。
