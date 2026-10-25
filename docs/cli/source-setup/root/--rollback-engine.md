# `--rollback-engine`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` からも起動） |
| オプション | `--rollback-engine` |
| 別名 | なし |
| 値 | 値なし。`argparse` の `store_true`。省略時 `False`、指定時 `True` |

## 役割

エンジン更新時に `engine/.previous/`（CUDA 13 または HIP）へ退避された直前のエンジンを、現在のエンジンと入れ替えます。入れ替え後の現行エンジンも `.previous/` に保存されるため、同じコマンドをもう一度実行すると元の世代へ戻せます（`setup.py:5063-5083`）。

## 使い方

Strata の checkout ルートで実行します。

```sh
python setup.py --rollback-engine
```

Linux の `./setup.sh --rollback-engine` と Windows の `START-HERE.bat --rollback-engine` も引数を `setup.py` に渡します（`setup.sh:6-12`、`START-HERE.bat:8-12`）。CUDA 12 用エンジンを切り替える場合は次のように明示します。

```sh
python setup.py --cuda 12 --rollback-engine
```

## 値と既定値

このフラグ自体は値を取りません。`--rollback-engine=true` のような値付き指定は parser が受理しません（`setup.py:8499-8500`）。重複指定について個別の検査はなく、`store_true` のままです。

対象ディレクトリは `--cuda 12` の場合 `engine-cuda12/`、それ以外は `engine/` です。`--cuda` は `12`、`13`、`auto` を受け付け、既定値は `STRATA_CUDA` の値（空なら未指定）です。分岐では値が文字列 `12` と一致する場合だけ CUDA 12 ディレクトリを選び、それ以外は通常の `engine/` を選択します（`setup.py:8509-8512`、`setup.py:1601-1603`、`setup.py:8614-8615`）。

## 実行時の動作

通常の parser 経路では、rollback 判定は `--update` の通常処理より前にあります。そのため `--update` と併記しても、rollback 分岐から戻り、同じ起動で通常の更新処理へは進みません（`setup.py:8614-8619`）。

`engine/.previous/` が存在し、空でなければ、処理は次の順でファイルを移動します。

1. `engine/.swap/` を消して作り直します。
2. `.previous/` 内の各ファイル・ディレクトリについて、同名の現行項目があれば `.swap/` に移します。
3. `.previous/` の項目を現行エンジンの場所へ移します。
4. `.swap/` の項目を `.previous/` に移し、`.swap/` を削除します。

したがって、復帰後も前世代が `.previous/` に残り、再実行で往復できます（`setup.py:5071-5083`）。退避世代はエンジンの更新が既存項目を置き換えたときに `install_unpacked` が保存します。最初のインストールでは旧エンジンがないため、rollback 用の保存世代は作られません（`setup.py:5020-5046`、`setup.py:5058-5060`）。

`--backend sycl` を同時に指定した場合は rollback 分岐より前に `sycl/setup_intel.py` へ引数が委譲されます。したがって、この経路で `--rollback-engine` が同じ入れ替え処理を行う根拠は確認できません（`setup.py:8561-8564`、`setup.py:7321-7344`）。

macOS では通常の `setup.py` parser より前に Metal 用 `metal/setup_mac.py` へ引数が委譲されます。`STRATA_CONTROL_INSTALL=1` のアプリ経路でも parser の後、rollback 分岐より前に `mac_control_setup` へ進みます。このため両経路について、ここで説明したローカル engine directory の rollback 動作は確認できません（`setup.py:80-81`、`setup.py:8418-8419`、`setup.py:8561-8564`）。

## 適用条件と副作用

- 指定した toolkit の `.previous/` がディレクトリで、かつ空でないことが必要です。通常エンジンは `engine/`、CUDA 12 エンジンは `engine-cuda12/` を使います（`setup.py:1601-1603`、`setup.py:5066-5068`）。
- rollback はネットワーク取得や engine build を呼ばず、既存ディレクトリ内のファイルを移動します（`setup.py:5063-5083`）。
- rollback 中の `shutil.move` 失敗を捕捉して元の状態へ戻す処理は、この関数にはありません。失敗時は例外経路となり、`.swap/` や一部移動済みの状態が残る可能性があります。更新時の `install_unpacked` には別途復元処理がありますが、その保証は rollback 処理には記載されていません（`setup.py:5031-5046`、`setup.py:5071-5083`）。
- `update.sh` / `UPDATE.bat` 経由では setup 起動前に git clone の `git pull --ff-only` を行い、その後 `--update` を付けて `setup.py` を起動します。rollback 分岐が `--update` より先なので、これらの wrapper で実行した場合、コード更新の後にエンジン rollback が走ります（`update.sh:10-17,62`、`UPDATE.bat:12-20,79`、`setup.py:8614-8619`）。

## 出力とエラー

保存世代がない、または空の場合、`engine_dir(toolkit)/.previous` の場所を含む警告を標準出力に表示して終了コード `1` を返します（`setup.py:5068-5070`、`setup.py:817-822`）。成功時は切替後の engine version と、置き換えた version および保存先を `[ok]` メッセージとして標準出力に表示し、`0` を返します（`setup.py:5074-5083`、`setup.py:817-818`）。

フラグに値を付けるなど parser で拒否される引数は `argparse` のエラーになります。rollback 中のファイル操作エラーについて、専用メッセージや終了コードへの変換は `rollback_engine` 内では確認できません（`setup.py:8499-8500`、`setup.py:5071-5083`）。

## 根拠

- parser 定義: `setup.py:8499-8500`
- `--cuda` の選択肢と既定値: `setup.py:8509-8512`
- 通常フローへの適用と `--update` との順序: `setup.py:8602-8619`
- エンジンディレクトリの選択: `setup.py:1601-1603`
- rollback の入れ替え、失敗時に関する範囲、出力: `setup.py:5063-5083`、`setup.py:817-822`
- rollback 世代の保存: `setup.py:5020-5060`
- wrapper からの引数委譲: `setup.sh:6-12`、`START-HERE.bat:8-12`、`update.sh:10-17,62`、`UPDATE.bat:12-20,79`
- 利用者向け説明（rollback で旧エンジンを戻し、再実行で進める）: `docs/TROUBLESHOOTING.md:106-108`

調査範囲は指定 revision の checkout 内のソースと既存資料です。Release archive や各 OS/backend の実機動作は確認していません。特に macOS と SYCL の委譲先での同フラグの扱いは、この調査では確定できません。
