# `--inspect`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers |
| オプション | `--inspect` |
| 別名 | なし |
| 値 | 1個以上。ソース指定と任意の variant 名を渡す |

## 役割

GGUF ファイルのヘッダーを解析し、テンソルの量子化・サイズ情報と、Strata がその形式を実行できるかの判定を表示します。モデル本体をダウンロードせずにローカルファイル、フォルダー、URL、ModelScope または Hugging Face のリポジトリを確認する用途です（`setup.py:8506-8508`; `tools/strata_inspect.py:1-13`）。

## 使い方

Strata のリポジトリルートで、ソースを1つ指定します。ローカルファイルの例です。

```sh
python3 setup.py --inspect ./models/model-00001-of-00002.gguf
```

リポジトリや複数 variant を含むフォルダーでは、必要なら2つ目の値で variant 名または glob を指定します。

```sh
python3 setup.py --inspect ms:owner/repo 'IQ3_*'
```

この値は `tools/strata_inspect.py` の positional `source` と `variant` に渡されます。`setup.sh` と `START-HERE.bat` は引数を `setup.py` に委譲します（`setup.sh:6-13, 76`; `START-HERE.bat:44-54`）。それらの wrapper は Python 環境の準備を先に行う場合があるため、直接 `setup.py` を実行する場合と副作用が異なることがあります。

## 値と既定値

- `argparse` の `nargs="+"` により、`--inspect` の後には少なくとも1値が必要です。1値目がソース、2値目が任意の variant です（`setup.py:8506-8508`; `tools/strata_inspect.py:150-160`）。
- ソースにはローカルの `.gguf` ファイル、ファイルを含むフォルダー、HTTP(S) URL、`ms:owner/repo`、`hf:owner/repo` を指定できます。variant 名は完全一致に加え、glob による一致も行います（`tools/quantscope.py:95-107`; `tools/strata_inspect.py:152-153, 161-167`）。
- setup parser は受け取った値の先頭2つだけを子プロセスへ渡します。3値以上を指定しても3つ目以降は診断に使われません（`setup.py:8559-8560`）。
- 既定値はありません。値なし、未知の setup option、型や choices の不正は `setup.py` の `argparse` エラーになります（parser 定義 `setup.py:8420-8425, 8506-8508, 8553`）。

## 実行時の動作

1. setup parser が全引数を解析し、`--model` と `--family` の組み合わせ検証を行います。その後、`--source` があれば親プロセスの `STRATA_SOURCE` を設定し、`--inspect` があれば同じ Python interpreter で `tools/strata_inspect.py` を起動して、その終了コードを返します（`setup.py:8553-8560`）。そのため、同時指定した他の setup option は通常の setup に適用されません。`--model` の上記検証と `--source` の環境変数設定だけは inspector 起動前に行われます。
2. inspector は指定ソースから名前が `.gguf` で終わり、`mmproj` を含まないファイルだけを選びます。複数 shard は名前から shard 番号を除いた variant にまとめます（`tools/strata_inspect.py:161-176`; `tools/quantscope.py:110-113`）。
3. 1 variant を選ぶと各 GGUF のメタデータとテンソル一覧を読み、量子化ごとのサイズ・bits/weight を表示します。Strata に同梱する fingerprint 情報と照合し、既知モデル、既知と同じ配置、未テスト、非対応などの判定文を表示します（`tools/strata_inspect.py:177-182`; `tools/quantscope.py:170-197, 308-333`; `tools/strata_inspect.py:95-130`）。複数 variant が候補として残る場合は一覧を表示し、個別 variant の解析はしません（`tools/strata_inspect.py:167-172`）。
4. GGUF の入力処理に使う `quantscope` は、データ本体ではなく先頭からメタデータ・テンソル表を含む範囲を読みます。remote URL はサイズ取得に HEAD を送り、ヘッダー読取時は HTTP Range 要求を使います。hub repository ではファイル一覧 API を読み、GGUF ごとに必要範囲を取得します（`tools/quantscope.py:46-58, 78-103, 128-141, 170-197`）。

## 適用条件と副作用

