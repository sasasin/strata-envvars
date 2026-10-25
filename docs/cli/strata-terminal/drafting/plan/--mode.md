# `strata drafting plan --mode`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` のいずれか。省略可能。 |

## 役割

DFlash2 drafter の取得計画を、指定した drafting の選択に基づいて判定します。`plan` は情報表示だけを行い、ダウンロードや pack の作成はしません。`--mode` を省略すると、`--config` があればその run config の `drafting` 値を使い、それもなければ `auto` として判定します（`strata_cli/drafting_cmd.py:23-29,40-55,63-73`、`strata_control/drafting.py:23-25,136-138`）。

## 使い方

```sh
strata drafting plan --mode dflash2 --family qwen --data-dir ./strata-data
```

この例では、Qwen family と指定したデータフォルダーに対して DFlash2 を選んだ場合の計画を表示します。`--config FILE` を併用すると、config 内のモデル名とデータフォルダーを使い、明示した `--mode` が config の `drafting` を上書きします（`strata_cli/drafting_cmd.py:23-26,40-55`）。

## 値と既定値

- parser は `choices=drafting.MODES` により `auto`、`mtp`、`dflash2`、`off` のみを受理します。既定値は parser 上 `None` で、値を省略した場合は config の `drafting`、それも未設定・読み込み不能なら `normalize()` の `auto` に相当します（`strata_cli/drafting_cmd.py:23-26,40-55`、`strata_control/drafting.py:23-25,136-138`）。
- 不正な値は `argparse` が拒否して usage とエラーを表示します。繰り返し指定時は `argparse` の通常の単一値引数として最後に指定した値が残ります。空文字は choices に含まれないため拒否されます（`strata_cli/drafting_cmd.py:26`）。
- `--config` が指定されると UTF-8 BOM を許容して JSON を読みます。ファイル読み込みまたは JSON 解析に失敗した場合、この処理は空 config として続けます（`strata_cli/drafting_cmd.py:40-46`）。

## 実行時の動作

`--mode` は `needs_pack()` と `decide()` の両方へ渡されます。`auto` は GPU architecture class による suggestion を使い、`mtp` は MTP、`off` は draft layer 無効を選びます。`dflash2` はモデル適合性、engine の serving 対応、pack の存在を順に判定します（`strata_cli/drafting_cmd.py:54,62-66`、`strata_control/drafting.py:67-80,162-183`）。

この revision の suggestion table は全 card class (`strix_halo`、`blackwell`、`rdna4`、`ampere`、`other`) で MTP を返します。また `ENGINE_SERVES_DFLASH2` は `False` です。そのため `auto` も `dflash2` もこの plan コマンドでは drafter の取得を必要とせず、明示した `dflash2` は「この mode では利用できない」として MTP に fallback します。`mtp` は MTP、`off` は `off` 判定です（`strata_control/drafting.py:50-56,76-80,141-146,162-183`）。

`--family` が指定されている場合は family (`qwen` または `gyro`) で DFlash2 の適合性を判定し、family がない場合は config の `model_name` を使います。`--data-dir` は config から推定するデータフォルダーより優先し、両方ともなければ Strata の既定データフォルダーを探索します（`strata_cli/drafting_cmd.py:23-26,47-55`、`strata_control/drafting.py:102-111`）。`--config` の `args` からデータフォルダーを抽出する規則は `--pack` または `--mtp` 引数を読み取る実装です（`strata_control/drafting.py:203-212`）。

GPU architecture の取得に失敗した場合は例外を外へ出さず、card class を `other` として判定します（`strata_cli/drafting_cmd.py:32-37`）。

## 適用条件と副作用

`plan` は `drafting_fetch.plan()` から pack の存在、想定ダウンロード量、配置先、repository revision などを取得し、選択された mode に応じた `needed` と説明文を加えて表示します。すでに有効な pack があれば `ready` とされます（`strata_cli/drafting_cmd.py:60-73`、`strata_control/drafting_fetch.py:29-39`、`strata_control/drafting.py:114-122`）。

このコマンドの plan 分岐はファイルを書き換えません。実際にネットワークから取得して pack を作るのは `fetch` 側であり、今回の対象オプション文書の対象外です（`strata_cli/drafting_cmd.py:63-73,87-101`、`strata_control/drafting_fetch.py:54-101`）。

## 出力とエラー

- 既定の human 出力は、通常は取得計画の説明文を表示します。mode が要求されたが適用できないとき（例: `--mode dflash2`）は `drafting.summary_line()` による fallback 理由の行を表示します（`strata_cli/drafting_cmd.py:63-73`、`strata_control/drafting_fetch.py:29-39`）。
- `--output json` または `jsonl` では、`schema_version: 1`、`ok: true` と計画情報（`needed`、`serves`、`drafter`、`note`、`line` 等）を JSON で stdout に出します。mode を明示し、取得不要なら `gb` は `0.0` に補正されます（`strata_cli/drafting_cmd.py:29,58-70`）。
- 不正な `--mode` は `argparse` の parser error となり、usage とエラーを stderr に出して終了コード 2 になります。plan 分岐内で個別の失敗戻り値は定義されていません。config の読込・JSON エラーは前述のとおり空 config に置き換わります（`strata_cli/cli.py:40-45,2217-2231`、`strata_cli/drafting_cmd.py:26,40-46,63-73`）。

## 資料との照合と調査範囲

Strata の `docs/release-notes-0.2.3.md:7` は Terminal で `--drafting dflash2` を選べると説明しています。一方、この調査対象 commit の `strata_control/drafting.py:141-146` は server mode では engine が DFlash2 を提供しないとして `ENGINE_SERVES_DFLASH2 = False` としています。本書は指定 commit のソース挙動を記載し、release note の説明をこの checkout の実行結果として扱っていません。

安全な同一 revision の CLI `--help`、配布 Release artifact、各 OS/backend 上での実行結果は確認していません。したがって、parser が宣言する受理範囲とソース上の計画ロジックを記録し、配布物における実挙動は断定しません。

## 根拠

- `strata_cli/cli.py:40-45,172-173,2144-2146,2217-2231` — root parser、`drafting` parser の登録、実行 dispatch、parser error の処理。
- `strata_cli/drafting_cmd.py:17-29` — `plan` / `fetch` parser、`--mode` choices と output 形式。
- `strata_cli/drafting_cmd.py:40-73` — config/data directory/mode の解決、plan 結果と表示。
- `strata_control/drafting.py:23-25,50-80,102-122,136-183` — mode 値、suggestion、適合条件、既定化、decision と取得要否。
- `strata_control/drafting_fetch.py:29-39,54-101` — 計画値と fetch のファイル・ネットワーク処理。
- `docs/release-notes-0.2.3.md:7` — 利用者向け資料との照合対象。
