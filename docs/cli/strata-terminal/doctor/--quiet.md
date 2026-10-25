# `strata doctor --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定は無効 |

## 役割

成功した診断の human-readable な標準出力を抑制します。診断自体を省略するオプションではありません。失敗時は診断報告を標準エラーへ出し、失敗を見落としにくくします。

## 使い方

```sh
strata doctor --profile my-profile --quiet
```

JSON レポートを取得する場合は `--quiet` と `--json`（または `--output json`）を併用できます。

```sh
strata doctor --profile my-profile --quiet --json
```

## 値と既定値

値は不要です。指定すると真になり、省略時は無効です。`doctor` 自身の parser 定義には `--quiet` がありませんが、`strata_cli/cli.py` は `doctor` を含む one-shot parser 群に `--quiet` を追加しています。追加時の既定値は `argparse.SUPPRESS` で、未指定なら属性を作らず、実行時の `getattr(..., False)` で無効として扱います（`strata_cli/cli.py:109-114,508-515,2236-2243`）。短縮別名、値の validation、繰り返し指定による追加動作はありません。

## 実行時の動作

`strata doctor` は profile または run-config の指定を解決して component inventory を作り、engine、tokenizer、参照ファイルなどを検査します。`--quiet` は検査結果を変えず、human 出力だけを標準出力から一時捕捉します。終了コードが 0 なら捕捉内容を出力せず、非 0 なら捕捉内容を標準エラーへ戻します。捕捉量が 64 KiB を超えた場合は古い部分を切り詰め、stderr に省略を示す行を加えます（`strata_cli/cli.py:1023-1045,2196-2214,2236-2248`）。

`--json` は one-shot の JSON 出力に切り替えます。JSON/JSONL 出力は quiet の捕捉対象外なので、`--quiet --json` でもレポートは標準出力に出ます（`strata_cli/cli.py:2232-2237`）。`--output` の有効値は `human` と `json` で、既定は `human` です（`strata_cli/cli.py:113`）。

## 適用条件と副作用

`--quiet` は `doctor` の一回実行に適用され、診断を無効化したり、ファイル検査を飛ばしたりはしません。通常の診断は engine を起動せず、修復・ダウンロードもしません。`--live` を併用した場合は診断側の動作として NVIDIA 環境で `nvidia-smi` を最大 5 秒待って一度呼び出します。これは quiet の副作用ではなく、ライブ検査の副作用です（`strata_control/doctor.py:80-90,146-160,230-235`）。

なお CLI の起動前処理は `main` 内で `private_files.adopt_user_defaults()` を呼びます。これは Windows 以外では何もせず、Windows では現在の process token の既定 owner/DACL の設定を試みます。`--quiet` 固有の動作ではありません（`strata_cli/cli.py:2217-2222`; `strata_control/private_files.py:349-389`）。

`--components` も `doctor` の parser で受理されますが、現行 `_doctor` はこの値を参照せず、指定の有無にかかわらず同じ component inventory を生成します（`strata_cli/cli.py:109-114,1023-1045`）。

## 出力とエラー

- human 出力で診断が成功した場合、終了コードは 0 で、`--quiet` は component 行・issue 行・live probe 行を抑制します（`strata_cli/cli.py:1032-1045,2241-2248`）。
- 必須 component の欠落・不正などで report の `ok` が偽なら終了コードは 5 です。quiet 時も生成済み human report は stderr に出ます（`strata_control/doctor.py:223-235`; `strata_cli/cli.py:1032-1045,2241-2248`）。
- `--live` の失敗条件も report の issue に反映されます。probe が利用できない場合や選択 GPU が見つからない場合など、severity が error の issue があれば `ok` は偽になります（`strata_control/doctor.py:118-143,230-235`）。
- profile 解決・設定読込などで例外になった場合、`_run` はエラーを stderr に出し、例外に設定された終了コード（通常の `ValueError` は 2、`OSError` は 6）を返します。quiet はすでに stderr に書かれたエラーを隠しません（`strata_cli/cli.py:2119-2173`）。
- `--output` に `human` / `json` 以外を指定した場合や、未知の引数を渡した場合は argparse が usage/error を stderr に出し、終了コード 2 で終了します（parser 定義 `strata_cli/cli.py:113`、引数解析 `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:109-114` — `doctor` parser と固有オプション。`--quiet` は `strata_cli/cli.py:508-515` で one-shot parser 群へ追加。
- `strata_cli/cli.py:1023-1045` — profile 解決、inventory 呼び出し、人間向け/JSON 出力、終了コード。
- `strata_cli/cli.py:2196-2248` — quiet の標準出力捕捉・成功時抑制・失敗時 stderr 再出力、JSON 出力との関係。
- `strata_control/doctor.py:80-115,118-143,146-160,218-235` — 読み取り専用 inventory、live probe、report の `ok` 判定。
- `strata_cli/cli.py:2119-2193,2223-2237` — 例外・CLI 引数エラーと JSON/quiet の分岐。
