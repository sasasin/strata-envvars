# `STRATA_ALLOW_NO_ENGINE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

setup が必要な engine component を取得・確認できなかった場合に、モデルの取得と準備を続けるかを制御する。文字列 `"1"` のときだけ続行を許可する。通常の `strata launch` は engine 不在時に事前確認を行い、続行が選ばれた場合、または `--yes` 等で確認を省いた場合に、モデル準備用の子 setup プロセスへこの値を設定する。これにより engine 不在のままモデル設定を保存するが、engine をインストールしたり、そのモデルを起動したりはしない。エンジン不在時の通常起動可否は `runner.py` 側の `engine_problem` によって決まる（`terminal/strata_cli/launch/runner.py:1207-1223, 1650-1661, 3173-3177`）。

setup では、Control install mode の標準 engine 欠落時（`control_engine_step`）と、モデル固有 shape engine の取得失敗時（`shape_engine_fetch`）に読む。ソース checkout の通常 engine ビルド経路では前者の分岐は使われない。`CONTROL` は `STRATA_CONTROL_INSTALL == "1"` で決まる（`terminal/setup.py:97-103, 9513-9520`）。

## 値と判定

値は数値や一般的な真偽値として解析せず、Python の `os.environ.get(...) == "1"` で文字列全体を比較する。空白除去、大文字小文字変換、数値変換はない。したがって unset、空文字、`0`、`true`、`01`、`1 ` は許可にならず、文字列 `1` のみ許可になる。標準 engine の分岐では別途 `STRATA_NEED_ENGINE == "1"` も必要。shape engine の分岐ではこの別条件はなく、取得結果が `None` になったときに直接判定する（`terminal/setup.py:9387-9399, 9417-9422`）。

| setup 経路 | `STRATA_NEED_ENGINE` | `STRATA_ALLOW_NO_ENGINE` | engine がない場合 |
|---|---|---|---|
| Control install の標準 engine | `"1"` | `"1"` | 警告を出してモデル準備を続ける |
| Control install の標準 engine | `"1"` | unset、空文字、または `"1"` 以外 | step 5 より前に失敗終了 |
| Control install の標準 engine | `"1"` 以外 | 任意 | 警告を出してモデル準備を続ける。この分岐では `ALLOW` は停止条件にならない |
| shape engine | 任意 | `"1"` | engine なしで続ける扱いにする |
| shape engine | 任意 | unset、空文字、または `"1"` 以外 | setup を失敗終了する |

該当箇所は `terminal/setup.py:9387-9399, 9417-9422`。CLI 引数や設定ファイルによるこの値の上書きは見つからなかった。

## 有効になる条件

- 標準 engine の分岐では `CONTROL` が真で、`EC.resolve(full=False)` が `EngineMissing` を送出し、さらに `STRATA_NEED_ENGINE` が文字列 `"1"` のとき、`ALLOW` が停止を抑止する。既存 engine が見つかった場合はこの分岐に入らない（`terminal/setup.py:9373-9390, 9513-9520`）。
- shape engine の分岐では `SHAPE_ENGINE["shape"]` が設定されたモデルで `shape_engine.ensure(...)` が engine の実行ファイルを返さず `None` になった場合に判定する。feed にこの PC 向け component がない場合、取得・feed 読み取りに失敗した場合などが `None` になる。使用中の既存 engine があり feed 側の更新に失敗したケースでは既存 engine を返すため、この許可分岐に入らない（`terminal/setup.py:9408-9422, 9486-9504`; `terminal/strata_control/shape_engine.py:349-355, 374-401, 402-410`）。
- OS 固有の値検査や build macro はこの変数自体にない。Control install は Windows/Linux の共通 engine 経路と macOS の `mac_control_setup` で使われ、Intel Control setup も shape engine fetch を呼ぶ場合がある。通常の macOS setup は別経路に振り分けられる（`terminal/setup.py:10934-10940, 11198-11220, 11407-11417`）。
- `strata launch` は engine 確認後にモデル準備 subprocess を起動する。engine 不在を `engine_problem` として記録したときは子環境へ `STRATA_ALLOW_NO_ENGINE="1"` を設定し、そうでないときは `STRATA_NEED_ENGINE="1"` を設定する。`_env()` は親環境を複製し、後者の分岐は既存の `STRATA_ALLOW_NO_ENGINE` を消さないため、呼び出し元が `STRATA_ALLOW_NO_ENGINE=1` を持っている場合は標準 engine の setup 停止条件も抑止される（`terminal/strata_cli/launch/runner.py:969-974, 1650-1661`）。
- engine がなく、launch の対話確認で続行が拒否された場合は子 setup を起動せず、「Stopped. Nothing was downloaded.」で終了する。許可された場合でも engine がないため serving はせず、設定保存後に警告結果を返す（`terminal/strata_cli/launch/runner.py:1207-1223, 3173-3177`）。

