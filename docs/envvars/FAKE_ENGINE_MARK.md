# `FAKE_ENGINE_MARK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

確認できた用途はテスト用の偽エンジンが実行記録を書き出すパスの指定です。Strata の本番実装がこの環境変数を読む箇所は見つかりませんでした。以下の動作はテスト fixture に埋め込まれたスタブのもので、通常の Strata engine の動作を表しません。

## 値と判定

テスト用偽エンジンは `os.environ[...]` で値を取り出し、`Path(...)` に渡します。真偽値や数値への変換、空文字の特別扱い、既定値はありません。未設定なら、その偽エンジンが値を参照した時点で `KeyError` になります。値は出力先ファイルまたはディレクトリのパスとして解釈されます。

| fixture | 値の設定と記録内容 |
|---|---|
| terminal lifecycle matrix | 一時ディレクトリ内の `mark` ディレクトリを設定し、その直下に `engine.pid` とイベント時刻ファイルを作る |
| component start / updater | `ran.txt` のパスを設定し、偽エンジンのスクリプト絶対パスと引数を書き込む |
| desktop installed-flow | `engine-ran.json` のパスを設定し、PID、スクリプトパス、引数の JSON を書き込む |

## 有効になる条件

これらはテスト専用の fixture です。`tests/terminal/` のテストは一時ディレクトリへのパスを環境に設定して偽エンジンを起動します。`apps/desktop/scripts/installed-flow.mjs` と `app-close-matrix.py` も desktop の installed-flow / close-matrix 検証で偽エンジンにパスを渡します。実際の本番 engine にこの値を渡す一般機能や、CLI・設定ファイルとの優先順位は確認できません。

## 実行時の詳細

- `tests/terminal/lifecycle_matrix.py` の偽エンジンは起動時に `FAKE_ENGINE_MARK` を読み、PID とイベント記録を書きます。matrix のテストは一時 `mark` ディレクトリを設定します（`tests/terminal/lifecycle_matrix.py:41-49,138-152`）。
- component start と updater のテストは、偽 engine スクリプトに環境変数から得たファイルへ自身の絶対パスと引数を書かせます。テスト側では一時 `ran.txt` を設定します（`tests/terminal/test_component_start.py:25-28,60-69`; `tests/terminal/update_fixture.py:25-28`; `tests/terminal/test_updater.py:41-45`）。
- desktop の installed-flow は偽 engine の起動時に PID、script、argv を JSON ファイルへ書きます。制御プロセスおよび偽 engine を含む host 子プロセスへ、一時 `engine-ran.json` のパスを渡します（`apps/desktop/scripts/installed-flow.mjs:62-69,79-87,103-117,126-132`）。close-matrix も偽 engine 用に mark パスを設定します（`apps/desktop/scripts/app-close-matrix.py:82-91`）。

環境変数の読み取りは上記テスト用エンジンの起動時です。Strata 本番コードによる読み取り、プロセス内での再読込、設定変更時の挙動はありません。リポジトリ内の `docs/` にこの名前の説明は見つからず、`docs/DETAILS.md` にも記述はありません。

## 根拠

- `tests/terminal/lifecycle_matrix.py:41-49,138-152`
- `tests/terminal/test_component_start.py:25-28,60-69`
- `tests/terminal/update_fixture.py:25-28`
- `tests/terminal/test_updater.py:41-45`
- `apps/desktop/scripts/installed-flow.mjs:62-69,79-87,103-117,126-132`
- `apps/desktop/scripts/app-close-matrix.py:82-91`

上記の全参照を確認し、候補名はテスト用 fixture / 検証スクリプトにのみ現れました。調査対象の HEAD の作業ツリーは `main` で clean でした。
