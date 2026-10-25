# `STRATA_NEED_ENGINE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata launch` がモデルを準備するために起動する `setup.py` に渡す内部フラグです。Strata Control の component-install 経路でエンジンが見つからない場合、モデルのダウンロードと準備を始める前にセットアップを失敗させます。通常のセットアップ設定や、エンジンをインストールする指示ではありません。

## 値と判定

`setup.py` は `os.environ.get("STRATA_NEED_ENGINE") == "1"` で判定します。文字列全体が `"1"` の場合だけ有効です。未設定、空文字、`"0"`、`"true"`、`"01"` などは無効です。比較前の trim・数値変換・大文字小文字変換はありません。

エンジン不足の分岐では、さらに `STRATA_ALLOW_NO_ENGINE` が文字列 `"1"` でないことを要求します。したがって両方が `"1"` の場合は `STRATA_NEED_ENGINE` による早期失敗を抑制し、警告を出してモデルの準備を続けます。

## 有効になる条件

- `setup.py` が `STRATA_CONTROL_INSTALL=1` の Control install モードで動き、`control_engine_step()` のエンジン確認に到達すること。このモードはエンジンをビルド・取得せず、既存 component を探します。
- エンジン component が見つからず、`EC.EngineMissing` が発生すること。エンジンが見つかれば、この変数の判定による処理はありません。
- `STRATA_ALLOW_NO_ENGINE` が厳密な文字列 `"1"` でないこと。

`strata launch` の runner は setup 子プロセス用の環境を作る際、継承した `STRATA_NEED_ENGINE` をいったん削除します。その後、runner がエンジン不足を把握していない通常経路では `"1"` を設定します。runner が `engine_problem` を保持している（エンジンがこの PC 向けに存在しないと判定済みの）場合は `"1"` を設定せず、代わりに `STRATA_ALLOW_NO_ENGINE=1` を渡して準備続行を明示します。つまり、呼び出し元のシェルから値を設定しても、この runner 起動では上書きされます。

## 実行時の詳細

runner は `STRATA_CONTROL_INSTALL=1` と `STRATA_INSTALL_DIR` を設定して `setup.py` を起動します。`control_engine_step()` は component を検索し、見つからない場合に `STRATA_NEED_ENGINE=1` かつ `STRATA_ALLOW_NO_ENGINE!=1` なら `fail()` を呼びます。失敗文にはエンジンがない旨と、モデルをダウンロードせず既存のダウンロード済みファイルは保持する旨が含まれます。

早期失敗を抑制した場合は、セットアップが missing-engine warning を出してモデルをダウンロード・準備し、エンジン component は後からモデル読み込み時に必要になります。runner 側では `engine_problem` が残っている場合、モデル設定の保存後に起動へ進まず、警告結果を返します。

この環境変数は runner が生成する子プロセス環境に設定され、setup 起動時に評価されます。`setup.py` 内で環境値をキャッシュするコードはありません。起動後の環境変更が判定に反映される経路ではありません。

## 根拠

- `setup.py:72-78` — `STRATA_CONTROL_INSTALL` による Control install モードの定義。
- `setup.py:7160-7187` — component 検索、厳密な文字列比較、`STRATA_ALLOW_NO_ENGINE` による例外、失敗または警告後の続行。
- `strata_cli/launch/runner.py:510-526` — `engine_problem` の記録、警告とモデルダウンロード続行の確認。
- `strata_cli/launch/runner.py:749-760` — 子の setup 用環境から継承値を除去し、状況に応じて `STRATA_NEED_ENGINE=1` または `STRATA_ALLOW_NO_ENGINE=1` を付与。
- `strata_cli/launch/runner.py:1157-1172` — missing-engine 状態ではモデル準備後に起動せず結果を返す。
