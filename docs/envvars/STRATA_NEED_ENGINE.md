# `STRATA_NEED_ENGINE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Control モードのセットアップが、通常の Strata エンジン component を見つけられない場合に、モデルの準備を続けず停止するよう指定する内部の受け渡し用環境変数である。`terminal/setup.py` の `control_engine_step()` が不足を検出した時だけ判定する。`STRATA_NEED_ENGINE=1` かつ `STRATA_ALLOW_NO_ENGINE` が `1` 以外なら、モデルのダウンロード・準備より前に `fail()` を呼ぶ。エンジンが見つかれば値にかかわらず通常どおり進む。(`terminal/setup.py:9373-9399`)

通常の `strata launch` は親プロセスから継承した同名変数を子プロセス環境からいったん削除し、エンジン不足がないときだけ `1` を設定して setup.py を起動する。このため、利用者が親環境に設定した `STRATA_NEED_ENGINE` はそのまま優先されない。一方、runner は通常起動時に継承された `STRATA_ALLOW_NO_ENGINE` を削除しないため、それが `1` なら setup.py の停止条件を抑止する。エンジン不足を検出済みで利用者が続行した場合も同変数を `1` に設定する。(`terminal/strata_cli/launch/runner.py:969-974, 1650-1661`; 不足時の確認と状態記録は `runner.py:1207-1223`)

## 値と判定

セットアップ側は `os.environ.get("STRATA_NEED_ENGINE") == "1"` と完全一致で比較する。文字列を数値・真偽値に変換せず、大文字小文字や前後の空白も正規化しない。さらに `os.environ.get("STRATA_ALLOW_NO_ENGINE") != "1"` を同時に要求する。(`terminal/setup.py:9387-9399`)

| 条件 | `STRATA_NEED_ENGINE` 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Control モードで通常の engine component が見つからない場合 | 不足時の停止条件を満たさず、警告してモデル準備を続ける | `1`（ただし `STRATA_ALLOW_NO_ENGINE` が `1` でないこと） | 空文字、`0`、`true`、`True`、` 1`、`1 `、`01`、その他の文字列 |
| engine component が見つかった場合 | 通常どおりセットアップ | 値は参照結果に影響しない | 値は参照結果に影響しない |
| Shape 専用 engine のセットアップ経路 | この変数による停止判定を通らない | 該当なし | 該当なし |

明示的な空文字は未設定とは異なる環境値だが、比較結果は `"1"` と一致しないため停止条件を有効にしない。`STRATA_ALLOW_NO_ENGINE=1` が同時にある場合は、`STRATA_NEED_ENGINE=1` でも停止しない。`STRATA_ALLOW_NO_ENGINE` の空文字・未設定・`0`・`true` などは `"1"` と異なるため、`STRATA_NEED_ENGINE=1` の停止を抑止しない。(`terminal/setup.py:9389`)

## 有効になる条件

- setup.py が Control モードで動くこと。`CONTROL` は `STRATA_CONTROL_INSTALL == "1"` で決まり、`engine_step()` はこのモードで通常の component engine 経路を `control_engine_step()` に振り分ける。(`terminal/setup.py:97-102, 9513-9520`)
- モデルが Shape 専用 engine 経路ではないこと。`engine_step()` は Shape engine が選ばれると Control の通常 component 経路より先に `shape_engine_step()` へ分岐する。(`terminal/setup.py:9513-9520`)
- `EC.resolve(full=False)` が `EngineMissing` を送出すること。engine が解決されれば環境変数は評価されず、成功表示の後に処理が続く。(`terminal/setup.py:9380-9388`)
- 停止するには値が厳密に `1` であり、かつ `STRATA_ALLOW_NO_ENGINE` が厳密な `1` でないこと。後者が `1` なら「engine なしでモデルを準備する」選択が優先される。(`terminal/setup.py:9389-9399`)
- `strata launch` では、エンジン不足時の確認で続行した場合は runner が `STRATA_ALLOW_NO_ENGINE=1` を設定するため、この変数による停止は行われない。確認を拒否した場合は setup.py を呼ばず、`LaunchError` で止まる。`--yes` または確認 UI がない経路では no-engine 確認は自動続行扱いとなる。(`terminal/strata_cli/launch/runner.py:1207-1223, 1650-1661`)

## 実行時の詳細

この変数を読むのは `control_engine_step()` 内の engine 解決失敗処理だけであり、setup.py のその処理に入った時点で `os.environ` から読み取る。値を関数内 `static` やモジュール変数に保存する実装ではない。runner は setup.py の子プロセスを起動する直前に継承環境を加工し、`STRATA_NEED_ENGINE` を削除してから必要に応じて設定する。親プロセスでの環境変更は runner が作った子プロセス環境の値にはそのまま反映されない。(`terminal/setup.py:9387-9399`; `terminal/strata_cli/launch/runner.py:1650-1661`)

条件が成立すると `fail()` が不足理由（`plain_notice` または `driver_notice`、いずれも無い場合は `no engine is installed for this PC`）と次の案内を表示し、終了コード `1` で停止する。案内は「get the engine that matches this graphics card (`strata update`, or the app's Settings), then run this again; nothing was downloaded and files already downloaded are kept」。runner は setup の出力を読み、終了コードが非ゼロなら `[X]` 行と直後の案内を失敗情報にし、末尾最大 400 行をセットアップログとして保存しようとする。(`terminal/setup.py:9387-9395, 1049-1056`; `terminal/strata_cli/launch/runner.py:1711-1727, 1765-1774`)

停止条件を満たさない場合、セットアップは不足を警告し、`home()/engine` と `component: missing` の仮 metadata を使ってモデルのダウンロード・準備へ進む。これは engine の導入や実行を行うものではなく、コメントにも engine はモデル読み込み時に検索されるとある。(`terminal/setup.py:9396-9400`)

## 根拠

- `terminal/strata_cli/launch/runner.py:969-974` — 子プロセス向け基底環境の作成。
- `terminal/strata_cli/launch/runner.py:1207-1223` — engine 不足の記録、利用者確認、拒否時の終了。
- `terminal/strata_cli/launch/runner.py:1650-1661, 1711-1727, 1765-1774` — setup.py 起動前の設定、失敗処理、出力保存。
- `terminal/setup.py:97-102, 9373-9405, 9513-9520` — Control モード、値判定、不足時の停止または続行、Shape 経路との差。
- `terminal/setup.py:1049-1056` — setup 停止時の出力と終了コード。
