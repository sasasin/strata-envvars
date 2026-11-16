# `--dsv41-package`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--dsv41-package` |
| 別名 | なし |
| 値 | `FILE`（文字列。既定値なし） |

## 役割

この引数は旧 DeepSeek-V4.1 用の引数との互換性のため parser に残っています。値を package として検査・導入する機能はなく、通常は `strata launch` の設定作成前に DeepSeek の提供終了メッセージを返します。`--help` の表示対象にも含まれません（`strata_cli/launch/cmd.py:85`）。

## 使い方

旧呼び出し形式を実行すると、値の内容にかかわらず（空文字列の場合を除く）DeepSeek は提供されていない旨を返します。

```sh
strata launch --dsv41-package /path/to/old-package.tar.gz
```

これは package の導入例ではありません。現行 Strata でこの引数を使って DeepSeek engine を導入することはできません。

## 値と既定値

値は parser 上必須の位置引数 `FILE` ですが、型変換、パス検査、ファイル存在確認は parser では行われません。省略時の値は `None` です。通常の非空値では `settings_from_args()` が属性の truthiness を確認し、DeepSeek 非提供メッセージの `ValueError` を発生させます。繰り返し指定した場合は argparse の通常の `store` 動作で最後の値が残ります（`strata_cli/launch/cmd.py:85,206-219`）。

`--dsv41-package=` のように空文字を明示すると parser は空文字を値として受け取り得ますが、判定は truthiness によるため廃止フラグとして検出されません。その場合、この引数は実質無視され、通常の launch 処理が続きます（同 `:218-219`）。

## 実行時の動作

parser が値を `a.dsv41_package` に格納し、`run_launch()` から呼ばれる `settings_from_args()` が `dsv41_package` を含む廃止済みフラグのいずれかに truthy な値があれば `retired.NOT_OFFERED` を送出します。ここで値は他の処理へ渡されず、ファイルを開いたり package をインストールしたりする経路もありません（`strata_cli/launch/cmd.py:85,217-222,798`）。

エラー文は「Strata no longer offers DeepSeek models. Run `strata launch` to choose one of the Qwen models.」です（`strata_control/retired.py:42-43`）。この例外は `run_launch()` 内で捕捉され、通常出力では `strata: ` を付けて stderr に出力し、終了コード 2 を返します。`--output json` が指定されている場合は stdout に `ok: false` とエラー内容を含む JSON を出力し、同じくコード 2 です（`strata_cli/launch/cmd.py:716-721,963-964`）。

## 適用条件と副作用

- 値が空でなければ、モデル名・選択中 family・preset の内容にかかわらず廃止メッセージで launch が止まります。DeepSeek のモデル名や family を別途検出した場合も同じメッセージになります（`strata_cli/launch/cmd.py:217-222`）。
- `--plan` を併用しても廃止判定は行われます。通常のモデル準備やサーバー起動へは到達しません（同 `:798,851-852`）。
- `--backend` も併用すると、その backend の値が妥当な場合、廃止判定より先に backend 選択を環境変数へ設定します。`--plan` なしでは選択を保存し、`--plan` ありでは保存しません。その後 `--dsv41-package` の判定で失敗します。したがって通常の launch は中止されても backend の保存状態は変更される場合があります。不正な backend 値なら、先にその値のエラーになります（`strata_cli/launch/cmd.py:771-798`）。
- `--preset` が指定されていれば廃止判定より前に preset を読み込みますが、非空の廃止引数で失敗した場合、preset の更新や launch 設定の保存・起動には進みません（同 `:206-219,798`）。
- `--help` にはこの引数が掲載されません。parser 定義自体は維持されているため、保存済みショートカットや古いスクリプトから渡された呼び出しは受理したうえで説明メッセージを返します（`strata_cli/launch/cmd.py:85`、互換目的の記述 `tests/terminal/test_retired_entry_points.py:200-216`）。

## 根拠

- `strata_cli/launch/cmd.py:73-86` — `strata launch` parser と `FILE` 引数の定義。help 表示から抑制。
- `strata_cli/launch/cmd.py:206-222` — 引数値による廃止判定と、モデル/family/preset に対する同じ判定。
- `strata_control/retired.py:42-43` — DeepSeek を要求した場合の利用者向けメッセージ。
- `strata_cli/launch/cmd.py:710-721,771-798,851-852,961-964` — backend 処理の順序、launch 設定処理への到達、失敗時の出力形式と終了コード。
- `tests/terminal/test_retired_entry_points.py:200-216` — 旧フラグを受理して拒否メッセージを返すこと、および help に表示しないことのテスト記述。動作説明の根拠は上記の実装ソース。

調査時の Strata checkout は `main` と `origin/main` が一致し、`git status --short --branch` に未コミット変更はありませんでした。旧 parser を確認した範囲では、現行 Strata が実際に導入する別の DeepSeek package 経路はありません。
