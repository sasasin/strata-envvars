# `--update`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の状態は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata install` |
| オプション | `--update` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`） |

## 役割

既存の Strata source install を更新するため、`setup.py` に `--update` を渡します。モデルを起動せずに Python runtime packages、必要なエンジン更新、インストール済みモデルの設定更新を行う経路です。これは `strata update` / `strata components update` が署名 feed から Engine と Control を更新する処理とは別です（`strata_cli/cli.py:2064-2082`、`setup.py:6682-6709`、`strata_cli/update_cmd.py:1-7`）。

## 使い方

```sh
strata install --update
```

`strata install` の後続引数は `setup.py` に渡されます。たとえば installer の `--build` などを渡す場合は次の形です（`strata_cli/cli.py:190-196,2074-2082`）。

```sh
strata install --update --build
```

## 値と既定値

値は不要です。Terminal parser では `action="store_true"` で、未指定なら false、指定すると true になります。短縮別名はありません（`strata_cli/cli.py:190-196`）。

この値を Terminal CLI が直接検証・補正する処理はありません。`strata install` が installer に渡す最初の引数を `--update` に切り替え、続く引数はそのまま引き渡します（`strata_cli/cli.py:2074-2082`）。installer 側の `setup.py --update` も `store_true` で宣言されています（`setup.py:8493-8499`）。

## 実行時の動作

1. `strata install` は `STRATA_INSTALL_DIR` があればその場所、なければ Terminal CLI の `ROOT` にある `setup.py` を選びます（`strata_cli/cli.py:2064-2069`）。
2. その `setup.py` が存在しなければ更新処理を始めず、stderr に installer がない旨と案内を出して終了コード `5` を返します（`strata_cli/cli.py:2068-2073`、エラー出力は `strata_cli/cli.py:527-532`）。
3. 存在すれば、現在の Python interpreter で installer を起動し、`--update` と後続引数を渡します。作業ディレクトリは installer の親ディレクトリで、installer の終了コードを Terminal CLI がそのまま返します（`strata_cli/cli.py:2074-2082`）。
4. `setup.py` の通常の更新分岐では、インストール済み model config を列挙し、該当 config がなければ「モデル未導入」と案内して終了コード `0` で戻ります。config があれば runtime packages の導入・確認、必要時の engine 更新、各 config の更新、共有 draft vocabulary の更新、Windows の HIP runtime 配置確認を行います。モデルファイル自体は更新処理で触らず、モデルも起動しません（`setup.py:6472-6474,6682-6709`）。

この経路自体は `git pull` を実行しません。`update.sh` は clone の場合に `git pull --ff-only` を行った後 `setup.sh --update` を実行しますが、Terminal CLI の `_install` は `setup.py` を直接呼びます（`update.sh:7-17,62-63`、`strata_cli/cli.py:2074-2082`）。

## 適用条件と副作用

- `setup.py` の配置先は `STRATA_INSTALL_DIR` で変更できます。指定した場所に installer がない場合は上記の終了コード `5` になります（`strata_cli/cli.py:2068-2073`）。
- Terminal bundle（CLI の `ROOT` に `python/` と `VERSION` がある場合）は、子プロセス環境に `STRATA_CONTROL_INSTALL=1` を設定し、未設定時は `STRATA_INSTALL_DIR` を `install_root()` の値にします（`strata_cli/cli.py:2075-2081`、`strata_cli/launch/catalog.py:184-193`）。Control mode の通常の model setup は pip package・engine をインストールせずコンパイルもしません（`setup.py:74-81`）。ただし非 macOS の `--update` 分岐では `update_install()` が別途 `update_installed_engine()` を呼ぶため、engine 更新処理も対象になります（`setup.py:6693-6697`）。その platform-specific な実行結果は実行検証していません。
- macOS の Control mode では、setup.py は通常の `a.update` 分岐より前に `mac_control_setup(a)` に進みます。その関数はモデルのダウンロード・準備と run config の書き込みを行い、`a.update` による専用更新分岐は通りません（`setup.py:8418-8420,8561-8562,8617-8619,8236-8241,8313-8339,8381-8405`）。したがってこの環境で `--update` が通常の `update_install` と同じ意味になるとは確認できません。
- 通常更新では packages の導入、engine の取得または再コンパイル、model config の書き換えが起こり得ます（`setup.py:6682-6704`）。更新対象 engine が実行中で置換できない場合は警告して既存 engine を保持します（`setup.py:5289-5296`）。
- `update_install` が対象 config を見つけない場合は変更を行わず終了コード `0` です（`setup.py:6688-6692`）。更新処理中の失敗は installer が出力するエラーに依存し、Terminal CLI は子プロセスの終了コードを返します（`setup.py:825-830`、`strata_cli/cli.py:2081-2082`）。

## 出力とエラー

`setup.py` の標準出力・標準エラーは子プロセスから呼び出し元へ引き継がれます。installer 不在時は Terminal CLI が stderr に `strata: ...` を出し、終了コード `5` を返します（`strata_cli/cli.py:2068-2073,527-532`）。`setup.py` の `fail()` はメッセージを出して終了コード `1` で停止し、正常な更新分岐は完了メッセージを表示して `0` を返します（`setup.py:825-830,6705-6709`）。

## 関連文書

- [`strata install` の索引項目](../../README.md#strata-install-install) — 同コマンドのオプション一覧。
- [`source-setup` の `--update`](../../source-setup/root/--update.md) — setup.py 自身の `--update`。Terminal CLI の転送フラグとは別の tool ID・parser scope。
- 署名 feed を扱う別コマンドの parser・処理は、調査対象リポジトリの `strata_cli/update_cmd.py:1-7,43-55` を参照してください。

## 根拠と調査範囲

- 索引ではこの項目を `strata install` 配下に配置しています（`docs/cli/README.md:375-380`）。同じ `--update` が `source-setup/root` にもありますが、tool ID と parser が異なるため別文書です（`docs/cli/README.md:1508-1516`）。
- Terminal parser、引数転送、installer の選択は `strata_cli/cli.py:190-196,2064-2082` を確認しました。installer の parser、更新分岐、更新処理は `setup.py:8412-8420,8493-8499,8553-8563,8617-8619,6682-6709` を確認しました。
- `update.sh` / `UPDATE.bat` は更新前に git pull を行う wrapper ですが、本オプションの Terminal 経路は wrapper を経由しません（`update.sh:7-17,62-63`、`UPDATE.bat:9-20,79`）。
- 同一 revision の CLI `--help` は実行していません。parser と呼び出し先のソースで動作を確認しました。OS ごとの実行結果やネットワーク・package manager の実際の成否、未記載の外部依存内部動作は実行検証していません。
