# `--from-config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile create` |
| オプション | `--from-config` |
| 別名 | なし |
| 値 | run config JSON のパス（`CONFIG.json`）。必須。 |

## 役割

新しい名前付き serving profile が参照する run config を指定します。profile は run config のコピーではなく、その設定ファイルへの絶対パスと空の overrides を持つ別ファイルとして保存されます。

## 使い方

```sh
strata profile create office --from-config /absolute/path/to/strata-model.json
```

`office` は新しい profile 名、パスは読み取り可能な run config JSON を指定します。`strata profile create` は名前を位置引数で受け取り、`--from-config` の省略は parser が拒否します（`strata_cli/cli.py:71-74`）。

## 値と既定値

- 値は必須の文字列です。`argparse` の通常の単一値引数として定義され、型変換や選択肢指定はありません。省略時は usage を伴う引数エラーになります（`strata_cli/cli.py:71-74`）。
- パスは `~` を展開し、`resolve(strict=True)` で存在を確認して解決した絶対パスとして記録します。相対パスも指定できますが、解決後のパスが保存されます（`strata_control/profiles.py:236-243`）。
- 空文字列を渡した場合も parser 段階では拒否されず、現在の作業ディレクトリを解決した後に run config として読み込もうとします。通常のディレクトリなら読み込み失敗になります（`strata_control/profiles.py:135-147,236-243`）。
- 複数回指定時の保持値は `argparse` の単一値 `store` 引数の規則に従い最後の値です（`strata_cli/cli.py:73`）。

run config として受理する最低条件は、JSON object であること、`args` が文字列のみの配列であること、`exe` と `tokenizer` が空でない文字列であることです。これらは既定値補完ではなく検証です（`strata_control/profiles.py:135-147`）。この関数は run config 全体の追加スキーマ検証を行いません。

## 実行時の動作

parser の値は `profiles.create(a.name, a.from_config)` に渡されます。create は名前を検証し、設定ファイルを読み取って最低条件を確認した後、`schema_version: 1`、`id`、解決済み `source_config`、空の `overrides` を含む profile を作成します。元の run config 内容は profile に複製されません（`strata_cli/cli.py:958-963`、`strata_control/profiles.py:236-249`）。

名前は小文字 a-z で始まり、全体が小文字英字・数字・`_`・`-` の最大64文字です（`strata_control/profiles.py:25,48-51`）。保存先は `STRATA_PROFILE_DIR` があればその値（`~` 展開あり）、なければ Windows では `%APPDATA%/Strata/profiles`（未設定時は home 配下）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）です（`strata_control/profiles.py:38-45`）。

## 適用条件と副作用

- 指定したパスを解決でき、内容を読み取れて、上記 run config 条件を満たす場合に限り作成されます。設定ファイルを実際に起動したり、ネットワークへ接続したりする処理はありません（`strata_control/profiles.py:135-147,236-243`。同ファイル冒頭の説明 `:1-5` も参照）。
- profile 保存ディレクトリを作成し、名前ごとの lock file を開いて排他ロックします。profile は一時ファイルへ書いて flush/fsync した後に置換保存され、一時ファイルは後始末されます（`strata_control/profiles.py:185-234,244-249`）。
- 同名 profile のファイルまたは symlink がすでに存在すると作成を拒否します。既存 profile は上書きしません（`strata_control/profiles.py:244-248`）。
- `--output human|json` は profile の成功結果の形式を選びます（既定値 `human`）。一方、共通 one-shot parser が追加する `--json` は parser 上受理されますが、成功処理は `a.output == "json"` のみを見ているため、`--json` 単独では成功結果を JSON に切り替えません（`strata_cli/cli.py:73-74,508-515,958-963`）。
- 同じ parser ループが `--quiet` も追加しますが、create handler はこれを参照しません。quiet による成功メッセージ抑制は実装されていません（`strata_cli/cli.py:508-515,958-963`）。

## 出力とエラー

- 成功時は終了コード `0`。`--output human`（既定）では `Saved profile <name> at revision <revision>`、`--output json` では profile オブジェクトと revision を含む JSON を stdout に出します（`strata_cli/cli.py:958-963,535-542`）。
- 名前不正、run config の必須キー不備、profile の重複など `ProfileError` / `ValueError` は、既定では `strata: <message>` を stderr に出し、通常の `ProfileError` は終了コード `2` です。`--output json` または `--json` がある場合、ValueError 系の失敗は JSON error envelope を stdout に出します（`strata_control/profiles.py:30-35,48-51,140-147,244-248`、`strata_cli/cli.py:527-532,2166-2173`）。
- パス解決不能や run config 読み込み時の I/O/JSON parse error は `ProfileError` 終了コード `5` です。その他の `OSError` は CLI 共通処理で整形され終了コード `6` になります（`strata_control/profiles.py:135-143,236-242`、`strata_cli/cli.py:2176-2183`）。
- `--from-config` など必須引数の不足や構文不正は argparse の解析段階で拒否されます。実行時の profile エラー処理には到達しません（parser 定義 `strata_cli/cli.py:71-74`）。

## 根拠

- parser、引数 scope、`--output`、共通 `--json` / `--quiet`: `strata_cli/cli.py:69-74,508-516`
- profile 作成の呼び出しと成功出力: `strata_cli/cli.py:958-963`
- profile 名、保存場所、run config の検査、profile 作成、重複拒否: `strata_control/profiles.py:25,38-59,120-147,236-249`
- lock と一時ファイルを使う保存処理: `strata_control/profiles.py:185-234`
- CLI の error 出力と終了コード処理: `strata_cli/cli.py:527-542,2166-2183`

調査時点の Strata checkout は `main...origin/main` で未コミット変更なしでした。CLI help の実行、build、テストは行わず、ソース parser と使用箇所を根拠にしています。
