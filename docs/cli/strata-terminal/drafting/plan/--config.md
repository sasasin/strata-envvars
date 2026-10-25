# `--config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--config` |
| 別名 | なし |
| 値 | run config JSON のファイルパス（`FILE`）。任意。 |

## 役割

指定したモデルの run config を使って、DFlash2 drafter の取得計画と選択状態を表示します。`plan` は表示のみで、ダウンロードや設定変更は行いません。`--config` が指定するのは Strata の run config であり、DFlash2 自体の設定ファイルではありません（parser: `strata_cli/drafting_cmd.py:20-26`、計画分岐: `strata_cli/drafting_cmd.py:63-73`）。

## 使い方

```sh
strata drafting plan --config /path/to/strata-model.json
```

任意の `--mode` で run config 内の `drafting` 選択を上書きできます。データフォルダーも明示する場合は `--data-dir DIR` を指定してください（`strata_cli/drafting_cmd.py:23-26,47-54`）。

## 値と既定値

- 値は1つのファイルパスです。parser に `required` や既定値はなく、省略時は `None` です（`strata_cli/drafting_cmd.py:22-26`）。
- 指定時は UTF-8 BOM を許容する `utf-8-sig` でテキストを読み、JSON として解析します。ファイル読み込み時の `OSError` と JSON 解析時の `ValueError` は捕捉され、空の設定として扱われます（`strata_cli/drafting_cmd.py:40-46`）。したがって、存在しないパスや不正な JSON はこのオプション単独ではエラーにならず、既定の判断へ進みます。
- JSON がオブジェクトであることの検証はありません。JSON として有効でもオブジェクト以外（例: 配列や `null`）を指定すると、後続の `.get()` 呼び出しで `AttributeError` になる経路があります（`strata_cli/drafting_cmd.py:44-54`）。この例外は `strata_cli/cli.py:2119-2127,2166-2193` の `_run` が捕捉する例外に含まれず、通常の CLI エラー出力・終了コードになるとは確認できません。

## 実行時の動作

- 指定ファイルから `drafting_cmd` が参照するのは `drafting`、`model_name`、`args` です。`args` に `--pack` または `--mtp` があれば、そこからモデルの data folder を推定します（`strata_cli/drafting_cmd.py:42-54`、`strata_control/drafting.py:203-212`）。
- モードは `--mode` が指定されていればそれを使い、そうでなければ設定の `drafting` を使います。どちらもなければ `drafting.normalize()` により `auto` として扱われます。受理モードは `auto`、`mtp`、`dflash2`、`off` です（`strata_cli/drafting_cmd.py:26,54`、`strata_control/drafting.py:23-24,136-138`）。
- data folder は `--data-dir` があればそれを優先し、次に config の `args` から推定します。推定できない場合は `Catalog().data_dir()` を使います（`strata_cli/drafting_cmd.py:47-54`、`strata_cli/launch/catalog.py:494-501`）。
- `--family` を指定すると config の `model_name` よりその family が DFlash2 対応判定に使われます。省略時は config の `model_name` が判定材料です（`strata_cli/drafting_cmd.py:25,54`、`strata_control/drafting.py:107-111`）。
- plan は選択モード、GPU architecture class、model/family、data folder から drafter と取得要否を判断します。architecture は検出された CUDA/HIP architecture のうち判定表に合うものから分類され、不明・未検出なら `other` です（`strata_cli/drafting_cmd.py:32-37`、`strata_control/drafting.py:58-79`）。
- 調査対象 revision では `ENGINE_SERVES_DFLASH2 = False` です。そのため `needs_pack()` は `dflash2` が選ばれていても `needed` を false とし、明示的に `dflash2` を選んだ場合の判定結果は MTP と「このモードでは利用できない」旨の note になります。plan は `--config` または `--mode` があり `needed` が false のとき、JSON の `gb` を `0.0` にします（`strata_control/drafting.py:141-146,162-183`、`strata_cli/drafting_cmd.py:63-68`）。
- `--config` がなく `--mode` もないときは、汎用の drafter取得計画を表示します。`--config` または `--mode` があり note がある場合は選択結果の行を人間向け出力に使います。それ以外の人間向け出力は downloader の計画文です。JSON/JSONL 指定時は成功結果を JSON で出力します（`strata_cli/drafting_cmd.py:57-73`）。

## 適用条件と副作用

このオプションは `strata drafting plan` と `strata drafting fetch` の両 parser に共通ですが、本書の対象は `plan` です（`strata_cli/drafting_cmd.py:17-29`）。`plan` はネットワーク取得処理を呼ばず、指定ファイルの読み込みと data folder・pack の存在確認、GPU architecture 情報の照会を行います（`strata_cli/drafting_cmd.py:32-73`、`strata_control/drafting.py:118-122`）。実際にファイルを取得・pack するのは別コマンド `strata drafting fetch` です。

## 出力と失敗

- `--output human` が既定です。選択された状態に応じて計画文または `Drafting: ...` の行を stdout に出し、終了コード `0` で戻ります（`strata_cli/drafting_cmd.py:29,69-73`）。
- `--output json` または `jsonl` は parser で受理されますが、plan 分岐の出力はいずれも単一の JSON オブジェクトです。成功時は `schema_version: 1` と `ok: true`、plan 情報を含みます（`strata_cli/drafting_cmd.py:29,59,69-71`）。
- 指定 config の読み込み失敗・JSON 構文エラーは上記のとおり空設定へフォールバックするため、エラー文や非ゼロ終了とはなりません（`strata_cli/drafting_cmd.py:42-46`）。有効な JSON でもオブジェクト以外の場合の未捕捉例外は「値と既定値」を参照してください。

## 根拠

- `strata_cli/drafting_cmd.py:17-29` — `drafting plan` parser と `--config FILE` の宣言。
- `strata_cli/drafting_cmd.py:40-73` — config の読込、入力値の優先順位、plan 出力。
- `strata_control/drafting.py:23-24,58-79,107-122,136-183,203-212` — モード、GPU class、対応 model、pack 判定と data folder 推定。
- `strata_cli/launch/catalog.py:494-501` — data folder の fallback。
- `strata_cli/cli.py:2119-2127,2144-2146,2166-2193` — コマンド dispatch と捕捉する例外。
