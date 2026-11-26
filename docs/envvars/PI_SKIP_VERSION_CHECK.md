# `PI_SKIP_VERSION_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata 自身がプロセス環境から読む入力変数ではない。Strata の `strata connect pi` が pi.dev 用のセットアップ情報を生成するとき、環境設定として `PI_SKIP_VERSION_CHECK=1` を固定で出力する。したがって Strata 内のモデル処理、サーバー起動、リクエスト処理を切り替えない。Strata がこの値を受け取った後の pi.dev 側の動作は本調査の対象外である。定義箇所は `terminal/strata_cli/launch/harness.py:302-306`。

候補名の全参照を検索した結果、Strata 所有コードでの参照はこの定義だけだった。`getenv`、`os.environ` 等を通じた `PI_SKIP_VERSION_CHECK` の読み取りは見つからない。

## 値と判定

Strata は値を読み取って判定しない。`pi` ハーネスの環境辞書に文字列 `"1"` を常に設定するため、親プロセス側でこの変数が未設定、空文字、`0`、`true`、その他の値でも、Strata が生成する値は変わらない（`terminal/strata_cli/launch/harness.py:302-306,343-347`）。

| Strata 側の条件 | 入力値の扱い | 出力される値 |
|---|---|---|
| `pi` ハーネスを選ぶ | 未設定・空文字・任意の値を参照しない | `PI_SKIP_VERSION_CHECK=1` |
| `pi` 以外のハーネスを選ぶ | この名前を参照しない | この変数の出力なし |

## 有効になる条件

- `strata connect pi` など、`pi` ハーネスを選んで接続情報を表示すること。ハーネス定義で `env` 関数が固定の辞書を返す（`terminal/strata_cli/launch/harness.py:302-306`）。
- Strata の出力は人間向け表示では `Environment:` の下に、Windows 以外なら `PI_SKIP_VERSION_CHECK=1`、Windows なら `set PI_SKIP_VERSION_CHECK=1` として現れる（`terminal/strata_cli/launch/cmd.py:1128-1133`）。JSON 出力ではレンダリング結果の `env` フィールドに含まれる（`terminal/strata_cli/launch/cmd.py:1082-1086`）。
- `strata connect` の `--write` はレンダリングされたファイルだけを書き込む処理であり、この環境辞書をプロセス環境へ設定する処理ではない（`terminal/strata_cli/launch/cmd.py:1019-1050,1108-1118`）。

## 実行時の詳細

`strata connect` はハーネス名を解決し、`harness.render()` を呼ぶ。`render()` は対象ハーネスの `env` 関数を呼び、その返り値を `env` として結果辞書に載せる。`pi` 用関数は入力環境を調べず、毎回 `{"PI_SKIP_VERSION_CHECK": "1"}` を返す（`terminal/strata_cli/launch/cmd.py:1067-1080`、`terminal/strata_cli/launch/harness.py:302-306,343-347`）。

人間向け出力は環境設定の行を表示し、JSON 出力は `env` オブジェクトとして含める。これらは接続設定の提示であり、Strata が pi.dev を起動したり、この名前を子プロセスへ渡したりする処理ではない（`terminal/strata_cli/launch/cmd.py:1082-1086,1120-1133`）。Strata プロセス内の読み取り時期や cache は該当しない。生成値は CLI の `--url`、`--key`、`--model`、`--context` では変化しない（`terminal/strata_cli/launch/cmd.py:1074-1080`）。

## 根拠

- `terminal/strata_cli/launch/harness.py:302-306` — `pi` ハーネスに環境名と固定値 `"1"` を設定。
- `terminal/strata_cli/launch/harness.py:343-347` — ハーネス環境辞書をレンダリング結果の `env` に格納。
- `terminal/strata_cli/launch/cmd.py:1067-1080` — ハーネス選択からレンダリングまで。
- `terminal/strata_cli/launch/cmd.py:1082-1086` — JSON 応答に `env` を含める。
- `terminal/strata_cli/launch/cmd.py:1128-1133` — 人間向け出力で環境設定行を表示。
- `terminal/strata_cli/launch/cmd.py:1019-1050,1108-1118` — `--write` がファイル一覧を対象にする。

