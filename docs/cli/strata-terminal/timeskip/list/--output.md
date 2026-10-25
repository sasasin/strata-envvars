# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip list` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

記録済み Time-skip run の一覧を人向けの行表示か、機械処理向け JSON で標準出力へ出す。出力ファイルを指定するオプションではない。

## 使い方

```sh
strata timeskip list --output json
```

## 値と既定値

- `human`: 既定値。各 run について ID の先頭 12 文字、state、decision outcome、prompt の先頭 48 文字を1行に表示する。run がない場合は `no Time-skip runs recorded` と表示する。
- `json`: `{"schema_version":1,"ok":true,"runs":[...]}` の JSON を1行で標準出力へ出す。`runs` の各要素には `id`、`state`、`workspace`、`prompt`、`started_at`、`finished_at`、`decision` が含まれる。空の場合も `runs` は空配列になる。
- 省略時は `human`。parser の `choices` にない値は argparse が拒否し、usage とエラーを標準エラーへ出して終了コード 2 で終了する。
- 同じオプションを複数回指定した場合は、標準の argparse `store` action により最後の値が使われる。

## 実行時の動作

`--output` は `strata timeskip list` の parser に `choices=("human", "json")`、`default="human"` として登録される（`strata_cli/cli.py:376-378`）。`strata timeskip list` が選ばれると `TimeSkipStore.list()` で一覧を読み、`json` なら `_success` を machine mode で呼び、`human` なら各行を整形して出す（`strata_cli/cli.py:1487-1498`、`strata_cli/cli.py:535-542`）。

一覧の対象は state directory 直下のディレクトリにある `run.json` で、項目はディレクトリ順に走査される。JSON 読み込み時に `OSError` または `JSONDecodeError` が起きた記録は一覧から読み飛ばされる（`strata_control/time_skip.py:702-713`）。

表示形式以外の一覧対象や保存状態は変えない。state directory の選択には同じコマンドの `--state-dir` が優先され、次に `STRATA_TIMESKIP_DIR`、最後に `state_base()/time-skip` が使われる。POSIX の `state_base()` は `$XDG_STATE_HOME/strata`（未設定なら `~/.local/state/strata`）、Windows は `%LOCALAPPDATA%\Strata`（未設定ならユーザー領域の `AppData\Local\Strata`）を返す（`strata_cli/cli.py:1476-1485`、`strata_control/paths.py:13-21`）。

## 適用条件と副作用

`human` と `json` は一覧の標準出力形式にのみ作用する。いずれの形式でも `TimeSkipStore` の初期化時に state directory を `mkdir(parents=True, exist_ok=True)` するため、ディレクトリが未作成なら作成される（`strata_cli/cli.py:1485`、`strata_control/time_skip.py:698-700`）。既存 run の変更や削除は一覧処理では行わない。

## 出力とエラー

- 正常時の終了コードは 0。human 形式は一覧を標準出力へ表示し、JSON 形式は成功 envelope と `runs` を標準出力へ出す（`strata_cli/cli.py:1487-1498`）。
- 不正な出力形式は parser の選択肢検査で拒否される。parser は `parse_known_args` を使い、残った引数を `ap.error(...)` に渡す（`strata_cli/cli.py:2223-2231`）。
- state directory の作成・走査などで `OSError` が発生した場合、共通処理が終了コード 6 として扱う。human 形式では `strata: ...` を標準エラーへ出し、`--output json` では `ok:false` の JSON error を標準出力へ出す（`strata_cli/cli.py:527-532`、`strata_cli/cli.py:2176-2183`）。
- 個別の `run.json` が読み取り不能または不正 JSON の場合は、その記録を黙って読み飛ばし、一覧全体は続行する（`strata_control/time_skip.py:707-710`）。

## 根拠

- `strata_cli/cli.py:376-378` — `timeskip list` parser と `--output` の値・既定値。
- `strata_cli/cli.py:1476-1498` — state directory の選択、一覧呼び出し、human/JSON の分岐と表示。
- `strata_control/time_skip.py:695-713` — state directory 初期化、`run.json` の走査・読み込み・返却フィールド。
- `strata_control/paths.py:13-21` — platform ごとの既定 state base。
- `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2176-2183`, `strata_cli/cli.py:2223-2231` — 出力 helper、OS エラー、引数エラーの処理。

調査範囲は上記 commit の checkout 内にある Terminal CLI と state store のソースコード。CLI help や Release 配布物との別途照合は行っていない。
