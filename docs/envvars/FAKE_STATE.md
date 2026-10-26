# `FAKE_STATE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この名前は、製品版 Strata engine や Control の設定ではありません。リポジトリ内で確認できる使用箇所は、デスクトップアプリの headless UI flow スクリプト `apps/desktop/scripts/ui-flows.mjs` が生成する fake installer 内だけです。スクリプトの説明も、fake installer と fake engine を使い、実際の engine を起動しない UI フローとしています。

fake installer はこの変数を、シナリオ状態ファイルを置くディレクトリとして使います。したがって、この候補を通常の Strata 利用者向け環境変数として扱う根拠はありません。

## 値と判定

| 状態 | fake installer の処理 |
|---|---|
| 未設定 | `os.environ['FAKE_STATE']` が `KeyError` になり、`STATE` 初期化時に処理が失敗する。 |
| ディレクトリパスが設定済み | その文字列を `pathlib.Path` に渡し、ディレクトリを `parents=True, exist_ok=True` で作成する。絶対パス・相対パスを区別する独自検査や数値変換はない。 |
| 空文字が設定済み | Python の `Path('')` はカレントディレクトリを指すため、そのディレクトリを作成対象にする。 |

設定値の内容確認、範囲制限、既定のパスへの fallback はありません。後続処理では `STATE / 'job.json'` を読み書きし、fake download job の状態を保持します。

## 有効になる条件

この処理が関係するのは `ui-flows.mjs` の headless UI flow がシナリオを実行し、そこから生成された fake installer が呼び出される場合だけです。各シナリオは一時 work directory の下に `fake-state` を割り当て、そのディレクトリを作成します。環境オブジェクトは `...env` を最後に展開するため、シナリオに渡す `env` が `FAKE_STATE` を含めば既定のパスを上書きします。

この変数を読む Strata の通常実行コードは確認できません。よって、engine、GPU backend、通常の CLI/server 起動に与える効果はこの調査からは確認できません。

## 実行時の詳細

シナリオ開始時に、`ui-flows.mjs` は `dirs.state` を `<scenario directory>/fake-state` として定め、他の作業用ディレクトリとともに作成します。その後、`baseEnv` に `FAKE_STATE: dirs.state` を設定します。fake installer のソース文字列は同スクリプト内に埋め込まれており、`STATE` を使って `job.json` を参照します。子プロセスの起動条件やユーザー環境からの上書きは各シナリオと起動経路に依存しますが、少なくともスクリプトの `env` 引数から上書きできる形です。

環境変数未設定時の例外や、状態ディレクトリの作成失敗時のログ・終了処理は、Strata engine の挙動ではなく、この fake installer の実行経路に属します。

## 根拠

- `apps/desktop/scripts/ui-flows.mjs:2-6` — UI flow が fake installer / fake engine を用いるスクリプトであることと起動方法。
- `apps/desktop/scripts/ui-flows.mjs:51-55` — fake installer 内で `FAKE_STATE` を必須参照し、値を `Path` に変換してディレクトリを作る。
- `apps/desktop/scripts/ui-flows.mjs:64-67` — `STATE / 'job.json'` を使う fake job 状態の読み書き。
- `apps/desktop/scripts/ui-flows.mjs:126-134` — シナリオ固有の `fake-state` パス作成と環境変数への設定。`env` の展開位置から上書き可能。

