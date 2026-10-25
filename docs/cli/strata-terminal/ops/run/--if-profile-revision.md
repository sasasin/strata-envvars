# `--if-profile-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--if-profile-revision` |
| 別名 | なし |
| 値 | 必須の `REVISION` 文字列。保存済み profile の revision と完全一致する値 |

## 役割

レシピの preview 後に保存済み serving profile が変わっていないことを確認してから、レシピを実行します。レシピ自体の変更を確認する `--if-revision` とは別の条件です。`--if-profile-revision` は `strata ops run` にだけ登録され、`ops plan` などでは受理されません（`strata_cli/cli.py:255-290`）。

## 使い方

```sh
strata ops plan restart-engine --profile local
strata ops run restart-engine --profile local --if-profile-revision 0123456789abcdef
```

実例では `ops plan` の結果に含まれる `profile_revision` の値を指定します。レシピ名と profile 名は利用環境のものに置き換えてください。

## 値と既定値

値は1つ必要です。parser は `REVISION` を文字列として受け取り、形式の正規表現 validation や既定値を設定していません。省略時は `None` となり、profile revision の比較を行いません（`strata_cli/cli.py:278-284`、`strata_control/recipes.py:363-373`）。

profile revision は保存 profile ファイルの生バイト列に対する SHA-256 の先頭16桁です（小文字16進数）。したがって、preview 時に得た値をそのまま指定します（`strata_control/profiles.py:62-64,150-166`）。指定値が現在値と一致しなければ、レシピ実行前に `profile changed after preview; plan it again before running` で失敗し、終了コードは `6` です（`strata_control/recipes.py:369-373`）。

## 実行時の動作

CLI はこの値を `recipes.run(..., expected_profile_revision=...)` に渡します。レシピの読み込み後、実行記録を作る前に現在の profile revision と比較します。そのため、この比較で不一致になった場合は journal の operation record を作成せず、レシピの処理にも進みません（`strata_cli/cli.py:1448-1457`、`strata_control/recipes.py:369-400`）。

比較はすべての対応レシピ種別に共通して先に行われます。`runtime.restart` レシピではさらに期待 revision が runtime restart に渡され、runtime が候補 profile を作成した後、drain 前にも再確認します（`strata_control/recipes.py:402-412`、`strata_control/runtime.py:1043-1068`）。

このオプションは `--if-revision`（レシピ revision）、`--if-owner-id`、`--if-instance-id`、`--if-source-sha256` と独立した確認条件です。レシピ revision と profile revision の両方を preview に固定したい場合は、それぞれの値を指定します（`strata_cli/cli.py:281-290`、`strata_control/recipes.py:369-394`）。

## 適用条件と副作用

profile revision の比較自体は読み取りです。省略すると比較を飛ばします。不一致なら profile の変更を許容して実行する fallback はなく、実行を拒否します。

一致して先へ進んだ後の副作用はレシピ種別によります。`runtime.restart` は runtime を再起動し得ます。`engine.calibrate.measure` は計測を行い新しいレポートを作成し、`components.verify` は component 情報を読み取り、レシピの `live` 設定時は GPU inventory も照会します。revision 条件はそれらの処理を変更せず、実行前提を追加します（`strata_control/recipes.py:395-428`）。

## 出力とエラー

実行前の revision 不一致は `ProfileError` として CLI の共通エラー処理に渡ります。通常出力では `strata: ...` を stderr に出し、`--output json` では `{"schema_version":1,"ok":false,"error":{"code":6,"message":"..."}}` 形式を stdout に出します（`strata_cli/cli.py:527-532,2170-2183`）。なお run 処理中の標準出力は stderr に振り向けられ、成功後は human 形式で operation JSON、JSON 形式で operation envelope が出力されます（`strata_cli/cli.py:1451-1464`）。

## 根拠

- `strata_cli/cli.py:255-290` — `ops run` parser と option scope、値の metavar、help。
- `strata_cli/cli.py:1448-1464` — profile/recipe の読み込み、引数転送、出力と終了コード。
- `strata_control/recipes.py:363-400` — revision の比較順序と mismatch error、journal 開始前の位置。
- `strata_control/recipes.py:402-428` — 各レシピの実行経路と restart への revision 転送。
- `strata_control/profiles.py:62-64,150-166` — profile revision の生成と profile load。
- `strata_control/runtime.py:1043-1068` — restart 時の再確認。
- `strata_cli/cli.py:527-532,2170-2188` — human/JSON エラー出力と例外処理。
