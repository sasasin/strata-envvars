# `--live`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--live` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は `false` |

## 役割

インストール済みコンポーネントの静的な確認に加えて、設定した GPU index が実ホストから見えるかを調べます。設定に対してホスト GPU を照会するため、`--profile` で保存済み profile または run config JSON を指定してください。`--live` は GPU を使った推論やドライバー互換性の検証は行いません。

## 使い方

```sh
strata doctor --profile /path/to/run-config.json --live
strata doctor --profile my-profile --live --output json
```

`--profile` は保存 profile 名または run config JSON のパスです。`.json`、絶対パス、スラッシュを含む値はパスとして解決され、それ以外は保存 profile 名として解決されます（`strata_control/profiles.py:382-388`）。

## 値と既定値

- `--live` は `argparse` の `store_true` で値を取らず、省略時は `false` です。繰り返し指定しても有効になるだけです（`strata_cli/cli.py:109-113`）。
- `--profile` を省略すると、ライブ照会は実施されません。report に `PROFILE_NOT_SELECTED_FOR_LIVE_PROBE`（severity `error`）が加わり、`ok` は `false` になります（`strata_control/doctor.py:151-160`）。
- profile の `gpu` 設定は、整数、整数のリスト、またはカンマ区切りの文字列として解釈されます。index は 0〜1023、要素数は 1〜64、重複不可です。空リスト、範囲外、非数値、重複は `invalid_selection` と `GPU_SELECTION_INVALID` を返すエラーになります（`strata_control/doctor.py:56-77`, `118-123`）。

## 実行時の動作

CLI は `--live` の値を `inspect_components(..., live=...)` に渡します（`strata_cli/cli.py:1023-1028`）。通常のコンポーネント確認を行った後、`--live` が有効なら `_live_probe` を呼び、結果と issue を report に追加します（`strata_control/doctor.py:218-235`）。

ライブ照会の条件と結果は次のとおりです。

- backend が `cpu` で GPU 選択が未指定なら `not_applicable` となり、ホスト照会をしません（`strata_control/doctor.py:124-125`）。
- `cuda`、`cuda_or_cpu_unverified`、`cpu`（GPU 選択あり）は NVIDIA の `nvidia-smi` を探し、`index,name,uuid,memory.total,driver_version` を CSV で取得します。呼び出しは5秒 timeout、出力上限は65,536文字、カード上限は64です（`strata_control/doctor.py:80-115`, `126-135`）。
- 照会できた場合、選択 index が一覧に存在するかを比較します。未検出 index は `GPU_NOT_VISIBLE`（severity `error`）、一致すれば `ok`、選択がなければ `selection_unverified` です（`strata_control/doctor.py:136-143`）。
- 上記以外の backend は device 番号を検証できず、`unverified` と `LIVE_GPU_PROBE_UNAVAILABLE`（severity `error`）になります。NVIDIA 照会が使えない場合は `unavailable` となり、選択 index がある場合または backend が `cuda` の場合は error、それ以外は warning です（`strata_control/doctor.py:126-135`）。
- GPU 選択が未指定の場合、カード一覧を取得できても「選択 index の照合」は行われません。レポートの `scope` はホストカード一覧のみで、engine 実行、CUDA 互換性、topology は未検証と明記されます（`strata_control/doctor.py:136-143`）。

この追加処理は `nvidia-smi` を読み取り目的で子プロセス実行します。`strata_control/doctor.py` のライブ照会経路には設定ファイルやコンポーネントを書き換える処理はありません。照会失敗は report の issue として扱われ、例外としては扱われません（`strata_control/doctor.py:80-143`, `230-235`）。

## 適用条件と副作用

- `--live` は `strata doctor` のスコープです。別コマンド `strata components verify` にも同名フラグがありますが、そちらは別 parser として登録されています（`strata_cli/cli.py:109-119`）。
- NVIDIA 以外の backend の device index はこの probe で検証されません。`cuda_or_cpu_unverified` は NVIDIA 照会を試みますが、選択 index が未指定なら得られるのはホストカード一覧であり、profile の実 GPU 選択を確認したことにはなりません（`strata_control/doctor.py:126-143`）。
- `nvidia-smi` が PATH にない、失敗する、timeout する、または想定外の出力を返す場合、probe は `unavailable` になります。カード数・index・メモリ・文字列フィールドの形式にも上限と検査があります（`strata_control/doctor.py:80-115`）。
- `--live` はドライバーや CUDA の互換性、GPU topology、engine 起動可否を保証しません（`strata_control/doctor.py:141-143`）。

## 出力とエラー

- 既定の human 出力では通常のコンポーネント行と issue を表示し、probe があれば `Live GPU probe: <status>` とカードの index、名前、メモリ、driver version、UUID を出力します（`strata_cli/cli.py:1029-1045`）。
- `--output json` では `schema_version: 1`、report の `ok`、report 全体を含む JSON を stdout に出します（`strata_cli/cli.py:1029-1031`）。
- report に error severity の issue がある場合は終了コード `5`、それ以外は `0` です（`strata_control/doctor.py:233-235`, `strata_cli/cli.py:1045`）。したがって probe が warning のみで unavailable の場合は、probe 自体が unavailable でも終了コードは `0` になり得ます。
- 保存 profile が見つからない場合や run config を読めない場合は、`profiles.resolve` / `read_run_config` のエラーが CLI の共通エラー経路で返されます。JSON 出力時は JSON error、human 出力時は stderr の `strata: ...` となり、profile 未発見や run config 読み込み失敗の既定 code は `5` です（`strata_control/profiles.py:135-147`, `150-166`, `strata_cli/cli.py:2166-2183`, `527-532`）。

## 根拠

- parser 定義とフラグの scope: `strata_cli/cli.py:109-119`
- `doctor` の dispatch と出力・終了コード: `strata_cli/cli.py:1023-1045`, `2138-2139`
- profile 名と JSON path の解決: `strata_control/profiles.py:382-388`
- GPU index の形式検証、NVIDIA 照会、backend 別条件、report への統合: `strata_control/doctor.py:56-77`, `80-143`, `146-160`, `218-235`
- run config 読み込みと共通エラー出力: `strata_control/profiles.py:135-147`, `strata_cli/cli.py:527-532`, `2166-2183`

調査範囲は上記 commit の checkout 内ソースです。CLI help や実ホストでの `nvidia-smi` 動作は実行しておらず、各 backend/OS の実機挙動は確認していません。
