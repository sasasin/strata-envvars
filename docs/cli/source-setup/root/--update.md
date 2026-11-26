# `--update`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` 経由） |
| オプション | `--update` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`argparse` の `store_true`）。省略時 `False` |

## 役割

モデルを起動せず、既存インストールを通常起動前と同様に更新する。git clone では最初に Strata のコードを取得し、続いて必要な Python パッケージ、古い／ソース変更済みのエンジン、各モデルの設定形式、draft token subset を更新する。モデル本体の重みファイルはこの経路では更新しない。`--build` と併用すると、通常の更新条件にかかわらず既存エンジンを現 checkout のソースから再コンパイルする（下記「相互作用」参照）。

## 使い方

```sh
# Linux: checkout 内で実行。モデルは起動せずに更新する
./setup.sh --update

# Windows: checkout 内で実行
START-HERE.bat --update

# 現在の Strata ソースからエンジンも再コンパイルする
./setup.sh --update --build
```

`setup.sh` は引数を `terminal/setup.py` に渡す。Windows の `START-HERE.bat` も同ファイルを Python で起動し、`UPDATE.bat` はこれを `--update` 付きで呼び出す。`strata install --update` は別の `strata-terminal` CLI スコープなので、この文書の対象外。

## 値と既定値

値は指定しない。parser は `action="store_true"` として登録し、指定時に `a.update` が真となる。`--update=true` のような値形式や重複指定の個別動作は定義されていない（重複指定を別の意味に解釈する処理もない）。通常の `argparse` により未知の引数や不正な引数形式は usage とエラーになる。

## 実行時の動作

1. `setup.py` は `--update` を parse した後、git clone なら `git pull -q --ff-only` を行う。pull に失敗した場合、git の出力を表示する。履歴が書き換わった旧 clone の特例では、追跡対象ファイルに変更がなければ旧 commit をバックアップ branch に残して `origin/main` へ移る。追跡対象のローカル変更があれば何も移動せず、終了コード 1 で止まる。detached HEAD や git 不在もエラー経路となる。
2. pull で HEAD が変わった場合、新しい `terminal/setup.py` を同じ引数で起動し、環境変数 `STRATA_UPDATE_PULLED=1` で二度目の pull を抑止する。変更がない場合は現在のプロセスが続行する。git clone でないソース配布物では自動取得できない旨と最新版のダウンロード案内を表示し、現在のコピーでインストール更新を続ける。
3. インストール済みモデルがなければ案内を表示して終了コード 0 で終わる。ある場合は（Control モードを除き）実行環境の runtime packages を `.venv` に導入する（同じ依存一覧が導入済みならスキップ。Control モードはアプリ同梱 package の有無を確認する）。その後、通常は必要なときだけエンジンを更新し、各モデル設定を現行形式へ移行し、通常のモデルでは共有 draft subset を更新する。Windows の HIP 設定ではエンジンの HIP runtime も配置する。
4. この処理はモデルを起動しない。エンジン更新に失敗した場合も、利用可能な既存エンジンを保って警告を出し、更新処理自体は完了扱いとなる場合がある。

## 相互作用

- `--build`: `--update --build` は再コンパイルを強制する。通常の `--update` では、ローカルビルド済みエンジンはソース fingerprint や binary の古さを確認し、ready-made エンジンは最低必要バージョン未満の場合に更新する。
- `--rollback-engine`: rollback 分岐は `--update` のインストール更新分岐より先に評価される。ただし git clone であれば、その前に `--update` の pull 処理が行われる。
- Apple Silicon の通常の setup 呼び出しは `metal/setup_mac.py` に委譲される。その parser の `--update` は索引上の別 scope `source-setup/mac/--update.md` が対象であり、本書は `terminal/setup.py` の root scope を扱う。Strata Control 実行時は pull を行わない。

## 適用条件と副作用

- 対象にモデル設定が存在すると、Python package 環境、エンジンファイル、モデルの run config、共有 draft subset などを変更し得る。通常のモデル重みは更新対象外。
- git clone ではネットワークアクセスを伴う git pull が行われる。依存やエンジンの取得も必要に応じてネットワークを使う。既存エンジンが実行中・ロック中なら更新を見送り、モデルを閉じて再実行する案内を表示する。
- `--build` を併用した場合は GPU 検出とソースビルドを伴う。ビルド失敗時は警告して既存エンジンを維持する経路がある。
- 通常の macOS setup は Metal 用 parser へ委譲される。Windows/Linux の wrapper は必要な場合に Python 仮想環境を作成してから parser を起動する。Control モードではコードの pull は行わず、package はアプリ同梱のものを確認する。

## 出力とエラー

- git clone で git が見つからない、detached HEAD、通常の pull 失敗、追跡対象ローカル変更により旧履歴へ移行できない場合は、案内を表示して非 0 で終了する。pull 失敗時は git の stdout/stderr を表示する。
- インストール済みモデルがない場合は setup の案内を表示して `0` を返す。
- エンジンが実行中・取得不能・再コンパイル不能などの場合、警告を表示して既存エンジンで続行する経路がある。更新後も必要最低バージョンに届かない場合、その旨を警告する。
- 最終的な終了コードは `main()` の戻り値をプロセス終了コードとして返す。メッセージは `say()` 経由で stdout に出力される。

## 根拠

- `terminal/setup.py:11530-11532` — `--update` の parser 定義、値を取らない action、help の説明。
- `terminal/setup.py:11606-11613` — parse 後に update pull を先に処理し、戻り値があればそこで終了する分岐。
- `terminal/setup.py:8386-8423` — git clone 判定、CONTROL/PULLED の抑止、detached HEAD・pull 失敗・変更なし・変更後の新 setup 再実行。
- `terminal/setup.py:8330-8365` — fast-forward pull 失敗後の旧履歴移行条件と、tracked local changes を検出した際の停止。
- `terminal/setup.py:8497-8530` — インストール済みモデルの有無、runtime packages、engine/config/draft 更新、非起動、警告後の終了。
- `terminal/setup.py:4310-4317`, `4349-4372` — 導入対象 package 群と、既導入時のスキップ・`.venv` への pip install。
- `terminal/setup.py:8273-8295`, `9135-9158` — run config の必要な移行時の書き込みと draft subset の更新。
- `terminal/setup.py:6452-6551` — エンジン更新条件、再ビルド指定、実行中・更新失敗時の既存エンジン維持。
- `terminal/setup.py:11692-11697` — `--rollback-engine` と `--update` の分岐順。
- `terminal/setup.py:11436-11437`, `9290-9294` — 通常の macOS setup を Metal 用 setup へ委譲。
- `terminal/setup.py:997-999`, `12565-12571` — stdout 出力と戻り値をプロセス終了コードにする処理。
- `setup.sh:6-17`, `81`; `START-HERE.bat:8-17`, `49-65`; `UPDATE.bat:1-7` — POSIX/Windows wrapper から `setup.py` への引数転送。
