# `STRATA_PRESET_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

保存済みチューニングプリセットの保存場所を指定します。Strata の Python 共通モジュールがこの値をプリセット用ディレクトリとして使い、名前付きプリセットの JSON、active slot の `active.json`、測定履歴 `history.jsonl` を同じ場所に読み書きします。Terminal とサーバー／アプリのチューニング機能がこのストアを共有します。環境変数を設定しただけではチューニングやプリセット適用は有効にならず、適用対象の選択肢に合う active preset がストアにある場合に限って overlay されます（`strata_control/presets.py:1-17,45-50,202-208,234-252,441-479`）。

## 値と判定

| 値 | ディレクトリの決定 |
|---|---|
| 未設定 | `strata_control.profiles.profile_dir().parent / "presets"` |
| 空文字 | `os.environ.get()` が空文字を返し falsy になるため、未設定と同じ既定場所 |
| 空でない文字列 | `Path(value).expanduser()` を使用 |

文字列の値域・大文字小文字・数値としての解釈はありません。空白だけの文字列も非空なので明示パスになります。`expanduser()` による `~` 展開はありますが、`resolve()` や絶対パス化はしません。そのため相対パスは Python プロセスの作業ディレクトリ基準です。値の存在、ディレクトリ作成可能性、書込権限は `preset_dir()` 内では検証されません（`strata_control/presets.py:45-50`）。

未設定時の `profile_dir()` は、Windows では `APPDATA` または `~/AppData/Roaming` の下の `Strata/profiles`、それ以外では `XDG_CONFIG_HOME` または `~/.config` の下の `strata/profiles` です。その親の `presets` が既定場所です。したがって `STRATA_PRESET_DIR` が空の場合、`STRATA_PROFILE_DIR`、`APPDATA`、`XDG_CONFIG_HOME` の設定が既定場所に間接的に影響します（`strata_control/profiles.py:38-45`）。

## 有効になる条件

- 明示値が空でなければそのパスが優先され、profile/config 環境変数由来の既定場所は使いません。
- 指定先に active preset が存在し、実行設定から作られる slot と一致する必要があります。プリセットがない、active 指定がない、またはディレクトリが存在しない場合、overlay は設定を変えません（`strata_control/presets.py:234-252,441-456`）。
- PC・エンジン・モデルの identity が hard change と判定された場合、active preset は読み込まれても適用されません。soft change は再確認情報を付けて適用されます。安全規則に反する設定も適用されません（`strata_control/presets.py:158-197,457-479`）。
- サーバー起動時に `STRATA_NO_PRESET` が空でない場合は `apply_saved_tuning()` が早期 return し、プリセットを読みません。これは別の変数であり、Python の truthiness 判定なので文字列 `0` も抑止値です。チューニング worker は測定条件に既存プリセットを重ねないよう `STRATA_NO_PRESET=1` を設定します（`serve/server.py:7654-7664`, `strata_control/tune_session.py:469-479`）。

## 実行時の詳細

`preset_dir()` は値をモジュール import 時に固定せず、呼び出されるたびに `os.environ.get("STRATA_PRESET_DIR")` を評価します。プリセット操作ごとに `_path()`、`_index()`、`list_presets()` などから呼ばれるため、プロセス内で `os.environ` が変更された場合、以後の操作は新しい場所を参照します。子プロセスへの継承・上書きは各起動側の環境設定に依存し、この変数を個別に転送・変更する共通処理は見つかりませんでした（`strata_control/presets.py:45-50,78-81,202-208,234-252,441-454`）。

プリセットの作成時は JSON を指定先へ書き、active 状態は `active.json` に記録します。測定試行の履歴も同じ場所の `history.jsonl` に追記されます（`strata_control/presets.py:53-68,268-307,310-327,487-505`）。サーバーは Strata engine の設定ファイルを読む際、`STRATA_NO_PRESET` が設定されていなければ overlay を行い、適用された場合は変更した engine 引数・環境設定を設定に加えます。適用時には `[strata] saved tuning '…' applied: …` を出力します（`serve/server.py:7654-7679,8024-8029`）。Terminal の起動設定表示・有効設定表示・チューニング保存も同じ `presets` モジュールを使います（`strata_cli/launch/app.py:137-148`, `strata_cli/launch/runner.py:1004-1018`, `strata_cli/tune_commands.py:242-251,361-375`）。

保存先へのアクセスに失敗した場合、overlay 自体は例外を外へ出さず、元の設定を返します。サーバーの起動はプリセットストアの読込失敗によって失敗させない設計です（`strata_control/presets.py:441-482`, `serve/server.py:7654-7679`）。

## 文書との照合

`docs/DETAILS.md` は過去の `--calibrate` 設定の保存先について「data folder の記録の隣」と説明していますが、これは現行の保存済みチューニングプリセットの `STRATA_PRESET_DIR` 仕様を直接説明する記述ではありません（`docs/DETAILS.md:597-612`）。現行コードでは `strata launch` とアプリにも独自のチューニング手順があることは `docs/MODELS.md:68-72` に記載されています。性能値はこの環境変数の保存先機能そのものを測る値ではないため記載していません。

## 根拠

- `strata_control/presets.py:1-17,45-81,202-252,268-327,441-505` — 保存場所決定、ファイル構成、読み書き、active preset の適用。
- `strata_control/profiles.py:38-45` — 明示値未指定時に参照するプロフィール設定場所。
- `serve/server.py:7654-7679,8024-8029` — サーバー起動時の適用と観測可能なログ。
- `strata_control/tune_session.py:469-479`, `strata_cli/launch/app.py:137-148`, `strata_cli/launch/runner.py:1004-1018`, `strata_cli/tune_commands.py:242-251,361-375` — 測定 worker、Terminal 表示、保存経路。
- `docs/DETAILS.md:597-612`, `docs/MODELS.md:68-72` — 関連説明との照合。
