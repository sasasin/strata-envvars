# `HOST_SPEC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの調査開始時の状態は `main...origin/main` で、未コミット変更はありませんでした。

## 役割

`HOST_SPEC` は通常の Strata アプリやエンジンの設定ではありません。インストール済みアプリの起動・終了を検証する `apps/desktop/scripts/installed-flow.mjs` が、Tauri shell を模した Node 子プロセスにホスト起動情報を渡すため、その場で設定するテスト用の環境変数です。リポジトリ内の完全一致参照は同スクリプトの設定箇所と読み取り箇所だけです。

## 値と判定

| 状態 | スクリプト上の扱い |
|---|---|
| 通常の呼び出し | `startHostViaShell()` が `{ command, args, options }` の `spec` を `JSON.stringify()` し、子 Node プロセスの `HOST_SPEC` に設定します。環境変数を外から渡す必要はありません。 |
| 読み取り | 子プロセスの `-e` コードが `JSON.parse(process.env.HOST_SPEC)` で文字列全体を JSON として解析します。値のトリミング、個別フィールドの検証、既定値への fallback はありません。 |
| unset または不正な JSON | `JSON.parse` が例外を投げます。スクリプトにはこの inline 子プロセスの例外を処理するコードがなく、ホスト起動・health check に進めません。 |
| 有効な JSON | `s.command`, `s.args`, `s.options` を `child_process.spawn()` に渡し、起動した PID を標準出力へ出します。 |

通常の経路で渡す JSON はスクリプト自身が組み立てるため、上表の unset・不正値は通常のテスト実行で利用者が設定する値域ではなく、受け渡しが欠けた場合の挙動です。

## 有効になる条件

この変数が読み取られるのは `installed-flow.mjs` の `startHostViaShell()` を実行するときだけです。同関数は検証フロー後半の「擬似 shell を kill したときに host と engine も終了する」ケースから呼び出されます。スクリプト自体は `--install <folder>` を必須とする手動実行用であり、通常のデスクトップ起動経路や Strata engine の実行ファイルには、この名前の読み取り箇所は見つかりませんでした。

## 実行時の詳細

擬似 shell 用の `spec` は、インストール先の Node と host entry、host の作業ディレクトリ、`stdio: 'ignore'`、`windowsHide: true`、および検証用環境（`STRATA_PACKAGED=1`、`STRATA_REAL_ENGINE=1`、`STRATA_NO_ACQUIRE=1` など）を含みます。親スクリプトは `HOST_SPEC` を設定して Node の `-e` コードを起動し、そのコードは JSON を解析して host を spawn します。親は出力された PID を読み、health endpoint を最大 200 回、各 150 ms 間隔で確認します。後続の検証では shell を強制終了し、host と engine の終了を確認して結果を `installed-flow.json` に記録します。

従って `HOST_SPEC` の実際の効果はこの検証用プロセス間受け渡しに限られます。ホストの業務動作を直接設定する値ではなく、JSON 内の `options.env` に入った環境が spawn された host に渡されます。

## 根拠

- `apps/desktop/scripts/installed-flow.mjs:125-137` — 擬似 shell の起動仕様生成、`HOST_SPEC` の設定、`JSON.parse`、host の spawn、PID/health check。
- `apps/desktop/scripts/installed-flow.mjs:265-285` — 擬似 shell の強制終了テストで `startHostViaShell()` を呼び、host と engine の終了を確認。
- `apps/desktop/scripts/installed-flow.mjs:1-23,33-34` — このファイルが installed app 検証スクリプトであることと CLI 起動条件。
- `docs/envvars/000_envvers.md:422` — 候補一覧には `HOST_SPEC` がある。候補名は実アプリ設定を意味せず、本調査ではテスト専用コードでの読み取りのみ確認。