## 実行時の詳細

setup の各分岐で必要になった時点に `os.environ.get` を呼び、値を関数間で cache しない。setup 起動後にプロセス環境が変更されない通常の起動では、その時点の環境値が使われる。標準 engine 判定は `control_engine_step`、shape engine 判定は `shape_engine_fetch` で行われる（`terminal/setup.py:9373-9425`）。

標準 engine がない場合、`STRATA_NEED_ENGINE="1"` かつ許可値がないと、step 5 のダウンロード前に `fail` し終了コード 1 となる。許可されると `home()/engine` を仮の engine directory とし、metadata に `component: "missing"` を記録して警告後に処理を戻す。Control install はこの metadata のとき engine family 検査を飛ばし、モデル取得・準備と `component:strata-engine` を参照する設定ファイル作成へ進む。後で engine が利用可能になってからモデルをロードする前提であり、この値が engine 自体を供給するわけではない（`terminal/setup.py:9393-9399, 9840-9857`）。

shape engine がない場合、許可値なら `shape_engine.WORDS["setup_skip"]` の警告を出して `None` を返す。Control install の shape setup は missing component としてモデル処理を続ける。macOS Control setup は `None` を `EngineMissing` にし、共通の警告を出して model download/preparation へ続く。許可値がなければ `fail` により終了コード 1 となる（`terminal/setup.py:9417-9425, 9486-9510, 10994-11009`）。

## ログと測定値

標準 engine を許可値で続行する場合、setup は次の警告を出す（`plain` の内容と `EngineMissing` の文字列表現は環境により変わる）。

```text
{plain} no engine is installed for this PC yet ({e}). The model is downloaded and prepared now; install the engine component for your GPU (the app's Settings, or the Terminal) before loading it
```

許可値がなく、`STRATA_NEED_ENGINE="1"` なら `{plain or "no engine is installed for this PC"}` と「get the engine that matches this graphics card ...」の hint を出して setup を停止する。shape engine は許可値の場合 `no engine for {model} is installed: the model is downloaded and prepared now; set it up again when the engine can be fetched` を警告し、許可値がない場合は `shape_engine.WORDS["setup_failed"]` と `setup_failed_hint` を失敗文として使う（`terminal/setup.py:9387-9399, 9417-9422`; `terminal/strata_control/shape_engine.py:45-63`）。

`docs/DETAILS.md` にこの変数の挙動や測定値を裏付ける記述は見つからなかった。ここに性能測定値はない。

## 根拠

- `terminal/setup.py:97-103` — Control install mode の判定。
- `terminal/setup.py:9373-9399` — 標準 engine の解決、値判定、停止・続行処理。
- `terminal/setup.py:9408-9425` — shape engine 取得結果に対する値判定。
- `terminal/setup.py:9486-9520, 9840-9857, 10934-11009, 11198-11220, 11407-11417` — setup 経路と missing engine の後続処理。
- `terminal/strata_control/shape_engine.py:349-410` — shape engine 取得関数が `None` を返す条件。
- `terminal/strata_cli/launch/runner.py:969-979, 1013-1045, 1167-1184, 1207-1223, 1610-1661, 1711-1733, 3151-3177` — launch の engine 確認、子プロセス環境、続行確認と結果。
