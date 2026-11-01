# `--show-key`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。調査対象 checkout は `main`（`origin/main` と同期）で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--show-key` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は `false` |

## 役割

`strata connect <app>` が人間向け出力に表示するアプリ設定・環境値の API key を、通常のマスク表示から実値に切り替えます。API key を端末やログに露出させるため、必要な場合だけ指定してください。

## 使い方

```sh
strata connect opencode --show-key
```

この例は OpenCode 用の設定を表示します。`--show-key` を付けない人間向け出力では、設定中の key は `key[:10]` に `••••••••` を続けた形でマスクされます。

## 値と既定値

値を取らない `store_true` フラグで、指定時は真、未指定時は偽です。回数による追加効果や値の validation はありません（parser は `strata_cli/launch/cmd.py:156-172`）。

## 実行時の動作

`connect` は key を `--key`、`--key-env` が指定する環境変数、選択した実行中 launch / `--preset` の順に採用し、どれも得られなければ空文字にします（`strata_cli/launch/cmd.py:945-950`）。Harness 設定生成時には空 key がプレースホルダー `strata-local` に置き換わります（`strata_cli/launch/harness.py:22,272-280`）。

`--show-key` は人間向け出力時、生成したファイル本文と環境変数をマスクせず表示します。未指定時は `harness.mask()` で key をマスクします（`strata_cli/launch/cmd.py:951-952,978-991`; `strata_cli/launch/harness.py:323-324`）。このオプションは設定ファイルを読み出したり変更したりせず、表示方法だけを切り替えます。

`--output json` と併用した場合、JSON のファイル本文等は常に `harness.mask()` に通されるため、`--show-key` を指定しても key はマスクされたままです（`strata_cli/launch/cmd.py:953-960`）。トップレベルの `--json` も CLI 本体が `output=json` に変換します（`strata_cli/cli.py:2248-2252`）。また、app 名を省略した場合は app 一覧を返す早期分岐となり、key を表示する処理には進みません（`strata_cli/launch/cmd.py:925-937`）。

## 適用条件と副作用

`--show-key` は `harness` 名を指定した `strata connect` に適用されます。`--write` と併用してもファイル書き込み自体の内容はこのフラグで切り替わりません。書き込みではマスク前の生成結果を使うため、key は設定ファイルに書かれます。既存ファイルはバックアップされ、JSON merge 対象では既存キーを保持しつつ新しい値で更新します（`strata_cli/launch/cmd.py:1011-1028`; `strata_cli/launch/harness.py:276-280,288-311`）。

このフラグ自体はファイル・ネットワーク・プロセスに副作用を起こしません。`--check` と併用する場合は、別途 server へ prompt と tool call を送信しますが、これは `--check` の動作です（`strata_cli/launch/cmd.py:961-977,1002-1010`）。

## 出力とエラー

人間向け出力では key を含む設定値が stdout に現れるため、端末記録やリダイレクト先にも残り得ます。`--output json` ではフラグの有無にかかわらずマスク済み設定を出力します。`--show-key` 固有の validation error や終了コード変更はありません。app 名が登録済み harness に一致しない場合は stderr にエラーを出して終了コード 2 になります（`strata_cli/launch/cmd.py:938-944`）。

## 根拠

- parser とフラグ定義: `strata_cli/launch/cmd.py:156-173`
- 適用する key の選択と human/JSON 出力: `strata_cli/launch/cmd.py:923-960,978-991`
- JSON 出力の mask および key 表示以外の `--check` / `--write` 経路: `strata_cli/launch/cmd.py:961-977,1002-1028`
- harness 用 key、render、mask、ファイル書き込み: `strata_cli/launch/harness.py:22,272-324`
- root parser 登録と `connect` の dispatch: `strata_cli/cli.py:488-490,2153-2155`
- 索引のコマンド階層と予定リンク: `docs/cli/README.md:991-1006`

同一 revision の CLI `--help` は補助実行していません。parser と処理経路をソースで確認しました。
