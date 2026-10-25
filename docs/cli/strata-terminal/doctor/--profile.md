# `strata doctor --profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み profile 名、または run config JSON のパス。必須ではありません。 |

## 役割

モデル固有のコンポーネント診断に使う run config を選びます。保存済み profile 名を指定すると、その profile が参照する `source_config` を診断します。JSON パスを指定すると、その run config 自体を診断します。どちらも推論エンジンの起動は行いません。

## 使い方

```sh
# 保存済み profile の source config を診断
strata doctor --profile four-gpu

# run config JSON を直接指定
strata doctor --profile /absolute/path/to/strata-model.json --output json
```

## 値と既定値

- parser は `--profile` に値を取る引数を定義しますが、`required=True` ではありません。省略時はモデル固有診断をせず、Terminal CLI と任意 monitor 依存だけを確認します（`strata_cli/cli.py:109-113`、`strata_control/doctor.py:146-160`）。
- 値が `.json` 拡張子（大文字小文字を問わない）、絶対パス、または `/`・`\` を含む場合はパスとして扱い、それ以外は保存済み profile 名として解決します。パスは `expanduser()` と `resolve()` を通ります。パスらしい値が不正でも profile 名へのフォールバックはありません（`strata_control/profiles.py:382-388`）。
- 保存名は `a-z` の小文字で始まり、以降は小文字英字・数字・`_`・`-` のみ、最大64文字です（`strata_control/profiles.py:25,48-55`）。
- 指定しなかった場合の既定値は `None` です。値の存在確認や形式検査は parser ではなく、実行時の profile/config 読み込みで行います。

## 実行時の動作

- 保存済み profile 名の場合、profile を読み込み、profile の `source_config` を診断対象にします。`_doctor` が診断関数へ渡す profile 固有情報は `id` のみで、profile の `overrides` は診断対象 config に適用されません（`strata_cli/cli.py:1023-1028`、`strata_control/profiles.py:382-388`）。
- JSON パスの場合、指定ファイルを run config として読みます。run config は `args` が文字列の配列であり、`exe` と `tokenizer` が空でない文字列であることが必要です（`strata_control/profiles.py:135-147`）。
- run config を選ぶと engine 実行ファイル、tokenizer ファイル、`args` 内の特定のパス引数（`--pack`、`--native`、`--ple-gguf`、`--expert-profile`、`--mtp`、`--control-vector-scaled`）、vision ファイル、任意 monitor 依存などを検査します。相対パスは config の `cwd` があればそこを基準にし、なければ config ファイルの親を基準にします（`strata_control/doctor.py:19-53,146-235`）。
- GPU 選択・driver との照合を試みるには `--live` が必要です。`--profile` を省略して `--live` を使うと profile 未選択の error issue になり、レポートは失敗扱いになります（`strata_cli/cli.py:112,1027-1028`、`strata_control/doctor.py:151-160`）。
- `--output json` または alias の `--json` はレポートを JSON で stdout に出します。human 出力では component の状態と issue を表示し、`--live` の probe 結果も表示します（`strata_cli/cli.py:508-515,1024-1045`）。
- `--components` は parser 上受理されますが、`_doctor` はこの値を参照せず、診断関数も常に component 一覧を作ります。そのためこの revision では `--components` の有無で診断内容は変わりません（`strata_cli/cli.py:111,1023-1028`、`strata_control/doctor.py:146-160,162-235`）。索引の項目名だけから任意指定の効果を想定しないでください。

## 適用条件と副作用

- `--profile` を省略した場合、profile やモデル用ファイルの検査は行われません。profile/run config を指定した場合も診断はファイル・設定の読み取りを中心とし、engine を起動しません（`strata_control/doctor.py:146-235`）。
- 保存済み profile の読み込みで通常の読み取りに `PermissionError` が起き、Strata が所有するファイルとして修復可能と判断した場合、読み直しの前にアクセス権を修復する経路があります。従って profile 名での呼び出しには、条件付きで profile ファイルの ACL/permission を変更する副作用があります（`strata_control/profiles.py:150-166`、`strata_control/private_files.py:476-484`）。
- `--live` は `nvidia-smi` を最大5秒の timeout 付きで実行し、カード一覧・driver 文字列を取得します。NVIDIA 以外の backend はこのコマンドでは未検証として報告されます。GPU 実行互換性や topology、モデル hash の検証までは行いません（`strata_control/doctor.py:80-115,118-143`）。
- report の `ok` は必須 component の missing/invalid や error severity の issue がない場合に true です。`--profile` なしの通常診断は `ok: true` になりますが、`--live` を加えると profile が必要なため false になります（`strata_control/doctor.py:151-160,223-235`）。

## 出力とエラー

- 成功時は human または JSON のレポートを stdout に出し、`report["ok"]` が true なら終了コード `0`、false なら `5` です（`strata_cli/cli.py:1029-1045`）。
- 保存 profile が存在しない・壊れている、run config が読めない・形式不正などの例外は共通エラー処理へ渡ります。human 出力では `strata: ...` を stderr に表示し、JSON 出力では `{schema_version, ok: false, error}` を stdout に出します。終了コードは例外に設定された値を使い、個別指定がなければ `2`、ファイル読み込み失敗や profile 不在など明示的に `5` とされたケースは `5` です（`strata_control/profiles.py:135-147,150-166`、`strata_cli/cli.py:527-532,2166-2188`）。

## 根拠

- `strata_cli/cli.py:109-113` — `doctor` parser と `--profile`、関連 option。
- `strata_cli/cli.py:1023-1045` — profile 解決、report 出力、終了コード。
- `strata_cli/cli.py:508-515,2166-2188` — `--json` alias と例外の出力・終了コード。
- `strata_control/profiles.py:25,48-55,120-147,150-166,382-388` — profile 名と形式、run config 読み込み、profile/path の判定。
- `strata_control/private_files.py:476-484` — PermissionError 時のアクセス修復と再読み込み。
- `strata_control/doctor.py:19-53,80-143,146-235` — 検査対象、live probe、report 内容と `ok` 判定。