- `--inspect` 分岐は通常のモデル setup、update、engine build、起動やデータフォルダー処理より前です。この分岐に入れば、それらの通常処理には進みません（`setup.py:8559-8564, 8602-8619`）。
- ただし `setup.py` の `main()` 冒頭では Windows の管理者実行時に、以後このプロセスが作成するファイルの owner と default DACL を現在ユーザー向けに設定しようとします。失敗しても例外は無視されます（`setup.py:8412-8419`; `strata_control/private_files.py:349-388`）。
- この分岐自体は fingerprint を読み取るだけで、出力ファイルへ書き込みません。`--source` も同時指定した場合、親 `setup.py` は `STRATA_SOURCE` を設定しますが、inspector の source 解決は `ms:` / `hf:` prefix、URL、ローカルパスで決まり、`STRATA_SOURCE` は参照しません（`setup.py:8557-8560`; `tools/quantscope.py:34-44, 95-107`）。
- remote を指定するとネットワーク通信が発生します。HTTP 要求は最大5回試行し、各要求の timeout は60秒です（`tools/quantscope.py:46-58, 99-103`）。ローカルフォルダーは再帰検索します（`tools/quantscope.py:104-107`）。
- `setup.py` の通常 parser に入る前に、macOS で `CONTROL` が無効な場合は `metal/setup_mac.py` へ引数が委譲されます。この経路では `setup.py` の `--inspect` parser/分岐を通りません（`setup.py:8418-8420, 7314-7318`; `metal/setup_mac.py:327-328`）。
- `setup.sh` は Python がなければ仮想環境の作成や Python 環境準備を行うことがあります。`START-HERE.bat` も bundled Python または venv 経路を選びます（`setup.sh:7-16, 70-76`; `START-HERE.bat:44-54`）。
- `update.sh` と `UPDATE.bat` は `setup.py` に委譲する前に Git clone で `git pull --ff-only` を試みます。そのため、これらの update wrapper に `--inspect` を渡しても wrapper 側の更新処理は先に起きます。診断だけを行う場合は `setup.py`、`setup.sh` または `START-HERE.bat` を使います（`update.sh:7-17, 62`; `UPDATE.bat:9-20, 79`）。

## 出力とエラー

- 解析成功時はテンソル群ごとの集計と `Strata:` 判定を標準出力に表示します。既知・同一配置・未テストの判定は終了コード `0`、Strata 非対応判定は `2` です（`tools/quantscope.py:308-333`; `tools/strata_inspect.py:177-182`）。
- `.gguf` が見つからない場合、または指定 variant が一致しない場合はメッセージを出して終了コード `1` になります。複数 variant が残るときの一覧表示は終了コード `0` です（`tools/strata_inspect.py:165-174`）。
- 不正な GGUF、通信失敗、JSON/ヘッダー解析失敗などは inspector 内で捕捉されず、Python の例外出力と失敗終了になります（`tools/strata_inspect.py:161-182`; `tools/quantscope.py:46-58, 170-197`）。setup 側の parser エラーは usage とエラーを表示し、`argparse` の終了コード `2` で終了します（`setup.py:8420, 8553`）。

## 根拠

- setup parser、親 parser 後の検証・環境変数設定・子プロセス呼び出し: `setup.py:8420-8425, 8502-8508, 8553-8564`
- inspector の引数、対象ファイル選択、variant 選択、出力・終了コード: `tools/strata_inspect.py:150-182`
- ローカル/remote source 解決、Range 読取、GGUF header parsing、集計出力: `tools/quantscope.py:34-58, 61-107, 128-141, 170-197, 308-333`
- setup の後続処理、Windows の token defaults、macOS 早期委譲: `setup.py:7314-7318, 8412-8420, 8557-8564, 8602-8619`; `strata_control/private_files.py:349-388`; `metal/setup_mac.py:327-328`
- 引数を委譲する wrapper と update wrapper の先行処理: `setup.sh:6-16, 70-76`; `START-HERE.bat:44-54`; `update.sh:7-17, 62`; `UPDATE.bat:9-20, 79`

## 調査範囲

同一 revision の parser とその実行先ソースを確認しました。CLI `--help` の実行、Release 配布物の確認、通信を伴う実行は行っていません。したがって記載はこの checkout のソース実装に基づき、配布済みバイナリでの動作確認は含みません。
