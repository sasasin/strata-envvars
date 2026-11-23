# `strata complete`（Strata Terminal CLI）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata complete` |
| POSIX の入口 | `terminal/bin/strata` |
| Windows の入口 | `terminal/bin/strata.cmd`（PowerShell スクリプトからは `terminal/bin/strata-direct.ps1`） |
| 主な実装 | `terminal/strata_cli/cli.py`、`terminal/strata_cli/completion.py` |

## 役割

シェルの補完設定に使うスクリプトを生成し、標準出力へ表示するコマンドです。実行中の `strata` CLI が持つ argparse のコマンド階層、サブコマンド、オプションと固定選択肢を読み取り、bash・zsh・fish 向けの形式に変換します。補完スクリプトのインストールや設定ファイルへの保存は行わないため、利用者が出力を適切なシェル設定から読み込むか、設定ファイルへ保存します。

## 基本的な使い方

```sh
# --shell を省略した場合。bash 用スクリプトを端末に表示する
strata complete

# zsh 用スクリプトを表示する
strata complete --shell zsh

# fish 用スクリプトを表示する
strata complete --shell fish
```

出力を設定ファイルへ保存する場合は、各シェルの設定場所に合わせてリダイレクト先を選びます。保存しただけでは現在のシェルに有効になりません。読み込み方法や設定ファイルの場所はシェルごとに異なるため、このコマンドはそれらを自動選択しません。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| bash（既定） | `strata complete` / `strata complete --shell bash` | bash の `complete -F` 関数を含むスクリプトを標準出力へ出す |
| zsh | `strata complete --shell zsh` | bash 補完関数を zsh の bash-completion 層で使うスクリプトを標準出力へ出す |
| fish | `strata complete --shell fish` | fish の `complete` 定義を標準出力へ出す |

## 主な動作

`strata` の parser に `complete` サブコマンドが登録され、`--shell` は `bash`、`zsh`、`fish` のいずれかを受け付けます。省略時は `bash` です。実行時には同じ CLI parser を補完生成器へ渡し、選択されたシェル用スクリプトを生成して stdout に書き込み、終了コード 0 を返します（`terminal/strata_cli/cli.py:536-538`、`terminal/strata_cli/cli.py:2231-2234`）。

生成器は parser の各階層をたどり、サブコマンド名と説明、長いオプション、固定 `choices` の値を取り出します。bash では現在のサブコマンド階層に応じて候補を組み立て、直前の引数が選択肢を持つオプションの場合にその選択値を候補にします。fish ではサブコマンドと長いオプションを登録し、固定選択肢を持つオプションには候補値を付けます。zsh は bash 補完関数を利用する形です（`terminal/strata_cli/completion.py:23-38`、`terminal/strata_cli/completion.py:52-85`、`terminal/strata_cli/completion.py:88-118`）。

コマンド自体はスクリプトを stdout に出す処理で、補完定義のファイル保存やインストールはしません。一方、zsh 用スクリプトには `bashcompinit`、`compinit -u` の呼び出しが含まれます。これは生成物をシェルで読み込んだときに実行されます（`terminal/strata_cli/completion.py:88-95`）。

## 出力と失敗

正常時は生成したスクリプトを stdout に出し、終了コード 0 です。`--shell` に `bash`、`zsh`、`fish` 以外を指定すると parser の選択肢検査で拒否され、生成処理へ進みません。parser エラーは `_StrataParser.error()` から argparse の標準処理へ渡されます（`terminal/strata_cli/cli.py:40-51,536-538`）。CLI の入口へ到達する前に Python が見つからない、または `strata.py` が見つからない場合、POSIX / Windows wrapper は stderr に診断を出して終了コード 5 で終了します（`terminal/bin/strata:90-114`、`terminal/bin/strata.cmd:14,50-52`、`terminal/bin/strata-direct.ps1:13-15,49-53`）。

## 関連状態・他の実行経路

補完候補は、スクリプトを生成した checkout / インストールに含まれる parser の文法を反映します。異なる版の `strata` で生成したスクリプトを使う場合、そのスクリプトに記録された候補と実際に実行する CLI の文法が一致する保証は、ここで確認したソースからは判断できません。

`strata.py` の入口では、コマンド分岐より先に更新済み Control への引き継ぎ判定、Windows ランチャーの修復処理、RAM budget の一度限りの移行処理も試みます（`terminal/strata.py:35-63`）。これらは `complete` 固有ではない共通起動処理です。本調査では各 helper の条件と変更内容までは追っていません。

さらに通常の CLI 起動処理では、parser を作る前に `quiet_crash_env()` を呼び、未設定時に当該プロセスの `GGML_NO_BACKTRACE` を設定します。また Windows では `adopt_user_defaults()` がプロセストークンの既定 owner / DACL を調整しようとします。後者はファイル保存ではなく、失敗しても例外を外へ出さない実装です（`terminal/strata_cli/cli.py:2314-2325`、`terminal/strata_control/childenv.py:58-64`、`terminal/strata_control/private_files.py:349-390`）。

## オプションの調査・文書

このコマンドの `--shell` の値と挙動は [CLI 索引の `strata complete` 節](../../README.md#strata-complete-complete) から個別文書を参照してください。

## 根拠

- `terminal/strata_cli/cli.py:62-66` — ルート parser と必須サブコマンドの登録。
- `terminal/strata_cli/cli.py:536-538` — `complete` と `--shell` の parser 定義、選択可能な値と既定値。
- `terminal/strata_cli/cli.py:2231-2234` — 生成器の呼び出し、標準出力への出力、正常終了。
- `terminal/strata_cli/completion.py:23-38` — parser からサブコマンド、オプション、固定選択肢を抽出。
- `terminal/strata_cli/completion.py:52-85` — bash スクリプトの構成。
- `terminal/strata_cli/completion.py:88-118` — zsh / fish スクリプトの構成。
- `terminal/strata.py:35-63` — CLI へ入る前の共通起動処理。
- `terminal/strata_control/childenv.py:58-64`、`terminal/strata_control/private_files.py:349-390` — 起動時の環境変数と Windows のトークン既定値処理。
- `terminal/bin/strata:90-114,147`、`terminal/bin/strata.cmd:1-14,42-52`、`terminal/bin/strata-direct.ps1:1-15,49-59` — POSIX / Windows の wrapper が Python の `strata.py` に引数を渡す経路と、起動条件を満たさない場合の終了経路。

本調査では `strata complete` を実行して生成物やシェル上の補完動作を検証していません。補完生成器のソースと parser 定義を確認した範囲の記述です。
