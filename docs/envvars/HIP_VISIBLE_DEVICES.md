# `HIP_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU driver がこの名前をどう解釈するかは対象外。

## 役割

Strata の HIP サーバーは `HIP_VISIBLE_DEVICES` をエンジン子プロセスへ引き継ぐか、設定された GPU や自動選択した GPU の値に置き換えます。また、サーバーは値を一部の管理処理（エンジン ordinal と GPU の対応付け、画像 reader の GPU 選択）で読みます。HIP エンジン本体は `--gpu` が指定された場合に既存値を確認し、必要なら CLI 値で上書きします。Strata のコードは環境値を一般的な GPU 可視性リストとして一律に parse していません。

## 値と判定

| 読み取り箇所 | 判定 |
|---|---|
| サーバー `visible_device_order()` | backend が `hip` のとき値全体が ASCII 数字 1～5 桁の項目 1～16 個をカンマ区切りにした形式で、各値が 0～65535 かつ重複なしの場合だけ整数リストを返す。それ以外（unset、空文字、空白、符号、空項目、範囲外、重複など）は空リスト。先頭ゼロは許される。 |
| サーバー `hip_auto_devices()` | `env.get("HIP_VISIBLE_DEVICES")` の真偽だけを見る。unset と空文字は未指定扱いで自動選択を続け得る。空でない文字列は内容を検証せず、自動選択を止める。 |
| サーバー `vision_card_off_igpu()` | `str(value or "")` をカンマで分割し、前後空白を除いて `isdigit()` の項目だけ整数化する。空・非数字項目は捨てる。2 個未満なら選択なし。 |
| HIP エンジンの `--gpu` 前処理 | 値の内容を解釈しない。unset/空文字では上書き警告を出さない。非空なら CLI 引数との完全な文字列一致を比較し、異なれば警告してから CLI 値に置き換える。 |

## 有効になる条件

- サーバーの GPU 設定で全 GPU が Off の場合、子環境に空文字を設定します。HIP backend で `hip_visible(cfg)` が空でなければ、その番号列を設定します。設定の `env` 項目はこの値を後から上書きできます。
- HIP backend で自動 GPU 選択が試されるのは、GPU 指定がなく、全 GPU Off でもなく、`hip_ordinal` が空で、`HIP_VISIBLE_DEVICES` と `ROCR_VISIBLE_DEVICES` の両方が空の場合です。したがって非空の `HIP_VISIBLE_DEVICES` は自動選択を抑止します。空文字は抑止しません。
- 自動選択には設定されたエンジンと同じディレクトリの `strata-device` 実行ファイルが必要です。`--list-devices` の起動が失敗する、timeout する、非ゼロ終了する場合は自動選択せず、元の環境値を保ちます。選択候補がない場合も元の値を保ちます。選択可能カードがないと `SystemExit` で理由を表示します。選択した場合は `[strata] automatic GPU choice: ...` を出し、その番号を `HIP_VISIBLE_DEVICES` に設定します。
- `--gpu LIST` を指定したエンジン起動では、HIP build（`STRATA_USE_HIP` または `STRATA_HIP_GFX906`）が環境名を `HIP_VISIBLE_DEVICES` に切り替え、CLI の `LIST` を設定します。非空の既存値と異なる場合は stderr に `warning: --gpu ... overrides HIP_VISIBLE_DEVICES=... from the environment` を出します。ここでは `--gpu` が環境値に優先します。
- サーバーの ordinal 対応付けは HIP backend でのみこの値を使います。CUDA_DEVICE_ORDER の条件は CUDA 側だけに適用されます。画像 reader は HIP backend で、明示的な `vision.cuda_device` がなく、可視リストに iGPU と独立 GPU の両方が判定できる場合に、環境値を解析して iGPU を避けるカードを選びます。該当しなければ元の環境を渡します。

## 実行時の詳細

サーバーの `child_env()` はサーバープロセス環境のコピーから始め、GPU 設定、設定ファイルの `env`、HIP 自動選択の順で `HIP_VISIBLE_DEVICES` を扱います。起動時に作った環境辞書はエンジン子プロセスに渡されます。画像 reader には `vision_env()` がこの辞書を渡し、必要なときはコピー上の `HIP_VISIBLE_DEVICES` だけを選択した GPU 番号に置き換えます。自動選択はサーバーの子環境を組み立てるときの処理で、リクエストごとの再評価ではありません。

サーバーの `visible_device_order()` は渡された環境辞書を呼び出し時に評価し、厳密な数値リストと判定できない場合は対応付けを空にします。これは server 起動時の topology 情報と replica 状態の組み立てに使われます。`HIP_VISIBLE_DEVICES` 自体を static cache する処理は確認できません。

HIP engine の main は `--gpu` を処理する前に backend macro に応じた環境変数名を選び、既存値を読みます。既存の非空文字列が CLI 引数と異なる場合だけ stderr に警告し、その後 `setenv` / `_putenv_s` で値を設定します。設定は最初の GPU 呼び出しより前に行われます。環境値単独の parse、無効値に対する Strata 独自のエラーや fallback はこの箇所にはありません。

## 根拠

- サーバーが環境をコピーし、GPU設定・config `env`・HIP 自動選択を適用: `serve/server.py:3747-3790`。
- 設定 GPU と `hip_ordinal` の選択: `serve/server.py:3081-3106,3391-3404`。
- 自動選択の抑止条件、`strata-device` 起動、失敗時の戻り、選択ログ: `serve/server.py:3622-3650`。
- 数値リスト検証と ordinal 対応付け: `serve/server.py:933-945,9458`。replica topology での利用: `serve/server.py:7267-7279`。
- 画像 reader 用の読み取り・置換と起動への受け渡し: `serve/server.py:3912-3946,9191-9224`。
- HIP engine で `--gpu` が既存環境値を比較・上書きする処理、backend 条件、警告文字列: `src/program/generate.cpp:2957-2978`。
- `strata-device --list-devices` の番号説明: `src/core/device_main.cpp:32-45`。
