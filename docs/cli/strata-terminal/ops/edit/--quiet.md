# `strata ops edit --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops edit` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は無効 |

## 役割

レシピ編集に成功したときの人向け完了メッセージを stdout に出さないためのフラグです。編集用エディターの起動、レシピの検証・保存、標準エラーのエラー表示を無効にはしません。

## 使い方

```sh
strata ops edit restart --profile local --quiet
```

`restart` は編集対象レシピ名、`local` は必須の profile 名です。編集には環境変数 `VISUAL` または `EDITOR` で利用できるエディターを設定してください。

## 値と既定値

- `--quiet` は値を受け取らず、指定すると `True` になります。省略時は `False` です。短縮 alias はありません。
- `--profile PROFILE` は必須で、レシピとその保存領域を選びます。`ops edit` では名前位置引数も必要です。
- `--output` の既定値は `human`、選択肢は `human` と `json` です。`--json` は `--output json` の alias です。
- 同じ `--quiet` を複数回指定する場合も真偽値が有効になるだけです。値を付けたり、サポートされない値を渡した場合は argparse の引数エラーになります。

## 実行時の動作

`--quiet` は `strata ops` の one-shot サブコマンド群に共通で登録されます。`main()` は `quiet` が有効で出力形式が `human` の場合、通常コマンドの stdout を捕捉し、終了コードが 0 なら表示せず破棄します。したがって `ops edit` の成功時に通常表示される `Saved recipe NAME: OLD -> NEW` は出ません。レシピ編集自体の処理順序は変わりません。

`ops edit` は保存済みレシピを読み、`VISUAL` が空でなければ `EDITOR` を選びます。選んだ文字列を分割し、一時 JSON ファイルを作ってエディターに渡します。エディターが正常終了すると JSON を読み直し、レシピの構造と kind ごとの値を検証して保存します。変更があれば前の revision を履歴に保存してから新しい内容を保存し、変更がなければ現在の revision を返します。

`--output json` または `--json` を併用すると、quiet 指定時も `main()` は出力を捕捉せず、JSON 成功結果を stdout に出します。これは quiet が人向け出力に適用され、機械可読出力には適用されないためです。

## 適用条件と副作用

- 成功した編集では一時 JSON を作成し、エディター子プロセスを起動します。変更内容が有効なら、レシピを profile の ops 保存領域に書き換え、前の revision を履歴として残します。未変更なら保存・revision 更新はありません。
- POSIX では保存領域・レシピ・履歴に owner-only の権限を要求します。レシピは通常ファイルで 64 KiB 未満である必要があります。レシピの profile/id、schema version、kind、kind 固有 params も検証されます。
- `VISUAL` と `EDITOR` のどちらも設定されていない場合、選択値が空の場合、レシピが欠落・不正な場合、エディターが異常終了した場合、または編集 JSON が不正・規則違反の場合は失敗します。エディター異常終了または JSON/保存検証失敗時は、編集 draft を一時ファイルに残し、そのパスをエラーに含めます。それ以外では一時ファイルを削除します。
- quiet は stdout の捕捉です。エラーは `_error()` が stderr に出すため、抑制されません。外部エディターの出力も子プロセスの標準出力・標準エラーを継承するため、quiet の捕捉対象外です。
- profile/recipe が編集処理中に変わった場合は revision 照合に失敗し、競合として保存を拒否します。

## 出力とエラー

- 人向け出力で成功した場合、quiet 指定時は stdout に完了メッセージを出しません。quiet なしならレシピ名と旧・新 revision を表示します。
- `--output json` / `--json` では成功時に schema version、recipe、previous revision、revision を含む JSON を stdout に出します。
- 例外は CLI 共通処理でエラーとして出力されます。`ValueError` 系は例外の exit code（未指定なら 2）、`OSError` は 6 です。JSON 出力時はエラー JSON、それ以外は `strata: ...` を stderr に出します。quiet のときもエラーは表示されます。
- quiet 実行中に失敗前の stdout があれば stderr に再出力されます。捕捉量の上限を超えた場合は、先行する人向け出力を省略した旨も stderr に出ます。parser が引数を拒否した場合はコマンド本体に入る前に使用法エラーとなり、quiet の出力捕捉対象外です。
- エディターが非ゼロ終了すると exit code 6 で draft の場所を示します。編集内容の JSON 構文エラーは exit code 2、レシピ revision の競合は 6 で、draft は保持されます。

## 根拠

- `strata_cli/cli.py:255-268,508-515` — `ops` のサブコマンド登録、`edit` の名前/profile/output、各 ops parser への `--quiet` と `--json` の追加。
- `strata_cli/cli.py:535-542,1419-1422` — edit 成功時の人向けメッセージと JSON 結果。
- `strata_cli/cli.py:2119-2129,2160-2173,2176-2188,2217-2248` — ops の実行分岐、例外出力、quiet 時の stdout 捕捉・破棄と JSON の適用除外。
- `strata_control/recipes.py:28-35,38-59,93-114,180-197` — 名前・profile、保存領域、レシピの形式・権限・内容検証と読み込みエラー。
- `strata_control/recipes.py:214-237,299-327` — revision 競合確認、履歴とレシピの保存、エディター選択・起動・draft 保持・一時ファイル削除。
