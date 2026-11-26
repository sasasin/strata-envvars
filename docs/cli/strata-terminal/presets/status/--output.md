# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets status` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

対象構成に対応する保存済みチューニング preset の状態を表示する形式を選ぶ。status 処理は preset や run config を更新せず、エンジンも起動しない。ただし、対象を保存 profile 名で指定したとき、profile の読込でアクセス権エラーが起きると、profile 読込 helper が権限を修復して再読込する経路がある。

## 使い方

```sh
# 人間向け表示（既定値）
strata presets status my-profile

# スクリプトなどから扱う JSON 表示
strata presets status /path/to/run-config.json --output json
```

`target` は保存 profile、run config JSON のパス、または一意に特定できるインストール済みモデル名を指定できる。CLI の parser は `status` に `target` と `--output` を登録し、`--output` の既定値を `human` としている（`terminal/strata_cli/tune_commands.py:59-66`）。

## 値と既定値

- `human`: 省略時の値。結果を人間向けの短い文として標準出力へ出す。
- `json`: `schema_version: 1`、`ok: true` と status データを含む JSON オブジェクトを標準出力へ出す。
- `choices=("human", "json")` による parser 検証があり、その他の値は argparse が拒否する。短縮別名や重複指定時の特別な処理は定義されていない（`terminal/strata_cli/tune_commands.py:59-66,101-106`）。

## 実行時の動作

`--output` は結果のシリアライズ形式だけを切り替え、status の計算は共通である。対象構成から model・context・KV・vision・goal などの選択値を読み取り、現在のハードウェア、engine、モデルファイルの identity とともに preset slot を特定する。該当 slot の active preset、staleness と理由、同 slot の preset 一覧、undo 可能性、前回 active だった preset を集めて出力する（`terminal/strata_cli/tune_commands.py:595-612`; 選択値と slot の構成は `terminal/strata_control/presets.py:89-117,128-132`）。

`human` は active preset があれば名前と状態を、なければ「該当選択肢の保存 tuning はない」旨を出力する。`json` は同じ結果を機械可読な object にして出力する（`terminal/strata_cli/tune_commands.py:101-106,606-612`）。どちらも status の取得範囲やエラー条件は変えない。

## 適用条件と副作用

status は構成ファイルと preset store を読み、identity 判定のためにローカルの CPU・メモリ・GPU 情報を調べる。NVIDIA では `nvidia-smi` を呼び出す場合があり、macOS ではメモリ取得のため `sysctl` と `vm_stat` を呼び出す。エンジン実行や測定、preset の書き換えはこの経路にない（`terminal/strata_control/tune_machine.py:47-65,70-117,264-309`; 読み取り処理の呼び出しは `terminal/strata_control/presets.py:162-182`）。probe が使えない場合、同モジュールは例外を抑えて情報を欠落値として返す。profile 名で対象を解決すると `profiles.load` を通り、ファイルアクセス権のエラー時は `read_bytes_repairing` が権限修復を試みてから再読込するため、この条件では profile の権限に副作用があり得る（`terminal/strata_control/profiles.py:153-173`; `terminal/strata_control/private_files.py:479-487`）。

## 出力とエラー

- 成功時は JSON／人間向けのいずれも標準出力へ出し、終了コード `0` を返す（`terminal/strata_cli/tune_commands.py:101-106`）。
- 対象 profile や run config を解決・読込できない場合など、`ValueError` 系または `OSError` は共通 handler で処理される。JSON 指定時は `schema_version: 1`、`ok: false`、`error.code` と `error.message` の JSON を標準出力へ出し、人間向けでは `strata: ...` を標準エラーへ出す。ProfileError が持つ終了コードを優先し、それ以外の例外は既定で `2` となる（`terminal/strata_cli/tune_commands.py:109-114,527-530`; ProfileError の型と終了コードは `terminal/strata_control/profiles.py:30-35`）。
- 不正な `--output` 値はコマンド処理に入る前に argparse が拒否する。parser 定義で許可値を限定している（`terminal/strata_cli/tune_commands.py:59-60`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-66` — presets の parser 階層、`status` の引数、`--output` の値と既定値。
- `terminal/strata_cli/tune_commands.py:101-114,472-485,527-530` — 成功・失敗出力の形式、status への振り分け、例外処理。
- `terminal/strata_cli/tune_commands.py:595-612` — status の計算内容と表示形式。
- `terminal/strata_control/presets.py:89-117,128-132,162-182` — 対象選択値、slot、現在 identity の構築。
- `terminal/strata_control/tune_machine.py:47-65,70-117,264-309` — ローカル環境 probe と engine／model identity の読み取り。
- `terminal/strata_control/profiles.py:153-173`; `terminal/strata_control/private_files.py:479-487` — profile 名指定時のアクセス権修復を伴う再読込。
- `docs/cli/README.md:773-776` — 作成対象の索引リンク、コマンド階層、option scope。
