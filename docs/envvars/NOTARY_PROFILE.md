# `NOTARY_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

macOS 配布物の署名・公証用スクリプト `tools/packaging/mac/sign-and-notarize.sh` が、`xcrun notarytool` に `--keychain-profile` として渡す Keychain profile 名を指定する。Strata の engine、server、通常の CLI の実行設定ではなく、この packaging スクリプトの実行時にだけ使われる。通常実行では起動前の profile 確認と各成果物の公証に同じ値を使う。`--dry-run` では公証を行わず、この値は profile 表示にも使われない（スクリプトは値の既定化自体は行う）。`tools/packaging/mac/sign-and-notarize.sh:13-21,47-48,206,221-230`

## 値と判定

スクリプト冒頭でシェルの `${NOTARY_PROFILE:-strata-notary}` を評価する。bash の `:-` により、環境変数が未設定または空文字なら `strata-notary` を採用する。空でない文字列はそのまま採用し、数値変換、文字列比較、trim、大小文字変換、profile 名としての形式検査はしない。値は引用符付き引数として `notarytool` に渡されるため、空白を含む値も一つの引数になる。`tools/packaging/mac/sign-and-notarize.sh:47-48,225,359,368`

| 条件 | unset | 設定時に使われる値 | 独自判定で無効になる値 |
|---|---|---|---|
| 通常実行 | `strata-notary` | 空でない値。例: `strata-notary`、`My Profile`、`0`、`false` | なし。値の妥当性は Strata 内で検査せず、後続の `notarytool history` の成否で preflight 判定する |
| `--dry-run` | `strata-notary` を代入するが公証には使わない | 空でない値を代入するが、公証には使わない | なし。dry-run は profile の成功可否を確認しない |

空文字は未設定と同じです。`0`、`false`、前後空白、大文字小文字違いも、空でなければ値としてそのまま渡されます。CLI に profile を指定する引数はなく、スクリプト内の `SIGN_ID` とは別々に処理されます。`tools/packaging/mac/sign-and-notarize.sh:47-48,66-81,174-181`

## 有効になる条件

- この値を読むのは `tools/packaging/mac/sign-and-notarize.sh` のみ。スクリプトは `uname -s` が `Darwin` でない場合、`This script runs on a Mac (it needs codesign, hdiutil, notarytool).` を stderr に出して終了コード 2 で停止する。`tools/packaging/mac/sign-and-notarize.sh:167-172`
- 通常実行（`--dry-run` なし）でのみ profile preflight を行い、`xcrun notarytool history --keychain-profile "$NOTARY_PROFILE"` が失敗すると `FAIL notary profile` と profile が機能しない旨を記録して終了コード 1 で停止する。Strata は成功時に `OK preflight: identity and notary profile found` を記録する。`tools/packaging/mac/sign-and-notarize.sh:221-230,123-124`
- `--dry-run` では `NOTARY_PROFILE` の preflight と `notarize` 呼び出しが省かれる。アプリの DMG、Terminal archive、engine package の各公証箇所は dry-run 分岐で skip を記録する。`tools/packaging/mac/sign-and-notarize.sh:18-21,221-231,545-574,716-721,779-784`
- 入力となる `.app` / `.dmg`、`--terminal`、`--engine` の組み合わせに応じて公証対象は異なるが、通常実行では各対象の `notarize` 呼び出しが同じ profile 値を使う。`--updater-archive` はアプリ入力を要求するが、profile の選択規則は変えない。`tools/packaging/mac/sign-and-notarize.sh:80-81,545-549,565-567,716-718,779-781`

## 実行時の詳細

値はスクリプトの初期化時（引数処理より前）にシェル変数へ一度代入され、その後は同じ値が preflight、notary submit、必要な場合の notary log 取得に使われる。後から親プロセスの環境を変更しても、実行中のこのシェルが値を再読込する処理はない。profile を上書きする CLI オプションもない。`tools/packaging/mac/sign-and-notarize.sh:47-48,66-79,221-226,354-376`

通常実行では profile preflight 成功後、アプリ、DMG、Terminal archive、engine package の該当経路で `notarize` 関数が呼ばれる。関数は `xcrun notarytool submit ... --keychain-profile "$NOTARY_PROFILE" --wait --timeout 60m` を実行し、出力を作業領域に保存してログへ追記する。status が `Accepted` なら成功を記録する。それ以外は submission ID が取れた場合に同 profile を使って `notarytool log` を呼び、最後に `FAIL notarise ...` と status（空なら `no answer from notarytool`）を記録して処理を終了する。これはコマンド呼び出し・出力判定についての記述であり、Apple 側や `notarytool` 内部の処理を説明するものではない。`tools/packaging/mac/sign-and-notarize.sh:354-376,548-549,565-567,716-718,779-781`

## ログと測定値

通常実行では開始時に `profile  : <値>` を標準出力と `sign-and-notarize.log` に記録する。preflight に失敗すると `FAIL notary profile: profile "<値>" does not work (create it once: xcrun notarytool store-credentials <値> ...), or there is no internet` を記録し、summary に `RESULT: FAILED...` を出して終了コード 1 となる。profile preflight のコマンド出力は `/dev/null` に送られる。成功時は `OK preflight: identity and notary profile found` を記録する。dry-run では profile 行は出さず、`mode     : DRY RUN (ad-hoc, no notarisation)` と公証 skip の行を出す。`tools/packaging/mac/sign-and-notarize.sh:84-85,108-113,123-124,204-207,221-230`

測定値は該当しない。

## 根拠

- `tools/packaging/mac/sign-and-notarize.sh:13-21,47-48` — 用途、既定値、dry-run の説明と初期化。
- `tools/packaging/mac/sign-and-notarize.sh:66-81,167-181` — CLI 引数と macOS / dry-run 条件。
- `tools/packaging/mac/sign-and-notarize.sh:221-231` — 通常実行の profile preflight と観測可能な結果。
- `tools/packaging/mac/sign-and-notarize.sh:354-376,545-549,565-574,716-721,779-784` — 実際の公証コマンド、status 判定、各入力経路の dry-run 条件。
