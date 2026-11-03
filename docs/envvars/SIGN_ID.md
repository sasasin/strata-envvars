# `SIGN_ID`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

macOS 配布物の署名に使う identity 文字列を指定します。読み取り箇所は `packaging/mac/sign-and-notarize.sh` だけで、通常の Strata エンジンやサーバーの設定ではありません。スクリプトは `.app` 内や Terminal アーカイブ、DeepSeek engine package 内の Mach-O、`.app` 自体、再構築した DMG の署名コマンドへ値を渡します。スクリプトは macOS 専用で、入力を署名して再配布するパッケージング作業に使います（`packaging/mac/sign-and-notarize.sh:2-7,167-171,267-285,488-549,646-738`）。

## 値と判定

| 入力・条件 | スクリプト内の値と処理 |
| --- | --- |
| `SIGN_ID` が未設定または空文字 | Bash の `${SIGN_ID:-...}` により `Developer ID Application: Niko Veit (79LR4R7RSC)` を使います。 |
| 空でない任意の値 | 文字列を trim や数値変換せず、そのまま選択値として保持します。 |
| `--dry-run` を指定 | 元の環境値にかかわらず `SIGN_ID` を `-` に上書きします。 |
| `--dry-run` なしで値が `-` | ad-hoc 署名は notarise できないとして stderr にエラーを出し、終了コード 2 で終了します。 |

既定値は環境値が空でない場合に限り上書きされます。`--dry-run` は環境値・既定値より優先します。`SIGN_ID` 用の CLI オプションや設定ファイルとの優先順位はありません（`packaging/mac/sign-and-notarize.sh:13-18,47-48,65-80,173-181`）。

## 有効になる条件

- macOS 上で実行する必要があります。`uname -s` が `Darwin` でなければ、SIGN_ID の identity 検査や署名処理より前に stderr へ `This script runs on a Mac (it needs codesign, hdiutil, notarytool).` を出して終了コード 2 で終了します（`packaging/mac/sign-and-notarize.sh:166-171`）。
- 少なくとも app、Terminal archive、engine package のいずれかを入力する必要があります。`--dry-run` は ad-hoc identity を選び Apple への notarisation を省略します。通常実行では `SIGN_ID=-` を拒否します（同:18-21,79-80,173-181）。
- 通常実行では、選択した文字列が `security find-identity -v -p codesigning` の出力に完全な引用文字列として含まれることを事前確認します。見つからない場合は `signing identity` の FAIL を表示し、終了コード 1 で停止します（同:216-226）。
- 起動時にシェル変数へ一度代入し、`--dry-run` の場合は引数処理後に上書きします。その後の環境変更を読み直すコードはありません。署名関数は選択値を `codesign --sign` の引数として渡します（同:47,65-78,173-181,267-285）。

## 実行時の詳細

通常実行では、identity の事前確認後にアプリ内の Mach-O を `codesign --force --sign "$SIGN_ID" --options runtime --timestamp` で署名し、アプリ自体も同じ署名関数に渡します。作り直す DMG は `codesign --force --sign "$SIGN_ID" --timestamp` に渡します。Terminal archive と `--engine` package の中の Mach-O も同じ `codesign_item` / `sign_tree` 経由です（`packaging/mac/sign-and-notarize.sh:267-309,517-520,548-549,623-738`）。

値が `-` の場合、署名関数は timestamp 引数を `--timestamp=none` に切り替えます。この値を通常実行で使うと事前検査で拒否されます。`--dry-run` ではスクリプトが値を `-` に固定し、Apple への送信・notarisation・stapling を省略します（同:18-21,173-181,267-285,529-559,701-706）。

通常実行で identity が Keychain の一覧にない場合、端末には `FAIL signing identity` と理由を出し、最後に `RESULT: FAILED...` を表示して終了コード 1 になります。identity が事前検査を通っても各 `codesign` 呼び出しが失敗する場合、その呼び出しを最大 3 回試し、失敗した対象の `FAIL` とログの場所を表示して停止します（同:86-123,216-226,267-309）。

## 根拠

- `packaging/mac/sign-and-notarize.sh:13-21,47-48` — 環境 override、既定値、dry-run の説明と既定値設定。
- `packaging/mac/sign-and-notarize.sh:65-80,166-181,216-226` — CLI 引数処理、macOS 条件、dry-run 上書き、`-` 拒否、通常実行の identity 検査。
- `packaging/mac/sign-and-notarize.sh:267-309,517-549,623-738` — 選択値を署名コマンドへ渡す実装と各パッケージ経路。
- `packaging/mac/README.md:3-9,21-32` — 対象スクリプトが Mac 配布物の署名・notarisation 用であることと、手動実行の案内。
