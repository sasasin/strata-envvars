# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile list` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 取らないフラグ（`store_true`）。未指定時は無効 |

## 役割

成功時の人間向け案内・一覧出力を抑えます。プロファイル一覧をスクリプトから実行し、成功時の表示を不要にする場合に使えます。プロファイルの検索や読み込み方法自体は変えません。

## 使い方

```sh
strata profile list --quiet
```

JSON が必要な場合は `--json`（または `--output json`）を併用します。

```sh
strata profile list --quiet --json
```

## 値と既定値

値は取りません。指定すると真、未指定では偽です。parser に範囲検証や値変換はなく、複数回指定しても有効状態になります。`strata profile list` に対する別名はありません。`--json` はこのコマンドを含む one-shot parser 群に追加される別オプションで、`--quiet` の別名ではありません。

## 実行時の動作

`strata profile list` は保存済みプロファイルを列挙して成功結果を作ります。既定の human 出力では各行に ID と revision（またはエラー）を表示し、該当がなければ `No saved profiles` と表示します。`--quiet` 指定時、CLI は human 出力を一時捕捉し、コマンドが終了コード 0 なら表示しません。

`--json` または `--output json` を指定すると、quiet でも JSON は抑制されません。`--json` は `--output json` に変換され、成功時は `{"schema_version":1,"ok":true,"profiles":[...]}` 形式の JSON が stdout に出ます。`--quiet` は出力形式や一覧内容を変更しません。

## 適用条件と副作用

このオプションは one-shot コマンドに適用されます。人間向け成功出力だけを抑え、プロファイル一覧を読み取る処理は引き続き実行されます。保存先ディレクトリは `STRATA_PROFILE_DIR`、Windows の `APPDATA`、または POSIX の `XDG_CONFIG_HOME`（未設定なら `~/.config`）から決まります。列挙時に各 JSON プロファイルを読み込み、破損などの `ProfileError` は一覧項目の `error` として返します。プロファイル読み込み経路は、管理者実行でロックされたファイルを必要に応じて修復すると記載されています。この読み取り・修復動作は quiet の有無で変わりません。

## 出力とエラー

human モードで成功したときは stdout が空になります（一覧が空の場合の `No saved profiles` も表示されません）。JSON モードでは成功 JSON を stdout に出します。一覧中の読み込みエラーは `profiles` の該当項目に `error` として含まれ、一覧コマンド自体は成功結果として返されます。

`--quiet` はエラーを無効化しません。失敗時のエラーは通常どおり stderr に `strata: ...` として出力され、該当エラーの終了コードが返ります。JSON モードではエラー JSON が stdout に出ます。未対応の引数は argparse が拒否し、usage とエラーを stderr に表示します。

## 根拠

- `strata_cli/cli.py:75-76` — `profile list` parser と `--output` の既定値。
- `strata_cli/cli.py:508-515` — `profile_list` を含む one-shot parser に `--json` と値なし `--quiet` を追加。
- `strata_cli/cli.py:958-967` — `list_profiles()` 呼び出し、人間向け一覧・空一覧メッセージ、成功結果。
- `strata_cli/cli.py:527-542` — human/JSON の成功出力とエラー出力、終了コード。
- `strata_cli/cli.py:2196-2214`, `2232-2248` — quiet 時の stdout 捕捉、成功時の抑制、失敗時の捕捉出力の stderr への退避、JSON 出力時の抑制除外。
- `strata_control/profiles.py:38-45` — プロファイル保存先の決定。
- `strata_control/profiles.py:150-182` — 各プロファイルの読み込み、列挙、エラー項目化。
- `strata_control/profiles.py:155-156` — 読み込み時の権限修復経路。
- `docs/TERMINAL.md:224-226` — one-shot の `--json` と `--quiet` の説明。ソース実装と整合。

調査は上記 commit のソースと同梱文書に基づきます。同一 revision の CLI help および Release 配布物との照合は行っていません。
