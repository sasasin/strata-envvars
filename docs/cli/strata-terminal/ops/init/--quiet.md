# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると `True`。未指定時は `False` として扱われる |

## 役割

成功時に人向けの案内を標準出力へ表示しない。初期化で作成する recipe の種類やファイル操作は変えない。

## 使い方

保存済み profile `local` に初期 recipe を用意し、成功メッセージを抑制する。

```sh
strata ops init --profile local --quiet
```

## 値と既定値

`--quiet` は `store_true` のフラグで、引数値は不要。`ops init` を含む one-shot parser 群に共通追加され、既定値は `argparse.SUPPRESS` である。未指定時も実行側は `getattr(..., False)` で通常モードとして扱う。専用の値 validation はない（`strata_cli/cli.py:508-515, 2236-2242`）。

`--profile` は必須で、`--output` は `human` または `json`（既定 `human`）。`--json` は `--output json` の別表記として同じ parser に追加される（`strata_cli/cli.py:258-267, 508-515`）。

## 実行時の動作

`ops init` は `recipes.initialize(profile)` を呼び、成功すると人向けには作成した名前、または `Recipes already initialized` を出す。`--quiet` の人向けモードでは、one-shot コマンドの stdout を最大 64 KiB まで一時捕捉し、終了コード 0 なら表示せず破棄する。したがって、このコマンドの成功メッセージは表示されない（`strata_cli/cli.py:1391-1398, 2196-2215, 2236-2248`）。

`--quiet` と `--output json`（または `--json`）を併用すると JSON は抑制されない。JSON 指定は quiet 捕捉より優先され、成功時は `schema_version: 1`、`ok: true`、profile 名、今回作成した recipe 名の配列 `created` が stdout に出る（`strata_cli/cli.py:535-542, 2232-2237`; `strata_cli/cli.py:1393-1398`）。

## 適用条件と副作用

この初期化は profile が既に保存されていることを前提とする。profile 名は小文字英字で始まり、小文字英字・数字・`_`・`-` を使う最大64文字の ID として検証される。保存済み profile を読み込み、`restart`（`runtime.restart`）、`calibrate`（`engine.calibrate.measure`）、`check`（`components.verify`）の3 recipe を不足分だけ作成する。対応する recipe が既にあり、kind も一致すればそのまま残す。kind の不一致が事前確認で見つかった場合は作成を始める前に失敗する（`strata_control/profiles.py:25, 48-55, 150-166`; `strata_control/recipes.py:153-177`）。

作成先は profile ディレクトリ配下の `.ops/<profile>/`。必要なディレクトリを作り、recipe JSON を排他的な新規作成で保存するため、既存ファイルを上書きしない。ファイル作成時は `0600` を指定し、書込み後に flush と fsync を行う。ディレクトリは POSIX で `0700` にし、Windows では所有ユーザー向け ACL を設定する。quiet はこれらの操作に影響しない（`strata_control/recipes.py:38-59, 130-150`; `strata_control/private_files.py:320-346`）。

profile が未保存・不正、recipe ディレクトリや recipe ファイルの形式・権限に問題がある場合などは失敗し得る。処理途中の競合など、事前確認後にエラーが起きた場合に先行作成分を戻す処理は `initialize` にない（`strata_control/recipes.py:38-59, 153-177`; `strata_control/profiles.py:150-166`）。

## 出力とエラー

通常の失敗は `_run` が例外をエラー応答へ変換し、テキスト形式では `strata: ...` を stderr に出す。quiet が捕捉するのは stdout だけなので stderr のエラーは隠れず、戻り値の終了コードも維持される。quiet 中に失敗前の stdout があった場合は stderr へ送り直し、捕捉上限を超えていれば省略を示すメッセージも stderr に出す（`strata_cli/cli.py:527-532, 2166-2188, 2196-2215, 2241-2248`）。

不明な引数や必須 `--profile` の欠落は `argparse` の解析段階でエラーとなり、`_run` の quiet 処理には入りません（`strata_cli/cli.py:258-267, 2223-2231`）。

## 根拠

- parser と適用範囲: `strata_cli/cli.py:255-267, 508-515`。
- quiet による stdout 捕捉、JSON の優先、終了コード処理: `strata_cli/cli.py:2196-2248`。
- init の呼出しと成功出力: `strata_cli/cli.py:1391-1398`。
- 初期 recipe の照合・作成と格納先: `strata_control/recipes.py:38-59, 130-177`。
- profile の読み込みと未保存時のエラー: `strata_control/profiles.py:150-166`。
