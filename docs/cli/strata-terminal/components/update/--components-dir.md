# `strata components update --components-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--components-dir` |
| 別名 | なし |
| 値 | ディレクトリパス（文字列）。parser に型変換・選択肢・パス検証の指定はない |

## 役割

`strata components update` がコンポーネントを検索・更新するルートディレクトリを明示する。インストール済み engine や更新状態を既定のユーザー領域とは別の場所に置く場合に使える。これは `strata components engine` にも同じ綴りのオプションがあるが、当該コマンドの文書は [別項目](../engine/--components-dir.md) を参照。

## 使い方

```sh
# 更新用の component root を明示する
strata components update --components-dir /srv/strata/components

# 同じ root を使って更新内容だけ確認する（feed の確認状態は保存される）
strata components update --components-dir /srv/strata/components --check
```

## 値と既定値

- `argparse` では `default=None` の値付き引数として登録され、`type`、`choices`、必須指定はない。短縮別名もない（`terminal/strata_cli/update_cmd.py:47-56,70-79`）。
- 値が truthy なら `Path(a.components_dir)` が root になる。空文字列を渡した場合はこの条件を満たさず、未指定時と同じ既定値選択に進む。パスの存在確認や正規化はこの処理では行わない（`terminal/strata_cli/update_cmd.py:318`）。
- 省略時は `default_components_dir()` を使う。まず `STRATA_COMPONENTS_DIR` が設定されていれば、その値がユーザー既定値として採用される。なければ Windows は `%LOCALAPPDATA%/Strata/components`（`LOCALAPPDATA` がなければホーム配下）、それ以外は `$XDG_DATA_HOME/strata/components`（未設定なら `~/.local/share/strata/components`）となる（`terminal/strata_cli/update_cmd.py:269-284`、`terminal/strata_control/engine_component.py:179-189`）。この option はそれらの既定値より優先する。
- source checkout にその checkout 自身の `engine-feed` があり、ユーザー既定 root に engine package が見つからず、かつ `STRATA_COMPONENTS_DIR` が設定されていない場合は、未指定時の root を checkout の `engine-feed` に切り替える。明示した `--components-dir` はこの fallback より優先される（`terminal/strata_cli/update_cmd.py:256-284,318`）。

## 実行時の動作

`run()` は選ばれた root を `updater.Context(components=...)` に渡す。通常更新では、この root から feed の記憶済み source を読み、更新処理へ同じ context を渡す。`--feed` がなければ feed 選択では `STRATA_UPDATE_FEED`、root 内に保存された feed source、既定 feed の順に参照される（`terminal/strata_cli/update_cmd.py:142-151,318-325,355-372`）。

root は更新状態と競合制御にも使われる。更新 lock は `<root>/.updates/update.lock` に作られ、state の保存先も root 基準である。engine の staging は `<root>/.s/` 以下、engine の配置先は `<root>/engine/` 以下になる（`terminal/strata_control/updater.py:191-214,255-265,778-789,803-824,1591-1607`）。したがって異なる `--components-dir` を指定すると、既定 root の engine・状態とは別の領域を更新する。

`--check` は選択された root で feed と更新可否を調べるモードだが、完全な read-only ではない。結果を `<root>` の state に `last_check` として保存する（`terminal/strata_cli/update_cmd.py:361-367`、`terminal/strata_control/updater.py:778-789`）。

環境変数 `STRATA_COMPONENTS_DIR` の既定値としての仕様は [環境変数文書](../../../../envvars/STRATA_COMPONENTS_DIR.md) を参照。

## 適用条件と副作用

- `--components-dir` は `strata components update` parser に登録され、`update_cmd.run()` で使われる。`strata components` の他のサブコマンド全般に自動適用される指定ではない（`terminal/strata_cli/update_cmd.py:70-79,307-325`）。
- parser 自身はパスの存在・書き込み権限・内容を検証しない。後続処理が root 配下の directory/file にアクセスするため、利用可能性はその処理時のファイルシステム結果に依存する。個々のアクセス失敗がどのエラー表示・終了コードになるかは一律には定まらず、確認できる範囲を超えて特定しない。
- 通常更新ではダウンロード、展開、engine の切り替え等が選択 root の下で発生し得る。`--check` では feed 以外の component download はしない一方、前述のとおり state を更新する（`terminal/strata_cli/update_cmd.py:361-372`、`terminal/strata_control/updater.py:778-789,803-824,1591-1607`）。

## 出力とエラー

この option 固有の値検証エラーや専用メッセージは parser に定義されていない。更新処理が捕捉した `UpdateError`、feed/signature/acquisition の失敗は human 出力では stderr の `strata: ...`、`--output json` / `jsonl` では JSON error object となり、処理が返す code を終了値にする（`terminal/strata_cli/update_cmd.py:311-316,378-390`）。指定 root へのアクセス障害を含む全例外の表示・終了値は、個別の呼び出し経路を超えて一律には確認できない。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,70-79` — 共通 option の parser 定義、および `components update` parser への登録。
- `terminal/strata_cli/cli.py:160-161,2210-2212` — parser 構築と `strata components update` の `update_cmd.run()` への dispatch。
- `terminal/strata_cli/update_cmd.py:256-284,307-325` — source checkout fallback、環境変数・ユーザー領域を含む省略時選択、明示値の root 化と context への設定。
- `terminal/strata_control/engine_component.py:179-189` — `STRATA_COMPONENTS_DIR` と OS ごとの per-user root の選択。
- `terminal/strata_cli/update_cmd.py:142-151,355-372` — root に紐づく feed source の選択、check/update 経路。
- `terminal/strata_control/updater.py:191-214,255-265,778-789,803-824,1591-1607` — lock/state、check 時の state 保存、stage と engine 配置・切り替え先。
- `terminal/strata_cli/update_cmd.py:311-316,378-390` — 捕捉対象のエラー出力と終了値。
