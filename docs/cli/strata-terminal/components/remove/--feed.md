# `strata components remove --feed`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 文字列を1つ取る。URL・フォルダー名などの形式検証はない。 |

## 役割

`--feed` は `remove` の parser で受理されるが、このコマンドの削除処理では値を使用しない。指定しても更新 feed の選択・読み込み・検証は行われず、削除対象や結果にも影響しない。`remove` はインストール済みエンジンをローカルで削除するコマンドである（parser 共通引数: `terminal/strata_cli/update_cmd.py:47-56,88-91`、削除分岐: `terminal/strata_cli/update_cmd.py:337-338,445-466,492-497`）。

## 使い方

```sh
# 指定したインストール済みエンジンを削除する。--feed の値は処理に使われない
strata components remove 0.1.54 --feed https://example.invalid/strata-feed.json
```

`remove` は位置引数 `engine`（バージョンまたはフォルダー名）を必要とする。`--feed` 自体は任意で、指定しない場合も削除処理は同じである（`terminal/strata_cli/update_cmd.py:88-91`）。

## 値と既定値

- `--feed` は共通 parser で `default=None` の文字列引数として登録され、`type`、`choices`、必須指定は設定されていない。そのため、このコマンドの parser は引数の値を feed URL やフォルダーとして検証しない（`terminal/strata_cli/update_cmd.py:47-49,88-91`）。
- 省略時の値は `None`。空文字列を渡した場合も parser 上は値として受理される。
- 共通定義の help 文には feed の指定先と既定候補（`STRATA_UPDATE_FEED`、前回使用値、プロジェクトの feed）が記されるが、これは `remove` の実行時には適用されない（`terminal/strata_cli/update_cmd.py:48` と `terminal/strata_cli/update_cmd.py:337-338,351-354`）。

## 実行時の動作

`strata components remove` は `update_cmd.run()` に入り、コンポーネント保存先とハードウェア情報から context を作った後、`engines`・`use`・`remove` 用の分岐に進む。この分岐は `_feed_source()`、署名鍵の読み込み、取得許可判定より前に実行される。そのため `--feed` の値も `STRATA_UPDATE_FEED` も削除処理では参照されず、ネットワークアクセスや feed の署名検証は発生しない（`terminal/strata_cli/update_cmd.py:303-321,337-354`）。

削除対象は `engine` と任意の `--family` からインストール済み一覧で特定される。対象が一意に決まると `delete_engine()` が対象フォルダーを一時名へ rename して削除する。`--feed` の値はこの選択にも削除処理にも渡されない（`terminal/strata_cli/update_cmd.py:445-466,492-497`、`terminal/strata_control/engine_library.py:317-344`）。

## 適用条件と副作用

- `--feed` の有無や値による適用条件はない。値が無効な URL でも拒否されず、削除の成否はローカルの対象エンジン状態で決まる（`terminal/strata_cli/update_cmd.py:337-338,445-466`）。
- `--feed` によるネットワーク・ファイル副作用はない。ただし、コマンド自体は対象エンジンのフォルダーを削除し、Qwen エンジンの場合は保存状態の `previous` / `pinned` / 該当する失敗記録を整理して履歴を保存する（`terminal/strata_control/engine_library.py:337-364`）。
- 使用中のエンジン、または実行中のプログラムが使用しているエンジンは削除できない。モデルと設定、他 family のエンジンは削除対象外（`terminal/strata_control/engine_library.py:317-319,328-335`）。

## 出力とエラー

`--feed` の値による独自の出力・エラーはない。削除成功時は人間向け出力に削除バージョンと解放サイズが表示され、`--output json` / `jsonl` では削除結果が JSON で出力される（`terminal/strata_cli/update_cmd.py:492-497`）。

対象が未インストール、曖昧、使用中などの場合、`UpdateError` が人間向けでは stderr、機械向けでは JSON エラーとして出力される。対象不一致・削除禁止は終了コード 2、フォルダー rename に失敗した場合は終了コード 6 で、後者は「何も変更していない」と報告する（`terminal/strata_control/engine_library.py:184-196,331-342`、`terminal/strata_cli/update_cmd.py:307-312,374-378`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,88-91` — `--feed` の共通 parser 登録、既定値、`remove` parser への登録。
- `terminal/strata_cli/update_cmd.py:303-321,337-354` — `remove` が feed 解決・取得経路より先にローカル処理へ分岐する根拠。
- `terminal/strata_cli/update_cmd.py:445-466,492-497` — engine/family による対象選択と `delete_engine()` 呼び出し、成功時出力。
- `terminal/strata_control/engine_library.py:317-364` — 削除拒否条件、rename と削除、状態履歴の更新、rename 失敗経路。
- `docs/cli/README.md:243-255` — `strata components remove` の階層と `--feed` の索引リンク。索引に記載された option が parser にも存在することを確認した。
