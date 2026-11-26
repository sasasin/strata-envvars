# `SIGN_ID`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`SIGN_ID` は、macOS 向けの署名・公証用スクリプト `tools/packaging/mac/sign-and-notarize.sh` が `codesign --sign` に渡す署名 identity を指定する。通常実行では未設定または空文字ならスクリプト所有者の Developer ID identity を使い、値を指定すればその文字列を署名 identity として使う。アプリ本体の実行時設定ではなく、配布物を署名する同梱 packaging ツールの設定である（`tools/packaging/mac/sign-and-notarize.sh:13-21,47,272-276,287-290`）。

`--dry-run` はこの値を常に `-` に置き換え、ad-hoc identity で署名する。このモードは公証を省略し、リリース用ではないとスクリプトが表示する（同 `:174-182`, `:108-110`）。

## 値と判定

スクリプト起動時に Bash の `${SIGN_ID:-既定値}` を評価する。したがって未設定と明示的な空文字はいずれも `Developer ID Application: Niko Veit (79LR4R7RSC)` に置き換わる。`:-` で始まる Bash の既定値展開であり、数値や真偽値への変換、空白除去、大文字小文字変換はない。その他の非空文字列はそのまま保持され、通常実行では `-` だけを特別扱いする（同 `:47`, `:174-182`）。

| 条件 | unset | 有効になる値（例） | 無効・特別扱いの値（例） |
|---|---|---|---|
| 通常実行（`--dry-run` なし） | 既定 identity に置換 | `Developer ID Application: Niko Veit (79LR4R7RSC)`、Keychain に列挙される任意の identity 名 | 空文字も既定値に置換。`-` は終了コード 2 で拒否。それ以外はまず文字列として受理されるが、Keychain の identity と一致しなければ事前確認で失敗 |
| `--dry-run` 指定 | 起動時の既定値展開後、値にかかわらず `-` に上書き | 環境変数の値にかかわらず `-` を使用 | 値による無効値判定なし。dry-run 自体は macOS 以外では先に終了する |

通常実行の identity 照合は、`security find-identity -v -p codesigning` の出力に対して、引用符付き identity 名を `grep -qF` で固定文字列検索する。スクリプトは `SIGN_ID` に対する別個の構文検証をせず、`0`、`true`、空白を含む文字列なども値として保持するが、Keychain 出力と一致しない値は通らない（同 `:221-228`）。

## 有効になる条件

- スクリプトは `uname -s` が `Darwin` でなければ `This script runs on a Mac (it needs codesign, hdiutil, notarytool).` と stderr に出して終了コード 2 で終わる（`tools/packaging/mac/sign-and-notarize.sh:167-172`）。
- 通常実行では `SIGN_ID=-` は公証できない ad-hoc identity として拒否される。stderr に `SIGN_ID=- is an ad-hoc signature, which Apple cannot notarise. Add --dry-run to test with it.` を出し、終了コード 2 で終わる。`--dry-run` があればこの拒否分岐を通らない（同 `:174-182`）。
- 通常実行では Keychain の codesigning identity 一覧に値が見つかる必要がある。見つからなければ FAIL 項目 `signing identity` に `"<値>" is not in your Keychain (security find-identity -v -p codesigning lists what is)` を記録して終了コード 1 で終わる（同 `:221-224`, `:123-124`）。
- `--dry-run` は CLI による上書きであり、環境変数の値より優先する。`NOTARY_PROFILE` は別変数であり、dry-run 以外の署名 identity とは独立して扱われる（同 `:47-48`, `:174-182`, `:205-206`）。
- 署名対象（`.app` / `.dmg`、Terminal アーカイブ、`--engine` 指定の engine package）と入力形式は CLI で選ぶ。対象の Mach-O、nested bundle、`.app`、`.dmg` に対する署名ヘルパーがこの identity を使用する（同 `:272-296`, `:298-313`, `:531-534`）。

## 実行時の詳細

値はスクリプトの先頭付近で一度シェル変数に展開され、コマンドライン解析後に `--dry-run` なら `-` に再代入される。以降は環境を読み直さず、実行中に親プロセス側の環境変数を変えても値は反映されない（`tools/packaging/mac/sign-and-notarize.sh:44-49,66-79,174-182`）。

通常実行は署名処理の前に Keychain identity を確認し、失敗なら処理を終了する。通過した identity は `codesign_item` の `codesign --force --sign "$SIGN_ID" --options runtime` と、disk image 用 `codesign_plain` の `codesign --force --sign "$SIGN_ID"` に渡される。identity が `-` の場合は timestamp を `--timestamp=none` にし、それ以外では `--timestamp` を付ける。各署名関数は失敗時に最大 3 回試行し、`codesign_item` は各失敗で `        (attempt N of 3 failed; the timestamp server is sometimes slow)` を出す。3 回失敗した対象は呼び出し元が FAIL として処理を止める（同 `:272-295`, `:302-310`, `:531-534`）。

dry-run では ad-hoc 署名に `--timestamp=none` を指定し、スクリプト内の公証・staple 処理は `DRY=0` の条件により実行しない。通常実行の identity 事前確認が成功しても、後段の署名コマンド自体が失敗すれば FAIL で終了する（同 `:174-182`, `:221-231`, `:275-276`, `:545-550`）。

## ログと測定値

開始時に `identity : <SIGN_ID>` を標準出力と `sign-and-notarize.log` に記録する。通常実行の identity 不一致は前述の FAIL 理由と `RESULT: FAILED. Read the FAIL line above. Full log: ...` を表示し、終了コード 1 になる。`SIGN_ID=-` の通常実行はログ作成前の preflight で拒否されるため、この開始ログには到達しない。dry-run の完了時には `RESULT: DRY RUN finished. Nothing was sent to Apple; these files are ad-hoc signed and are NOT for release.` と表示する（`tools/packaging/mac/sign-and-notarize.sh:108-113,181-182,201-206,221-224`）。

署名コマンドの出力はログへ追記され、失敗時はその末尾 12 行が stderr に出る。コード上に `SIGN_ID` に関する性能測定値はない（同 `:139-147`, `:279-284`, `:291-295`）。

## 根拠

- `tools/packaging/mac/sign-and-notarize.sh:44-49` — 環境値の既定値展開。
- `tools/packaging/mac/sign-and-notarize.sh:167-182` — macOS 条件、dry-run の上書き、`-` の通常実行拒否。
- `tools/packaging/mac/sign-and-notarize.sh:221-231` — Keychain identity 確認と FAIL / dry-run preflight。
- `tools/packaging/mac/sign-and-notarize.sh:272-296` — identity を署名コマンドへ渡す処理と timestamp 分岐。
- `tools/packaging/mac/sign-and-notarize.sh:298-313,531-550` — 署名対象とアプリ処理の呼び出し。
- `tools/packaging/mac/README.md:7-10,32-33` — packaging ツールと override / dry-run の説明（補助資料。動作の根拠はスクリプト）。
