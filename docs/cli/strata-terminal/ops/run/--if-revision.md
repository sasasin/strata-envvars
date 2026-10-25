# `--if-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--if-revision` |
| 別名 | なし |
| 値 | `REVISION` を1つ取る。保存 recipe の revision 文字列と完全一致することを実行時に照合する。 |

## 役割

`strata ops plan NAME --profile PROFILE` で確認したあと、その時点の保存 recipe が変更されていないことを条件に実行するための任意のガードです。recipe revision が一致しなければ、recipe の内容に基づく操作を始めずに失敗します。保存 serving profile の revision を照合する `--if-profile-revision` とは別の値・条件です。

## 使い方

```sh
strata ops plan restart --profile four-gpu --output json
strata ops run restart --profile four-gpu --if-revision RECIPE_REVISION
```

`RECIPE_REVISION` は plan 結果の `recipe_revision`、または `strata ops show restart --profile four-gpu` の `revision` から取得します。recipe と serving profile の両方を preview 時の状態に限定したい場合は、別途 `--if-profile-revision PROFILE_REVISION` も指定します。

## 値と既定値

- `--if-revision` は `argparse` の通常の文字列引数で、`metavar="REVISION"` です。省略時の値は `None` で、比較を行いません。オプション名だけで値を省くと parser の usage error になります（`strata_cli/cli.py:278-290`）。
- recipe revision は recipe ファイルのバイト列に対する SHA-256 の先頭16桁の小文字16進文字列です（`strata_control/recipes.py:188-196`、`strata_control/profiles.py:62-64`）。
- CLI parser は値の形式・長さを事前検証しません。`strata_control.recipes.run` が読み込んだ revision との文字列完全一致を調べるため、誤った形式や大文字を含む値も受理後に不一致として扱われます（`strata_control/recipes.py:369-371`）。
- 同じオプションを複数回指定した場合の専用処理はありません。`argparse` の既定動作により、最後に指定した値が比較に使われます。

## 実行時の動作

`strata ops run` はまず対象 recipe を読み、ファイル内容から算出した revision と指定値を比較します。一致しなければ `ProfileError`（終了コード6）を送出し、recipe を再計画してから実行するよう促します。この比較は operation journal の開始記録より前に行われるため、不一致時にはこの run による journal record も作られません（`strata_control/recipes.py:363-373,397-400`）。

一致した場合は、読み込んだ recipe に従って実行します。revision ガード自体は操作内容を変えず、recipe が変更された状態での実行を止めます。revision は保存 recipe の内容から算出されるため、内容を変更して保存すると対応する revision に変わり、rollback で過去の内容を復元するとその内容の revision に戻ります（`strata_control/recipes.py:214-237,253-280`）。

recipe の種類によって、ガード通過後の処理と副作用は異なります。

- `runtime.restart`: runtime restart を行い、現在の instance を drain して新 instance を開始します（`strata_control/recipes.py:375-412`）。
- `engine.calibrate.measure`: `--exclusive` も必要です。測定用 engine を起動し、設定済み `report_dir` に一意名の新規 report を書きます。run config の変更や tuning の自動適用は行いません（`strata_control/recipes.py:395-397,413-423`）。
- `components.verify`: component を検査します。recipe の `live` が真なら host GPU inventory を照会し、recipe 実行によるファイル書き込みはありません（`strata_control/recipes.py:424-428`）。

recipe revision の照合は recipe を一度 load した直後の比較であり、recipe 保存処理とのロックを実行全体に保持する仕組みはこの経路にありません。照合後にファイルが更新されても、この呼び出しは読み込んだ recipe の内容を使って進みます（`strata_control/recipes.py:369-374,397-400`）。

## 適用条件と副作用

このオプションは `strata ops run` にのみ登録されています。`--profile` と recipe 名が必要です。オプションを省略すれば revision 条件なしで実行します。recipe が存在しない、壊れている、形式不正、または POSIX で所有者専用権限要件を満たさない場合は、revision 比較より前の load で失敗します（`strata_cli/cli.py:255-290`、`strata_control/recipes.py:180-196`）。

revision 不一致時に recipe の操作や journal 記録は開始しません。一致後に操作が受理されると、`ops run` は operation record を作り、実行結果に応じて成功・失敗状態を記録します（`strata_control/recipes.py:397-438`）。このオプションは profile revision、runtime owner/instance、candidate source bytes を照合しません。それらの条件が必要な場合はそれぞれ `--if-profile-revision`、`--if-owner-id` / `--if-instance-id`、`--if-source-sha256` を使います（`strata_cli/cli.py:281-290`、`strata_control/recipes.py:372-394`）。

## 出力とエラー

- revision が一致しない場合、エラー文は `recipe changed after preview; plan it again before running`、終了コードは6です（`strata_control/recipes.py:370-371`）。通常出力では `strata: ...` を stderr に出し、`--output json` では `{"schema_version":1,"ok":false,"error":{"code":6,"message":"..."}}` 形式の JSON を stdout に出します（`strata_cli/cli.py:527-532,2166-2188`）。
- revision が一致しても、recipe 実行結果が失敗なら operation の JSON/human 表示と recipe の結果コード（既定5など）を返します。成功時は0です（`strata_cli/cli.py:1451-1464`）。
- revision の不一致や load error は `recipes.run` 呼び出し前または journal 開始前に発生するため、このオプションの不一致に対する操作実行結果・operation ID は出力されません（`strata_cli/cli.py:1448-1457`、`strata_control/recipes.py:369-400`）。

## 根拠

- `strata_cli/cli.py:255-290` — `ops` parser 階層、必須の profile/name と `--if-revision` 宣言。
- `strata_cli/cli.py:1391-1464` — `ops run` の分岐、revision 値の引き渡し、結果・終了コード。
- `strata_control/recipes.py:180-196` — recipe の読込・検査および revision の算出呼び出し。
- `strata_control/recipes.py:363-438` — revision 比較、各 kind の適用処理、副作用、journal 記録。
- `strata_control/profiles.py:62-64` — revision の SHA-256 先頭16桁形式。
- `strata_cli/cli.py:527-532,2166-2188` — human/JSON error 出力と例外の終了コード処理。
- `docs/TERMINAL.md:98-122` — `ops plan` / `ops run` の利用例と operator recipe の動作概要。利用者向け説明として参照し、実装の詳細は上記ソースで確認。

## 調査範囲

調査対象 checkout は上記 commit のソースです。別 revision の配布済み CLI や Release artifact は照合していません。`--help` は実行せず、parser 定義と同一 checkout のソースを根拠にしました。
