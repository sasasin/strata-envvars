# STRATA_NO_PRESET

調査対象: Strata main の HEAD 011c9e600a93bbc9fd451c563501b5831c32bbca（2026-10-22 時点）。対象は Strata が所有するサーバーおよび調整ツールのソース。外部ライブラリの環境変数動作は対象外。

## 役割

Strata の Python サーバーが起動時に保存済みチューニングを run config に重ねる処理を抑止します。主な用途は自動調整の測定ワーカーで、試行対象の設定に別の保存済みチューニングが上乗せされないようにします。これは保存済みチューニングの作成・保存を無効にする設定ではありません。

## 値と判定

serve/server.py は os.environ.get("STRATA_NO_PRESET") の戻り値を Python の真偽値として判定します。文字列の数値 parse や "1" との比較はありません。

| 環境変数の状態 | 判定 | 動作 |
|---|---|---|
| 未設定 | 偽 | 通常どおり保存済みチューニングの適用を試みる |
| 空文字列 | 偽 | 通常どおり適用を試みる |
| 空でない文字列（例: 0, false, 1, anything） | 真 | 保存済みチューニングの適用をスキップする |

大文字小文字、空白、文字列の内容は検査しません。値を読み取る際にキャッシュする実装はなく、apply_saved_tuning() の呼び出し時に環境を確認します。

## 有効になる条件

サーバー起動処理が設定ファイルを読み込み、--engine strata である場合に限り apply_saved_tuning() が呼び出されます。したがって、この関数経由の効果は「設定ファイルあり、Strata engine」の起動経路に限られます。環境変数を設定しても、他 engine や設定ファイルなしの経路でこの判定は行われません。

自動調整の各試行では、調整ツールが子サーバー用の環境を親プロセス環境から複製した後、STRATA_NO_PRESET を文字列 "1" に上書きして worker として起動します。そのため、調整実行時に親環境で未設定または空文字でも、試行サーバーでは保存済みチューニングの重ね合わせが抑止されます。

## 実行時の詳細

サーバーは run config を読み込んで引数を整えた後、環境変数が空でない場合は config をそのまま返します。この早期 return により、プリセットモジュールの import と overlay() の呼び出し、適用結果や「適用できない理由」の通知は行われません。変数が未設定または空文字なら overlay() を呼び出し、適用可能なアクティブ preset があれば引数・環境設定・リクエスト単位の sampling 設定を config に重ねます。preset store の読み取りに失敗した場合も、サーバーは config のまま起動を続けます。

この設定は起動時の判定を変えます。起動後に Python プロセスの環境が変化しても、すでに済んだ config 処理はやり直されません。Strata engine 自身によるこの環境変数の読み取りは確認できません。

## 根拠

- serve/server.py:7654-7679 — apply_saved_tuning() の環境判定、早期 return、preset overlay、通知、例外時の config 継続。
- serve/server.py:8024-8029 — config 読み込み後、設定ファイルがあり engine が strata の場合に適用関数を呼ぶ。
- strata_control/tune_session.py:469-485 — 親環境の複製後に STRATA_NO_PRESET="1" を設定し、子 worker を起動する。
- strata_control/presets.py:441-482 — overlay が active preset の確認、適用条件の検査、引数・環境・request sampling 設定の上書きを行う。
