# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 取らないフラグ。指定時に有効 |

## 役割

成功時の人間向け情報出力を抑え、スクリプトなどで検証結果の通常表示が不要な場合に使います。検証自体を省略したり、チェック範囲を狭めたりするフラグではありません。

## 使い方

```sh
strata components verify --profile four-gpu --quiet
```

`--profile` は必須です。`four-gpu` は保存済みプロファイル名の例で、実際の環境に存在する名前を指定します（`--profile` は `strata_cli/cli.py:116-119`、プロファイル名または JSON パスの解決は `strata_cli/cli.py:1023-1028`、`strata_control/profiles.py:382-388`）。

## 値と既定値

`--quiet` は値を取りません。`action="store_true"` のため、指定時は真、未指定時は `False` 相当です。verify parser を含む one-shot parser 群に共通追加され、属性の既定値は `argparse.SUPPRESS` なので、未指定時は Namespace に属性を作らず、実行時の `getattr(a, "quiet", False)` が偽として扱います（`strata_cli/cli.py:508-515`、`strata_cli/cli.py:2236-2247`）。繰り返し指定しても真のままです。値を付ける構文（例: `--quiet=true`）は受理されません。

## 実行時の動作

`strata components verify` は `_doctor` に渡され、プロファイルを解決してコンポーネントを検査します（`strata_cli/cli.py:2119-2139`、`strata_cli/cli.py:1023-1028`）。`--quiet` が有効で、`--output` が `human` の場合、CLI 共通層が stdout を最大 64 KiB のバッファに一時捕捉します。検査関数や表示処理は通常どおり実行され、終了コードが 0 なら捕捉した人間向け出力を表示しません（`strata_cli/cli.py:2196-2217`、`strata_cli/cli.py:2236-2247`）。

`--output json` またはその alias `--json` を指定すると quiet 捕捉を通らず、JSON 結果を通常どおり stdout に出します。quiet は標準出力の表示制御であり、検査の判定や機械可読出力を変えません（`strata_cli/cli.py:119`、`strata_cli/cli.py:513-515`、`strata_cli/cli.py:2232-2247`、`strata_cli/cli.py:1023-1031`）。

## 適用条件と副作用

人間向け出力の表示以外に `--quiet` 固有の副作用はありません。ファイル検査やレポート生成は通常どおり行われます。また `--live` を併用すれば quiet の有無にかかわらず live GPU probe が実行されます。CUDA 系では `nvidia-smi` を最大 5 秒で問い合わせ、他 backend では未対応 probe として報告する経路があります。したがって `--quiet` は外部コマンド実行や読み取りを無効化しません（`strata_cli/cli.py:118`、`strata_control/doctor.py:84-95`、`strata_control/doctor.py:118-143`、`strata_control/doctor.py:230-235`）。

## 出力とエラー

- `--output human` で検査が成功（終了コード 0）すると、通常なら stdout に出るコンポーネント一覧や issue 表示を抑えます（`strata_cli/cli.py:1029-1045`、`strata_cli/cli.py:2241-2247`）。
- 検査が失敗して非 0 で戻り、stdout に捕捉済みの人間向け出力があれば、それを stderr に書き出して診断を残します。捕捉量が 64 KiB を超えた場合は、末尾の 64 KiB と `strata: earlier human output omitted in quiet mode` を stderr に出します。終了コードは検査側の値を維持します。`components verify` の report が不成功なら `_doctor` は 5 を返します（`strata_cli/cli.py:2241-2248`、`strata_cli/cli.py:1032-1045`）。
- `_error` などが直接 stderr に書くエラーは quiet の stdout 捕捉対象外です（`strata_cli/cli.py:527-532`）。引数不足や未知オプションは quiet 処理より前に parser が処理し、通常の argparse usage/error を stderr に出して終了します（`strata_cli/cli.py:2223-2231`）。
- `--output json` / `--json` では quiet が JSON を抑制せず、失敗時も JSON のエラー出力が保持されます（`strata_cli/cli.py:529-530`、`strata_cli/cli.py:2232-2237`）。

## 根拠

- parser の verify 定義: `strata_cli/cli.py:114-119`。
- 共通 `--quiet` 追加と既定値: `strata_cli/cli.py:508-515`。
- verify の dispatch と検査・人間/JSON 出力・終了コード: `strata_cli/cli.py:1023-1045`、`strata_cli/cli.py:2119-2139`。
- quiet の捕捉・失敗時 stderr 再表示・JSON の扱い: `strata_cli/cli.py:2196-2217`、`strata_cli/cli.py:2223-2248`。
- 検査関数の `--live` probe 適用条件と結果判定: `strata_control/doctor.py:118-143`、`strata_control/doctor.py:146-160`、`strata_control/doctor.py:230-235`。
- 調査時の対象 checkout は `git rev-parse HEAD` で上記 commit、`git status --short --branch` は `## main...origin/main`（追加の変更表示なし）でした。調査の補助として `--help` は実行せず、parser と処理経路をソースで確認しました。
