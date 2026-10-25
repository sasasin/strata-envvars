# `strata components verify --profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 必須の文字列。保存済み profile 名、または run config JSON のパス |

## 役割

検査するインストール済み profile を選びます。実際には指定値を保存済み profile 名または run config パスとして解決し、その run config が参照する engine、tokenizer、model 関連ファイルなどを読み取り検査します。engine の起動やファイルのダウンロードは行いません。

## 使い方

```sh
strata components verify --profile four-gpu
strata components verify --profile ./configs/run.json --output json
```

`--profile` は parser で必須です。パスは `.json` 拡張子、絶対パス、または `/`・`\\` を含む値として扱われます。それ以外の値は保存済み profile 名として解決されます。

## 値と既定値

- 値は必須です。省略すると `argparse` が usage とエラーを表示して終了します（終了コード 2）。空文字列を含め、値の文字列自体に parser 上の `choices` や形式検査はありません。
- `strata_control.profiles.resolve()` は値を `expanduser()` したうえで、`.json` 拡張子（大文字小文字を無視）、絶対パス、または区切り文字を含む値ならファイルパスとして解決します。それ以外は profile 名として `load()` します。パスらしい値が見つからなくても profile 名にはフォールバックしません。
- 保存 profile 名の場合、profile の `source_config` が検査対象になります。profile の `overrides` はこの処理では適用されず、返される report では saved profile の ID が示されます。
- このオプション自体に既定値はありません。`--output` は別オプションで、既定値は `human` です。

## 実行時の動作

この parser は `components verify` 専用の `--profile` を定義しています。`_run()` は `components` コマンドを `_doctor()` に渡し、`_doctor()` が値を `profiles.resolve()` で解決して `inspect_components()` に渡します。したがって、同じ名前の `strata doctor --profile` とは別 parser scope ですが、profile/path の解決と検査処理は共有されます。

run config は JSON として読み込まれ、`args` が文字列配列であること、`exe` と `tokenizer` が空でない文字列であることを検証します。その後、engine 実行ファイル、tokenizer の `vocab.json`・`merges.txt`・`token_type.json`、config の引数にある認識対象のファイル・ディレクトリ指定、vision 設定を検査します。相対パスは config の `cwd`（文字列の場合）、なければ config ファイルの親ディレクトリを基準にします。

通常の検査はファイル存在・種別・サイズ（通常ファイルは空でないこと）等を調べ、required な欠落・不正を issue にします。これはファイルのハッシュや完全性を検証するものではありません。`--profile` と `--live` を併用した場合は run config の backend と GPU 選択値も live probe に渡します。profile の保存値は読み取りだけ行い、書き換えません。

## 適用条件と副作用

- 通常の検査は外部プロセスを起動しません。`doctor.py` は report 内に driver probe の候補パスを記載する目的で `shutil.which()` を使いますが、外部ツールを実行するのは `--live` の場合です。
- `--live` は現在 NVIDIA の `nvidia-smi` を最大5秒で一度呼び出し、見えるカードの index 等を確認して profile の選択 index と照合します。これは host 上のカード一覧確認であり、engine の実行可否、CUDA 互換性、GPU topology を証明しません。
- CPU backend で GPU 選択がなければ live probe は適用外です。CUDA 系以外の backend（HIP、SYCL 等）は qualified probe が未実装として error になります。NVIDIA probe が使えない場合、backend が `cuda` または GPU index を明示していれば error、どちらも不明なら warning になります。
- Linux の HIP/SYCL では通常検査時にも `/dev/dri/renderD*`（HIP は存在すれば `/dev/kfd` も）のアクセス権を確認し、アクセス不能なら warning を追加します。
- `--live` がない場合は GPU に関する外部 probe を行いません。いずれの経路も engine を起動せず、component を修復・取得しません。なお、保存 profile の読み込みでアクセス拒否が起きた場合、ユーザー自身のデータ領域内なら Windows の private-file helper がアクセス権を一度修復して再読込する経路があります。

## 出力とエラー

- human 出力は component ごとの status/name/detail と issue を標準出力に表示します。live probe の結果がある場合は status とカード情報も表示します。
- `--output json` は `schema_version`、report の `ok`、詳細な `report` を含む JSON を標準出力に出します。`report.ok` が真なら終了コード 0、required component の欠落・不正や live probe error などで偽なら 5 です。warning だけでは `ok` を偽にしません。
- profile が未保存、profile JSON が不正、run config が読めない、または必須キーの形式が不正な場合は失敗します。`ProfileError` は `_run()` の `ValueError` 経路で処理され、human 時は `strata: ...` を標準エラーへ、JSON 出力時は `ok:false` と error code/message を標準出力へ出します。既定の ProfileError code は 2 ですが、profile/config の読込失敗など一部は code 5 です。
- profile 名で指定した profile は読み込み時に通常ファイルであることと 1 MiB 以下であることを確認します。指定がファイルパスの場合は、最終的な run config の読込時に失敗が判明します。

## 根拠

- `strata_cli/cli.py:114-119` — `components verify` の parser と `--profile` の必須指定、`--live`、`--output` の scope。
- `strata_cli/cli.py:1023-1045,2138-2139` — profile 解決、検査関数への引き渡し、report の human/JSON 出力と終了コード。
- `strata_control/profiles.py:30-35,135-147,150-166,382-388` — ProfileError、run config の形式検査、saved profile の読み込み制約、名前とパスの振り分け。
- `strata_control/doctor.py:44-53,80-115,118-143,146-235` — component 検査、NVIDIA live probe の上限・判定、required issue と report の `ok` 判定。
- `strata_control/doctor.py:238-252` — Linux HIP/SYCL device node のアクセス警告。
- `strata_control/private_files.py:442-459,476-484` — 保存 profile の read が PermissionError になった場合の、ユーザー領域に限定した Windows access repair と再読込。

## 調査範囲

対象 checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、調査時の `git status --short --branch` は `## main...origin/main` でした。ソースを読み取って確認し、CLI help、Release artifact、別 OS/backend 上の実機動作は調査していません。
