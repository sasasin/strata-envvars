# `NOTARY_PROFILE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

macOS の配布物を署名・公証する `packaging/mac/sign-and-notarize.sh` が、Apple `notarytool` に渡す Keychain profile 名を指定します。Strata の通常の CLI、サーバー、推論実行はこの変数を読みません。用途はこの配布用シェルスクリプトに限られます。

スクリプト起動時に値を `NOTARY_PROFILE` シェル変数へ設定し、実行モード表示、profile の事前確認、公証 submission、および失敗時の公証ログ取得で使います（`packaging/mac/sign-and-notarize.sh:13-16,44-49,201,216-223,349-371`）。

## 値と判定

| 環境の値 | スクリプト内の値 |
|---|---|
| 未設定 | `strata-notary` |
| 空文字 | `strata-notary` |
| 空でない文字列 | その文字列をそのまま使用 |

代入は Bash の `${NOTARY_PROFILE:-strata-notary}` です。値を数値や真偽値として parse せず、空白の trim、大文字小文字変換、書式検証も行いません。空白だけの値を含め、非空ならそのまま profile 名として渡します。コマンドライン引数による上書き経路はありません（`packaging/mac/sign-and-notarize.sh:47-49,65-80`）。

## 有効になる条件

- macOS 配布物の署名・公証スクリプトを実行したときだけ関係します。通常実行では `xcrun` の存在を確認し、事前確認として `xcrun notarytool history --keychain-profile "$NOTARY_PROFILE"` を実行します（`packaging/mac/sign-and-notarize.sh:173-181,216-223`）。
- `--dry-run` の場合は profile 値の初期化自体は行われますが、profile 表示・事前確認・notarytool による公証は行いません。app、Terminal archive、engine の公証呼び出しは `DRY=0` の分岐内です（`packaging/mac/sign-and-notarize.sh:173-181,201,216-225,529-540,550-559,701-706,763-769`）。
- この変数は macOS の配布処理用です。実装上の profile 妥当性や Keychain 登録内容の検証は Strata が独自に行わず、`notarytool history` の終了結果を事前確認に使います。

## 実行時の詳細

環境値をスクリプト開始時にシェル変数へコピーします。以降、環境変数を再読込する箇所やキャッシュ更新はありません。通常実行では解決後の値を `profile  : ...` と標準出力およびスクリプトログに表示します。続く `notarytool history` の標準出力・標準エラーは `/dev/null` へ捨てられ、コマンド失敗時には `fail` が `notary profile` の失敗として「profile が機能しない、またはインターネット接続がない」旨を報告します（`packaging/mac/sign-and-notarize.sh:201-203,216-223`）。

各公証対象は `xcrun notarytool submit ... --keychain-profile "$NOTARY_PROFILE" --wait --timeout 60m` に渡されます。成功判定は一時出力から読み取った status が `Accepted` かどうかです。それ以外の場合、submission ID が得られていれば同じ profile を使って `notarytool log` を呼び出し、取得ログを表示・保存してから `fail` します（`packaging/mac/sign-and-notarize.sh:349-371,529-540,550-559,683-706,763-769`）。profile 名を引用して引数にしているため、シェルによる単語分割はされません。profile 名の意味や Keychain 検索結果は `notarytool` 側の処理であり、ここでは Strata がその名前を渡すことまでを確認しています。

## 根拠

- 環境変数の説明、既定値の代入: `packaging/mac/sign-and-notarize.sh:13-16,44-49`
- CLI 引数処理に profile 上書きがないこと: `packaging/mac/sign-and-notarize.sh:65-80`
- 通常実行時の表示と事前確認・失敗報告: `packaging/mac/sign-and-notarize.sh:201-225`
- 公証と失敗時ログ取得: `packaging/mac/sign-and-notarize.sh:349-371`
- app / dmg / Terminal archive の公証条件: `packaging/mac/sign-and-notarize.sh:529-559,683-706`
- Mac 用署名・公証手順と環境変数 override の説明: `packaging/mac/README.md:1-10`
