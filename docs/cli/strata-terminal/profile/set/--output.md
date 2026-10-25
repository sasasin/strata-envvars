# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile set` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ出力形式を選ぶ別オプション） |
| 値 | `human` または `json` |

## 役割

`strata profile set` の成功結果を人向けまたは JSON 形式で標準出力へ出します。設定値の変更方法や保存の有無は選びません。変更を保存せず差分だけ確認する場合は、別オプションの `--plan` を使います。

## 使い方

```sh
strata profile set demo parallel=8 --output json --plan
```

この例は `demo` プロファイルの `parallel` を `8` にした場合の差分を JSON で表示します。`--plan` を外すと変更を保存します。

## 値と既定値

- 値は小文字の `human` または `json` に限られます。省略時は `human` です。parser は `choices=("human", "json")` と `default="human"` を指定しています。[`strata_cli/cli.py:84-88`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L84-L88)
- `--output` は値を取る通常の `argparse` オプションです。同じオプションを複数回指定した場合は最後に指定した値が残ります。
- 選択肢以外の値は parser が拒否し、usage とエラーを標準エラーへ出して終了コード `2` で終了します。これは `main` が `_run` より前に `parse_known_args` を行うため、コマンド共通の JSON エラー処理より前の失敗です。[`strata_cli/cli.py:2217-2231`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L2217-L2231)

## 実行時の動作

- 成功時、`--output json` は `schema_version: 1` と `ok: true` を含む JSON オブジェクトを1行で標準出力に出します。`--output human` では通常、保存時の変更概要を人向けの文面で出します。[`strata_cli/cli.py:535-542`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L535-L542) [`strata_cli/cli.py:986-997`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L986-L997)
- `--json` は `profile set` を含む one-shot コマンドに追加され、`--output json` と同様に扱われます。両方を指定した場合も JSON です。[`strata_cli/cli.py:508-515`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L508-L515) [`strata_cli/cli.py:2232-2237`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L2232-L2237)
- `--plan` 併用時は保存せず、`changes` と `would_save` を結果に含めます。ただし human 出力用の文面はこの分岐で渡されないため、`--output human` の場合も成功結果は整形 JSON になります。`--output json` なら成功 envelope 内に同じ計画データが入ります。[`strata_cli/cli.py:986-992`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L986-L992) [`strata_cli/cli.py:535-542`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L535-L542)
- `--output json` 自体は設定ファイルを書き換えません。一方、`--plan` がなければ `profile set` は `propose_values` の結果を `save` に渡します。値に実質的な変更があれば、現在の revision を照合したうえで履歴を保存し、プロファイルを更新します。同じ値なら保存関数は現行データを返し、更新しません。[`strata_cli/cli.py:986-997`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L986-L997) [`strata_control/profiles.py:266-295`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L266-L295)

## 適用条件と副作用

このオプションは `strata profile set` 専用です。同じ `--output` でも他コマンドでは値や意味が異なり得ます。`profile set` に `--output` 固有のファイル・ネットワーク・プロセス操作はありません。出力形式にかかわらず、保存モードではコマンド本体がプロファイルと必要な履歴を更新します。設定先は `STRATA_PROFILE_DIR`、Windows の `APPDATA`、または POSIX の `XDG_CONFIG_HOME`（未指定時はホーム配下）から解決されます。[`strata_control/profiles.py:38-45`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L38-L45) [`strata_control/profiles.py:284-295`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L284-L295)

## 出力とエラー

- JSON モードの通常のコマンドエラーは、標準出力に `schema_version: 1`、`ok: false`、`error.code`、`error.message` を持つ JSON を出し、エラー固有の終了コードで終了します。human モードでは `strata: ...` を標準エラーへ出します。[`strata_cli/cli.py:527-532`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L527-L532) [`strata_cli/cli.py:2166-2183`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L2166-L2183)
- 例として、未登録プロファイルは終了コード `5`、保存中に revision が変わった場合は `6` です。いずれも `--output json` なら JSON エラーとして処理されます。[`strata_control/profiles.py:150-166`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L150-L166) [`strata_control/profiles.py:271-295`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L271-L295)
- profile 名や `KEY=VALUE` の検証エラーも `_run` の `ValueError` 処理を通ります。オプション値自体の不正は parser 段階のため、この JSON エラー形式にはなりません。[`strata_cli/cli.py:2166-2173`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_cli/cli.py#L2166-L2173) [`strata_control/profiles.py:48-50`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L48-L50) [`strata_control/profiles.py:66-95`](https://github.com/Niko1221/Strata/blob/7dd5cf18e68c639a8773e096c5c79f971ea2a9f5/strata_control/profiles.py#L66-L95)

## 根拠

- parser 定義とコマンド階層: `strata_cli/cli.py:84-88`。
- JSON 成功・失敗 formatter と `--json` 処理: `strata_cli/cli.py:508-515`, `535-542`, `527-532`, `2232-2237`。
- `profile set` での出力分岐と保存呼び出し: `strata_cli/cli.py:986-997`。
- プロファイル値の提案・検証・保存、保存時の履歴と revision 確認: `strata_control/profiles.py:66-117`, `266-309`。

調査時の `git status --short --branch` は `## main...origin/main` で、作業ツリーに未コミット変更はありませんでした。CLI help は補助実行せず、ソースの parser・呼び出し・例外処理を根拠にしました。
