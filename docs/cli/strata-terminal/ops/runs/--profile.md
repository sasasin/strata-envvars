# `--profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile 名（値を必須とする） |

## 役割

`--profile` は、`strata ops runs` が一覧表示するローカル operation journal の profile を指定する。ここでの `runs` は記録の読み取りだけを行い、operation を実行しない。recipe 実行に加えて、一部の直接 runtime/calibration 実行も同じ journal に記録される（`terminal/strata_cli/cli.py:1474-1478`、`docs/TERMINAL.md:133`）。

## 使い方

```sh
strata ops runs --profile four-gpu
strata ops runs --profile four-gpu --limit 50 --output json
```

`--profile` は必須で、`--output` の既定値は `human`。JSON 表示は `--output json` または共通 one-shot alias `--json` で選べる（`terminal/strata_cli/cli.py:286-297,539-545`）。

## 値と既定値

- 値は `--profile NAME` の形式で必須。省略すると argparse が usage error として拒否する。profile 名は小文字英字で始まり、小文字英数字・`_`・`-` を使用でき、長さは最大 64 文字（`terminal/strata_cli/cli.py:294`、`terminal/strata_control/profiles.py:25,48-55`）。
- 有効な既定 profile はない。`recipes._directory()` が `profiles.load()` を呼ぶため、その名前の profile ファイルが必要（`terminal/strata_control/recipes.py:38-41`）。未保存の名前はエラーになる。launch preset 名も独立した保存済み profile とは扱われず、別途 `strata profile create` を案内する（`terminal/strata_control/profiles.py:153-168`）。
- profile の探索先は `STRATA_PROFILE_DIR` があればその値、Windows では `APPDATA` 配下（未設定時は home 配下）、それ以外では `XDG_CONFIG_HOME` または `~/.config` 配下（`terminal/strata_control/profiles.py:38-45`）。
- 同じ `--profile` の複数回指定時の意味は parser で定義されていないため、挙動を保証できない。

## 実行時の動作

parser は値を文字列として受け取り、`_ops()` はこれを `journal.list_runs(profile, limit=...)` に渡す。profile は `~/.config/strata/profiles`（または設定された profile directory）の `<NAME>.json` から読み込まれ、その profile の recipe 配下にある `.runs` が一覧対象となる（`terminal/strata_cli/cli.py:294,1474-1478`、`terminal/strata_control/profiles.py:38-55,153-168`、`terminal/strata_control/recipes.py:38-64`、`terminal/strata_control/journal.py:47-63,259-278`）。

記録はファイル更新時刻の降順で並び、`--limit` 件まで読み込まれる。各行には operation ID、recipe/direct の由来、kind、state、開始・終了時刻が含まれ、実行中の記録は `completion_unverified` として示される。壊れている、またはサポートされない個別記録は一覧全体を止めず、その行に `error` として返る。journal ディレクトリが存在しない場合は空一覧になる（`terminal/strata_control/journal.py:259-278`）。

## 適用条件と副作用

このコマンドは記録を参照する読み取り操作で、operation の開始・停止や journal 記録の作成は行わない。profile の読込時に `private_files.read_bytes_repairing()` が使われるため、昇格実行でロックされた profile は必要に応じてその場で修復される（`terminal/strata_control/profiles.py:153-162`）。journal directory が symlink である場合や POSIX で owner-only の権限要件を満たさない場合は拒否される（`terminal/strata_control/journal.py:47-57`）。

## 出力とエラー

- human 出力では、各記録の operation ID と state を表示する。該当記録がなければ `No operation runs recorded` と表示（`terminal/strata_cli/cli.py:1474-1478`）。
- JSON 出力は `schema_version`、`ok`、指定 profile 名、`runs` 配列を stdout に出す（`terminal/strata_cli/cli.py:566-573,1474-1478`）。
- 一覧上限 `--limit` は既定 20、整数 1〜100。範囲外は `operation list limit must be 1..100` で失敗する（`terminal/strata_cli/cli.py:296-297`、`terminal/strata_control/journal.py:259-262`）。
- ProfileError は human 時 stderr、JSON 時 stdout にエラーを出し、例外に exit code があればそれを使用する。通常の未知の profile は code 5、option の不足・不正な profile 名は parser/profile validation のエラーとなる（`terminal/strata_cli/cli.py:558-563,2248-2255`、`terminal/strata_control/profiles.py:30-35,48-55,163-172`）。

## 根拠

- `terminal/strata_cli/cli.py:283-297` — `ops runs` parser と必須 `--profile` 定義、`--limit` の既定値。
- `terminal/strata_cli/cli.py:1461-1478` — profile を journal 一覧処理へ渡し、human/JSON を出力。
- `terminal/strata_control/profiles.py:25,38-55,153-172` — profile 名規則、保存先、profile 読み込みと未保存時のエラー。
- `terminal/strata_control/recipes.py:38-64` — profile を検証して `.ops/<profile>` の recipe directory を特定。
- `terminal/strata_control/journal.py:47-57,259-278` — journal directory、limit validation、mtime 降順の一覧と破損記録の扱い。
- `docs/TERMINAL.md:125,133` — 利用例と `ops runs` が journal を読み取る説明。ソース挙動の根拠には上記実装を使用。
