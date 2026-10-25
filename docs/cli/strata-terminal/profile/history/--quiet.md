# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile history` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値なし。`store_true` の真偽フラグ |

## 役割

履歴取得が成功したときの標準出力を抑制します。履歴を取得する処理そのものは通常どおり実行されます。人間向け出力だけを抑えるため、`--output json` または `--json` と併用した場合は JSON を抑制しません（`strata_cli/cli.py:99-101,508-515,1006-1010,2232-2243`）。

## 使い方

```sh
strata profile history default --quiet
```

機械可読出力を得る場合は、`--quiet` を付けても JSON が標準出力に出ます。

```sh
strata profile history default --quiet --output json
```

## 値と既定値

値は取りません。parser は共通の one-shot オプションとして `action="store_true"` で登録し、`default=argparse.SUPPRESS` とします。指定しなければ属性自体が追加されず、実行時の `getattr(a, "quiet", False)` では偽として扱われます。複数回指定を拒否する独自検証はありません。値を後置すると未認識引数として parser エラーになります（`strata_cli/cli.py:508-515,2223-2231,2236`）。

`history` の出力形式は `--output {human,json}` で、既定値は `human` です。`--json` は one-shot parser に追加され、`--output json` に正規化されます（`strata_cli/cli.py:99-101,508-515,2232-2235`）。

## 実行時の動作

`strata profile history` はプロファイル名を受け取り、履歴一覧を取得します。コマンド共通処理でまずプロファイルを読み込み、その後 history 分岐で履歴を取得します。現在のプロファイル revision と保存済み revision が出力対象です。human 形式では各行に revision と `current` / `saved` を表示します。quiet 指定時は `_run()` の標準出力を一時捕捉し、終了コードが 0 なら捕捉内容を表示せず破棄します。JSON の場合はこの捕捉分岐を通らず、成功 JSON を通常どおり出します（`strata_cli/cli.py:968,1006-1010,535-542,2232-2243`; `strata_control/profiles.py:312-323`）。

履歴処理は `.history/<profile-name>` 以下の revision ファイルを読み取り、現在のプロファイルも読み込みます。履歴ファイルは revision 形式に合う通常ファイルのみ対象です。現在 revision を先頭に置き、残りは保存時刻の降順で返します。`--quiet` によってこの読取条件や並び順は変わりません（`strata_control/profiles.py:312-323`）。

## 適用条件と副作用

このオプションは one-shot parser 群に含まれる `strata profile history` で有効です。quiet は stdout の捕捉だけを行い、履歴取得に伴うファイル作成・更新・削除はありません。履歴取得のためのプロファイルディレクトリは `STRATA_PROFILE_DIR`、Windows の `APPDATA`、または Unix 系の `XDG_CONFIG_HOME`（未設定時はホーム下 `.config`）から決まります（`strata_cli/cli.py:508-515,2241-2248`; `strata_control/profiles.py:38-45,312-323`）。

`--output json` / `--json` 併用時は JSON が優先され、quiet で stdout は抑制されません（`strata_cli/cli.py:2232-2237`）。

## 出力とエラー

- human 出力では成功時の stdout を抑制し、終了コード 0 を返します。quiet なしの human 出力は履歴の各 revision と `current` / `saved` 表示です（`strata_cli/cli.py:1006-1010,535-542,2236-2243`）。
- プロファイル名が不正、プロファイルが存在しない、または読取に失敗する場合は通常のエラー経路になります。quiet は stderr を捕捉しないため、human モードでは `strata: ...` が stderr に出て、エラーコードを返します。quiet 分岐中に非ゼロ終了となり、stdout に内容があれば、その内容も stderr に再出力されます。捕捉内容が 64 KiB を超えて切り詰められた場合は、省略を示す文言を stderr に出します（`strata_cli/cli.py:2166-2188,2196-2214,2241-2248`; `strata_control/profiles.py:48-55,312-323`）。
- 必須のプロファイル名不足や余分な引数など parser のエラーは quiet の実行時捕捉より前に処理されます。JSON モードの実行エラーは JSON エラーを stdout に出し、エラーコードを返します（`strata_cli/cli.py:527-532,2223-2235`）。

## 根拠

- `strata_cli/cli.py:99-101` — `profile history` の parser、位置引数 `name`、出力形式と既定値。
- `strata_cli/cli.py:508-515` — `profile_history` を含む one-shot parser 群への `--quiet` / `--json` 登録。
- `strata_cli/cli.py:1006-1010` — 履歴取得と human 出力。
- `strata_cli/cli.py:527-542,2166-2188,2196-2248` — 成功・失敗出力、エラー変換、quiet の stdout 捕捉と失敗時再出力。
- `strata_control/profiles.py:38-55,312-323` — プロファイル保存場所、名前検証、履歴の読み取りと順序。
