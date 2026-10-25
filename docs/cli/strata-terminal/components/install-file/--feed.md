# `--feed`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | URL またはフォルダーを想定する文字列。parser で型・形式検証はしない |

## 役割

このオプションは `install-file` の parser では受理されますが、このサブコマンドの実行処理は値を参照しません。したがって `--feed` を指定しても、導入元 feed の変更、feed の読み込み、ネットワーク通信には影響しません。`--feed` が効く他の更新経路の説明を、このコマンドへ当てはめないでください。

## 使い方

ローカルにある engine package を導入する構文は次のとおりです。

```sh
strata components install-file ./strata-engine-package.tar.gz
```

このコマンドで `--feed` は省略してください。指定しても処理結果は変わりません。parser 上は `strata components install-file --feed https://example.invalid/feed ./strata-engine-package.tar.gz` のように値を渡せますが、その値は使用されません。

## 値と既定値

parser は `--feed` を値を取る引数として登録し、既定値を `None` にしています。`type`、`choices`、必須指定はなく、URL やフォルダーの形式検証もありません。ヘルプ文は「URL またはフォルダー」としていますが、これは `install-file` 実行時の有効性を保証しません。複数回指定した場合の値は通常の `argparse` の単一値引数として最後の指定になりますが、いずれも実行分岐で参照されません。値を省略すると parser が usage error（終了コード 2）にします。

## 実行時の動作

`install-file` の実行分岐は、信頼鍵を読み込み、稼働中 engine の待機条件を処理した後、位置引数 `file` を `updater.install_engine_file()` に渡して終了します。この分岐に `_feed_source()` の呼び出しはなく、`a.feed` は読み取られません。`STRATA_UPDATE_FEED` や前回記録された feed もこの導入処理には使われません。

代わりに導入関数は指定されたローカル archive を展開し、組み込み鍵または `STRATA_UPDATE_TRUSTED_KEYS` で追加された鍵を使って manifest の署名と全ファイルを検証し、実機との適合性を確認します。その後、stage した engine の test-start と切替を行います。元の archive は削除されません。

## 適用条件と副作用

`--feed` 自体に適用条件や副作用はありません。値は保存も転送もされません。`install-file` 全体としては、`--components-dir` が指定されていればその場所を使い、なければ既定の component folder を使います。指定 archive の読込、component folder 内の staging・状態更新、署名検証、稼働中 engine との競合確認、test-start、成功時の切替が行われます。engine が提供するファイル群を操作するため、`--feed` の無効性と導入処理の副作用は区別してください。

## 出力とエラー

`--feed` の値だけを理由にした検証エラーや警告はありません。通常の成功時は human 出力（既定）または `--output json` / `--json` の JSON が出ます。`--quiet` は one-shot コマンド共通 parser に追加されますが、成功時の出力抑制を制御します。エラー時は `update_cmd.run()` が JSON 指定時に JSON error、その他では `strata: ...` を stderr に出し、例外の終了コードを返します。パッケージ不正・署名不一致・実機不適合などは終了コード 5、切替後の受理失敗は 6、稼働中 engine による拒否は updater の Busy 経路（終了コード 7）です。

## 根拠

- `strata_cli/update_cmd.py:30-39` — `_common()` が `--feed` を `default=None` で登録し、型変換や選択肢を設定していません。
- `strata_cli/update_cmd.py:57-62` — `install-file` が位置引数 `file` と共通 option 群を持ちます。
- `strata_cli/update_cmd.py:90-105` — `a.feed`、環境変数、記憶済み値から source を決める処理。ただし `install-file` 分岐からは呼ばれません。
- `strata_cli/update_cmd.py:174-217` — `install-file` 分岐が `a.feed` を参照せず `install_engine_file()` を呼び、成功出力を行います。
- `strata_cli/update_cmd.py:246-255` — update / feed / signature error の出力形式と終了コード伝播。
- `strata_control/signing.py:194-216,248-259` — 組み込み鍵と `STRATA_UPDATE_TRUSTED_KEYS` の読込、および署名 verifier の登録。
- `strata_control/updater.py:1088-1148` — archive の読込、展開、manifest とファイル検証、適合性・downgrade 確認、ローカル archive を残す処理。
- `strata_control/updater.py:994-1077` — engine の test-start、切替、旧版保持、状態記録、staging の後始末。
- `strata_cli/cli.py:508-515,2217-2236` — one-shot の `--json` / `--quiet` 登録と `--json` から JSON 出力への変換。

調査範囲は上記 checkout のソースです。同一 revision の `--help` は実行していません。parser の help 文にある「URL またはフォルダー」という案内と、`install-file` の実使用箇所を照合した結果、値が使用されないことを確認しました。
