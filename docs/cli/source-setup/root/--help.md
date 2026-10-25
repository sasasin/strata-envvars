# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などからも起動） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`setup.py` の現在の parser が公開するオプション一覧と説明を表示して終了します。標準の Python `argparse.ArgumentParser` が自動で `-h` / `--help` を追加するため、ソースに独立した `add_argument("--help", ...)` 宣言はありません。

## 使い方

Strata checkout のルートで、利用する Python から直接実行します。

```sh
python setup.py --help
```

Linux の `setup.sh --help`、Windows の `START-HERE.bat --help` も引数を `setup.py` に渡します。ただし、これらの wrapper は Python runtime / 仮想環境がない場合にその準備を先に行うため、初回のヘルプ確認には上記の直接呼び出しが適しています。

## 値と既定値

値は取りません。`-h` は同じ parser action の短縮別名です。別の option 値、設定ファイル、環境変数によりヘルプの表示内容を切り替える処理は確認できません。

## 実行時の動作

通常の Windows / Linux 経路では、`main()` が `ArgumentParser` を作成し、オプションを登録して `parse_args()` を呼びます。`--help` / `-h` は argparse の組み込み action として usage と説明を標準出力に表示し、成功終了します。通常の setup 処理へは進みません。

表示されるのは parser の通常のヘルプ対象です。`argparse.SUPPRESS` を指定した引数（画像生成関連の5 option と `--skip-build`）は受理されてもヘルプ出力には表示されません。

## 適用条件と副作用

- macOS で Control mode ではない場合、`setup.py` は独自 parser を作る前に `metal/setup_mac.py` へ引数を渡します。したがって同じ `-h` / `--help` でも表示されるのは Metal setup 固有の parser のヘルプです。Mac の app / Control mode は `setup.py` 側の parser を使います。
- `main()` は parser より前に `private_files.adopt_user_defaults()` を試します。この処理は Windows でプロセス token の既定 owner / ACL を調整し、Windows 以外では何もせず、例外も外へ出しません。
- wrapper 経由ではヘルプ parser に到達する前に runtime を探し、必要に応じて Python や仮想環境を準備します。`UPDATE.bat` / `update.sh` はさらに更新処理を行ってから setup wrapper を呼ぶため、単なるヘルプ表示の入口としては扱えません。

この調査では `--help` を実行していません。出力文言・終了コードは同一 revision の CLI 実行結果ではなく、parser 定義と argparse の組み込み動作に基づく説明です。

## 出力とエラー

正常な help action は usage と公開 option の説明を出力して終了します。未知の引数や型・choices に合わない値は parser の通常の引数エラー経路に入り、`argparse` がエラーと usage を表示します。CLI の help action 自体に Strata 独自の validation、警告、ファイル生成、モデル起動処理はありません。

## 根拠

- `setup.py:8412-8420` — `main()` 冒頭の Windows 向け既定 ACL 調整、macOS 通常経路の委譲、argparse parser の生成。
- `setup.py:8421-8553` — root parser の option 登録と `parse_args()`。`--help` を無効化する指定はなく、非表示 action は `argparse.SUPPRESS` で登録されています。
- `setup.py:8554-8566` — parser 後の validation / 分岐。help action はこの処理より先に終了します。
- `metal/setup_mac.py:326-358` — macOS 側 parser の組み立てと `parse_known_args()`。macOS 通常経路での help scope の根拠です。
- `strata_control/private_files.py:349-380` — `adopt_user_defaults()` は Windows のみ token owner / ACL を調整し、他 OS では何もしません。
- `setup.sh:6-12,68-76` — POSIX wrapper の runtime / venv 準備後の引数委譲。
- `START-HERE.bat:8-12,44-54` — Windows wrapper の runtime 選択と `setup.py` への引数委譲。
- `UPDATE.bat:1-6,19-20`、`update.sh:1-6,16-17` — update wrapper は `setup.py` に渡す前に更新を行います。
- [CLI 索引](../../README.md) — `source-setup` のコマンド階層とこの予定リンク。
