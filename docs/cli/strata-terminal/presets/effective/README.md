# `strata presets effective`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets effective` |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py`、`strata_control/profiles.py` |
| 引数 | `target`（保存済み profile 名、または run config JSON のパス） |
| 出力形式 | `--output human\|json`（既定値: `human`） |

## 役割

指定したモデル設定について、次回の起動に使われる設定へアクティブな tuning preset を重ねた結果を表示します。preset が適用されたか、構成から変わる engine 引数や環境変数、sampling 設定、適用されない場合の理由を確認できます。測定や engine の起動を行うコマンドではありません。

## 使い方

```sh
# 保存済み profile の実効設定を人向けに表示
strata presets effective my-profile

# JSON run config を指定し、機械処理向け JSON で表示
strata presets effective ./strata-model.json --output json
```

`target` に `.json` パス、絶対パス、または `/`・`\\` を含むパスを指定すると JSON 設定ファイルとして扱います。それ以外は保存済み profile 名として解決され、その profile の `source_config` を読みます。設定 JSON には文字列の `args` 配列と空でない `exe`、`tokenizer` が必要です。

## 実行時の動作

- active preset の検索に使う選択情報と model identity を構成から求め、該当 slot の active preset を読み込みます。preset の識別状態が `hard` の場合や、設定が安全規則を満たさない場合は適用せず、その理由を結果へ含めます。`soft` 状態では適用を続け、再確認が必要な理由を表示します。
- 適用可能なら元の設定のコピーに preset の engine 引数、環境変数、per-request 値を重ねます。設定ファイル自体は書き換えません。`changed` には元と適用後の engine 引数の差分が含まれます。
- JSON 出力のトップレベルには `schema_version: 1`、`ok: true` と、`applied`、`preset`、`state`、`reasons`、`why_not`、`notice`、`args`、`env`、`sampling`、`changed`、`per_request` を持つ結果が出ます。人向け出力は適用時に preset 名を、未適用時には標準設定を使う旨を表示します。

## 注意点

- `--output` は `human` または `json` を受け取り、既定値は `human` です。このサブコマンド固有のほかのオプションはありません。
- preset store が存在しない、または active preset が見つからない場合は、preset を重ねずに構成値を表示します。overlay の読み込み・検査中に例外が起きた場合も、overlay helper は例外を飲み込み、元の構成で `applied: false` の結果を返します。
- 実効値は選択した profile / run config と現在参照できる preset・identity に基づく確認結果です。別の設定を指定した起動や、表示後にファイル・環境が変わった起動の結果までは保証しません。
- コマンド本体は設定や preset を更新しません。ただし CLI 共通の起動処理で `private_files.adopt_user_defaults()` が呼ばれます。これは権限を上げた実行でもプロセスが作成するファイルをユーザー所有にする処理です。

## 関連文書

- [CLI 索引](../../../README.md) — `strata presets` のコマンド階層と各文書。
- [`strata presets`](../README.md) — preset 管理コマンドの概要。
- [`strata presets apply`](../apply/README.md) — preset の有効化。
- `strata presets status`、`show`、`off`、`strata tune auto` — 各項目は CLI 索引に予定パスとして掲載されています。

## 根拠

- Strata `strata_cli/cli.py:40-45,486-488` — Terminal CLI の parser と `presets` parser の登録。
- Strata `strata_cli/tune_commands.py:54-80` — `presets effective` と `target`、共通 `--output` の parser 定義。
- Strata `strata_cli/cli.py:2119-2152` — `presets` を `presets_command` に委譲する dispatch。
- Strata `strata_cli/tune_commands.py:289-305,361-378` — effective の呼び出し、合成結果と表示 payload の組み立て。
- Strata `strata_control/presets.py:441-480` — active preset の照合、staleness・設定検証、引数・環境・sampling への overlay と失敗時の fallback。
- Strata `strata_control/profiles.py:135-147,382-388` — run config の検証と profile 名 / JSON パスの解決。
- Strata `strata_cli/cli.py:2217-2224` — parser 実行前に行う CLI 共通の user-default ownership 処理。
