# `strata components engines --backend`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | 文字列。parser 上の choices・型変換・必須指定なし |

## 役割

このコマンドでは `--backend` は受理されますが、現行の実装では読み取られません。インストール済みエンジンを一覧し、backend ごとに絞り込む効果はありません。backend ファミリーの指定が役立つのは更新・切替など別コマンドであり、この一覧コマンドの動作には反映されません。

## 使い方

```sh
strata components engines --backend cuda
```

値は任意の文字列で、例の `cuda` 以外も parser で拒否されません。ただし、何を指定しても一覧結果は変わりません。

## 値と既定値

`strata_cli/update_cmd.py:47-50` で共通引数として `default=None` で登録され、値の制約はありません。省略時は `None` です。空文字列も明示的な文字列として parser には渡せます。重複指定時の処理は argparse に委ねられ、通常は最後の指定値が引数に残ります。アプリケーション側で値を検査する処理はありません。

## 実行時の動作

`strata_cli/update_cmd.py:82-83` で `engines` サブコマンドに共通オプション群を登録します。実行時は `strata_cli/cli.py:2145-2147` から `update_cmd.run` に入り、`strata_cli/update_cmd.py:419-425` で `engines` 分岐が選ばれますが、ここでは `a.backend` を参照せず `lib.list_engines(ctx)` を呼びます。そのため `--backend` は一覧の対象選択、順序、表示内容に作用しません。

一覧処理は `strata_control/engine_library.py:152-167` にあり、インストール済みエンジンを読み取り、ファミリー別にまとめてサイズ等を返します。同関数の説明と実装ではファイルの読み取りのみで、変更やダウンロードは行いません。JSON 出力では一覧全体を出力し、人間向け表示では全ファミリーとエンジンを表示します（`strata_cli/update_cmd.py:426-437`）。

## 適用条件と副作用

`--backend` の適用条件はなく、値は無視されます。コマンド自体はインストール済みコンポーネントの一覧を読むだけで、ファイル変更・ダウンロードを行わないと `strata_control/engine_library.py:152-154` に記載されています。サーバー稼働状態の照会に失敗した場合は `strata_control/engine_library.py:155-158` で `serving=False` として一覧処理が続きます。

## 出力とエラー

正常時は終了コード `0` で、人間向けまたは JSON の一覧を出力します（`strata_cli/update_cmd.py:426-438`）。`--backend` の値を理由とする検証エラーはありません。ファイルアクセス等に関する一覧処理の全失敗経路や終了コードは、参照した箇所だけからは特定できないため記載していません。

## 根拠

- `strata_cli/update_cmd.py:47-50` — 共通 parser での `--backend` 登録、既定値、検証の有無。
- `strata_cli/update_cmd.py:82-83` — `engines` コマンドへの共通オプション登録。
- `strata_cli/cli.py:2145-2147` — CLI dispatcher から `update_cmd.run` への委譲。
- `strata_cli/update_cmd.py:419-425` — `engines` 分岐が backend 引数を使わず一覧関数を呼ぶ箇所。
- `strata_cli/update_cmd.py:426-438` — 人間向け・JSON 出力と正常終了。
- `strata_control/engine_library.py:152-167` — インストール済みエンジン一覧の構成と読み取り動作。
