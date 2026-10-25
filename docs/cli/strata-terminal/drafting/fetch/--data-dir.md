# `--data-dir`

調査対象: Strata commit 7dd5cf18e68c639a8773e096c5c79f971ea2a9f5（2026-10-25 時点）。調査対象 checkout は main...origin/main で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | strata-terminal |
| コマンド | strata drafting fetch |
| オプション | --data-dir |
| 別名 | なし |
| 値 | DIR。文字列をそのままパスとして扱う |

## 役割

DFlash2 drafter の取得・pack 先となるモデルデータフォルダーを指定します。完成した pack は DIR/dflash2/qwen3.8-flash-next-dflash2.q8.pack に置かれます。ダウンロード元の一時ファイルも DIR/dflash2/src/ 以下に作られます。

## 使い方

```sh
strata drafting fetch --data-dir /mnt/models
```

## 値と既定値

- 値は必須の単一文字列です。parser は型変換、存在確認、絶対パス確認などを行わず、指定値から Path を作ります。相対パスはプロセスの現在ディレクトリー基準です。~ もホームディレクトリーへ展開されません。
- 省略時、まず --config で読み込んだ JSON の args からデータフォルダーを推定します。--pack の値があればそのパスの2階層上を、なければ --mtp の値の2階層上を使います（--mtp の値の basename が数字の場合は候補にしません）。どちらも導けない場合は Strata の既定フォルダーを解決します。
- 既定フォルダー解決は、Terminal とデスクトップアプリの設定のうち更新日時が新しい方、既存の Documents/Strata モデルフォルダー、インストール先の順に選びます。設定の不一致を同期する際は、古い側の設定ファイルを書き換える場合があります。
- --data-dir "" は空文字列として受理されますが、truthiness 判定により明示指定とは扱われず、省略時と同じ解決に進みます。

## 実行時の動作

--data-dir があれば、その値が --config から推定した場所より優先されます。選ばれたフォルダーから pack の有無を調べ、必要な場合 dflash2/src を作成し、固定 revision のファイルを取得・検査して engine 用 pack を生成します。取得した pack は指定データフォルダー配下に保存されます。既に有効な pack（ファイルサイズが1 MiB超）があれば、そのファイルを再利用します。

--if-needed との相互作用に注意してください。この revision では ENGINE_SERVES_DFLASH2 が False であり、needs_pack() は drafter が実際に使われる場合にだけ true です。そのため --if-needed を付けると、--data-dir に pack がなくても取得をスキップします。--if-needed を付けない通常の fetch は、pack がなければ取得を試みます。

## 適用条件と副作用

- --data-dir 自体によるパス妥当性検証はありません。ディレクトリーは取得時に必要に応じて作成されます。OS がパスを扱えない、または作成・書き込みできない場合は処理に失敗します。
- pack が未準備の場合、明示的な fetch はネットワークアクセスを行います。取得ファイルは repository 内で固定されたサイズと SHA-256 に照合され、不一致の一時ファイルは削除されます。中断時は .part を残し、次回再開に使います。
- 成功後、元の config.json と model.safetensors は削除され、pack のみが残ります。pack 生成に失敗した場合は一時 .tmp を削除します。
- --config が指定されても、JSON 読み込み失敗・不正 JSON はここではエラーにならず空設定として扱われます。その場合、--data-dir がなければ既定フォルダー解決へ進みます。
- 既定値の解決では、Terminal / app 設定同期や Catalog の初期化によるディレクトリー作成が起こり得ます。明示的な --data-dir があれば Catalog 経由の既定フォルダー解決は行いません。

## 出力とエラー

- 成功時は通常、人間向け出力として完成した pack のパスを表示し、終了コード 0 を返します。--output json / jsonl では結果を JSON で出力します。jsonl は取得・pack の進捗を JSON Lines で出します。
- --if-needed によるスキップも終了コード 0 で、通常は Nothing to download.、機械向け出力では skipped: true を返します。
- DraftingError または取得禁止を示す AcquisitionRefused は終了コード 5 です。通常出力では strata: ... を stderr に、機械向け出力では ok: false と drafting_failed を含む JSON を stdout に出します。
- パス作成など OSError は共通 CLI handler で処理され、終了コード 6 になります。parser が値を受け取れない場合（DIR の欠落など）は argparse の usage/error 経路です。

## 根拠

- 索引上の配置とコマンド scope: docs/cli/README.md:339-349（調査対象文書の索引エントリー）。
- parser、既定値への分岐、--config の扱い、--if-needed、成功・失敗出力: strata_cli/drafting_cmd.py:17-29,40-54,57-99。
- コマンド登録と dispatch: strata_cli/cli.py:172-173,2144-2146。
- config の args からのフォルダー推定、pack path と有効判定、現行の serve 対応条件: strata_control/drafting.py:114-122,141-146,179-211。
- pack の作成、取得前の安全ゲート、部分ファイルの再開、hash 検査、pack 後の元ファイル削除: strata_control/drafting_fetch.py:29-39,54-102。
- 既定フォルダー候補と設定ファイル同期: strata_cli/launch/catalog.py:223-251,494-501、strata_control/discovery.py:227-259,262-289。
- 共通 CLI の OSError エラー処理: strata_cli/cli.py:2176-2183。

調査範囲は上記の同一 checkout に含まれるソースです。CLI の help や配布済み Release artifact は別途実行・照合していません。
