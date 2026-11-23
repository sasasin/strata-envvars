# `strata components install-file --feed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 文字列。parser 上は URL やディレクトリとしての形式検証がない |

## 役割

`--feed` は `install-file` でも引数として受理されますが、このコマンドの処理では値を参照しません。インストール対象は位置引数 `file` で渡すローカルのエンジンアーカイブであり、feed を使った取得・照会は行われません。

## 使い方

```sh
strata components install-file ./engine-package.zip --feed https://feed.example/strata-feed.json
```

上の例では `--feed` の値は無視されます。指定するアーカイブ自体が有効な Strata エンジンパッケージである必要があります。

## 値と既定値

`--feed` は共通 parser で `default=None` の文字列引数として登録され、`choices`、`type`、必須指定は設定されていません（`terminal/strata_cli/update_cmd.py:47-56,92-94`）。したがって parser は値の URL・ディレクトリ形式を検証しません。

ただし `install-file` の実行分岐では `a.feed` を読みません。値を省略しても明示しても、このコマンドのパッケージ選択や検証先は変わりません（`terminal/strata_cli/update_cmd.py:341-350`）。

## 実行時の動作

`--feed` は `strata components install-file` 用 parser に登録されています（`terminal/strata_cli/update_cmd.py:92-94`）。一方、通常の feed ベースの更新では `run()` が `_feed_source(a, root)` を呼び、その関数は明示値、`STRATA_UPDATE_FEED`、保存済み source、既定 feed の順に選びます（`terminal/strata_cli/update_cmd.py:142-152,351-354`）。`install-file` はこの共通処理より前に分岐し、署名鍵を読み込んでから位置引数のファイルを `updater.install_engine_file()` に渡します（`terminal/strata_cli/update_cmd.py:341-350`）。このため、`--feed`、`STRATA_UPDATE_FEED`、保存済み feed のいずれも同コマンドの入力には使われません。

ローカルファイルは展開後、組み込みの信頼鍵で署名と全ファイルを検証し、この PC に適合するか確認されます。適合すれば通常のテスト起動・切り替え処理へ進み、元のアーカイブはその場所に残されます（`terminal/strata_control/updater.py:1638-1641,1659-1695`）。

## 適用条件と副作用

この無視動作は `components_command == "install-file"` の分岐で適用されます。feed を参照しないオフライン経路であり、`--feed` の値によるネットワークアクセスはありません（`terminal/strata_cli/update_cmd.py:341-350`; `terminal/strata_control/updater.py:1638-1641`）。アーカイブの展開・検証・導入そのものは行われ、コンポーネント保存先やハードウェア適合判定などは別の共通引数・状態に依存します（`terminal/strata_cli/update_cmd.py:314-320`; `terminal/strata_control/updater.py:1646-1682`）。

## 出力とエラー

`--feed` の値に対する警告や feed 関連エラーは、このコマンド分岐にはありません。成功時は人向け出力または JSON/JSONL 用の機械可読出力を返します（`terminal/strata_cli/update_cmd.py:305-306,345-350`）。入力ファイルがない、拡張子が対応しない、アーカイブを読めない、マニフェストが不正、署名・ファイル検証に失敗、または PC に適合しない場合は `UpdateError` として失敗し、テキスト出力では標準エラーに `strata:` を付けて表示します。これらのエラーは feed 値ではなく、指定ファイルや導入条件に関するものです（`terminal/strata_control/updater.py:1630-1635,1642-1645,1652-1672,1680-1682`; `terminal/strata_cli/update_cmd.py:307-312,374-378`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,92-94` — 共通引数としての `--feed` 登録と、`install-file` parser への適用。
- `terminal/strata_cli/update_cmd.py:142-152,341-354` — feed 解決関数と、`install-file` 分岐がそれを通らずファイル導入へ進む処理。
- `terminal/strata_control/updater.py:1630-1695` — 対応アーカイブ形式、ローカル導入、署名・全ファイル検証、適合判定、導入処理。
- `docs/cli/README.md:177-188` — `strata components install-file` のコマンド階層と `--feed` の索引登録。
