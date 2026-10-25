# `strata components verify --live`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| オプション | `--live` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False` |

## 役割

通常のコンポーネント確認に加えて、対象プロファイルの GPU 選択番号とホスト上で見える NVIDIA GPU の番号を照合します。これは NVIDIA ホストカード一覧の確認であり、engine の実行、CUDA 互換性、GPU topology の検証ではありません。

## 使い方

保存済みプロファイルを確認する例:

```sh
strata components verify --profile my-profile --live
```

run config JSON を直接指定する例:

```sh
strata components verify --profile ./run-config.json --live --output json
```

`--profile` は必須です。保存名または JSON パスを受け付けます。出力は `--output human|json` で選べ、`--json` は JSON 出力の alias です。one-shot コマンド共通の `--quiet` を指定すると、human 出力は成功時に抑制され、失敗時には stderr に出されます。JSON 出力は `--quiet` では抑制されません。

## 値と既定値

`--live` は `argparse` の `store_true` フラグで、値は不要です。指定しなければ `False` となり、live probe は行われず、レポートの `live_gpu_probe` は `null` です。重複指定による別の動作はありません。

## 実行時の動作

コマンドは `--profile` を `profiles.resolve` に渡し、保存済みプロファイルならその source config と profile ID を、JSON パスなら解決済みパスを `inspect` に渡します。`--live` はその呼び出しの `live` 引数になります。

live probe は run config の `gpu` を選択番号として解析します。値は整数、整数文字列、またはカンマ区切り文字列を受理し、1〜64 個、各 0〜1023、重複なしという規則です。形式が不正なら `invalid_selection` とエラー issue を返します。

現行実装で NVIDIA 問い合わせを行う backend は `cuda`、`cuda_or_cpu_unverified`、および GPU 選択のある `cpu` です。`nvidia-smi` を PATH から探し、GPU index/name/UUID/total memory/driver version を CSV で取得します。実行は5秒で timeout し、終了コード、出力サイズ（64 KiB 以下）、カード数（1〜64）、フィールド形式などを検証します。指定 index が一覧にない場合は `missing_selected` と `GPU_NOT_VISIBLE` エラーになります。一覧取得に失敗すると `unavailable` になります。

`cpu` で GPU 選択が未設定の場合は `not_applicable` です。`cuda` 系で選択が未設定でも一覧取得は行い、成功時は `selection_unverified` となります。その他の backend（HIP、SYCL、Metal など）は番号付けに適格な live probe が未実装として `unverified` と `LIVE_GPU_PROBE_UNAVAILABLE` を返します。

このオプションは `nvidia-smi` を読み取り専用で呼び出します。Strata 自身は engine を起動せず、設定やファイルを書き換えません。GPU 選択値の解析、probe の分岐、カード照合は `strata_control/doctor.py` の該当箇所で実行されます。

## 適用条件と副作用

- `--profile` は必須で、対象 run config の `backend` と `gpu` の値に基づいて probe の適用条件が決まります。
- `nvidia-smi` が見つからない、失敗する、timeout する、または想定外の出力を返すと probe は `unavailable` です。選択 index がある場合、または backend が `cuda` の場合はこの issue の severity は `error`、それ以外は `warning` です。
- CPU backend でも GPU 選択が設定されている場合は NVIDIA 問い合わせを試みます。
- probe が `ok` でも確認範囲はホストのカード一覧と番号だけです。engine 実行可否、CUDA 互換性、device topology は未検証です。

## 出力とエラー

人間向け出力では、通常の component と issue の一覧に加え、probe 結果があれば状態とカードごとの index/name/memory/driver/UUID を表示します。JSON 出力では `{schema_version, ok, report}` として probe 情報を含む report 全体を出力します。

レポートに error severity の issue があれば終了コード `5`、なければ `0` です。したがって、未対応 backend の live probe は現行コードではエラー issue となり、他の確認が通っても終了コード `5` になります。profile/config 読み込みなどで発生する `ValueError` / `OSError` は共通 CLI エラー経路に入り、JSON 指定時は error object を出力します。

## 根拠

- `strata_cli/cli.py:114-119` — `components verify` parser、必須 `--profile`、`--live` の型と説明、出力形式。
- `strata_cli/cli.py:508-515` — one-shot parser 群への `--json` alias と `--quiet` 登録。
- `strata_cli/cli.py:1023-1045` — profile 解決、`inspect` 呼び出し、human/JSON 出力、終了コード。
- `strata_cli/cli.py:2129-2139` — `components verify` が `_doctor` に dispatch される経路。
- `strata_cli/cli.py:2166-2183` — `ValueError` / `OSError` の共通エラー処理。
- `strata_control/profiles.py:135-147,382-388` — run config の読込要件と保存名/JSON path の解決。
- `strata_control/doctor.py:56-77` — `gpu` 選択値の形式・範囲・重複 validation。
- `strata_control/doctor.py:80-115` — `nvidia-smi` の呼び出し、timeout、出力検査。
- `strata_control/doctor.py:118-143` — backend 分岐、選択番号との照合、status と issue。
- `strata_control/doctor.py:146-160,162-164,223-235` — live flag の反映、profile 未指定扱い、probe 呼び出しと最終 `ok` 判定。

調査範囲はこの checkout のソースです。実機の `nvidia-smi` 出力や各 backend のホスト上での動作は実行して確認していません。
