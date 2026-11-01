# `STRATA_ALLOW_NO_ENGINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

モデル準備用の setup が Strata engine を見つけられないとき、`strata launch` がモデル準備を続けるために使います。この変数は engine を取得したり、実行可能にしたりするものではありません。setup が engine 不在で停止する条件を解除し、警告を出してモデルのダウンロード・準備へ進ませます。

実際の読み取りは `setup.py` の `control_engine_step()` 内、`engine_component.resolve(full=False)` が `EngineMissing` を送出した場合に限られます。通常の `strata launch` は engine の確認・更新をモデル準備より先に行い、engine が使えない場合に確認を経て子 setup を起動します（`strata_cli/launch/runner.py:718-748,826-842,2286-2297`）。

## 値と判定

setup は `os.environ.get("STRATA_ALLOW_NO_ENGINE") != "1"` を文字列全体で比較します。`"1"` だけが停止を抑止し、数値変換、空白除去、大文字小文字変換はありません。

| `STRATA_NEED_ENGINE` | `STRATA_ALLOW_NO_ENGINE` | EngineMissing 時の setup の処理 |
|---|---|---|
| 文字列 `"1"` | 文字列 `"1"` | 停止条件に入らず、警告後に続行 |
| 文字列 `"1"` | 未設定、空文字、その他の値 | `fail()` を呼び、終了コード 1 で停止 |
| 未設定、空文字、その他の値 | 任意 | この停止条件に入らず、警告後に続行 |

したがって、この変数単独で「engine 不在を許可」するわけではありません。判定は setup が `EngineMissing` を処理する時点で `os.environ` から行われ、static cache や設定ファイルへの保存はありません。CLI 引数による上書きはありません。根拠: `setup.py:7751-7763`。

## 有効になる条件

- `setup.py` が Control install モードで動作し、engine 解決処理が `control_engine_step()` に到達する必要があります。Control モードは `STRATA_CONTROL_INSTALL == "1"` で決まります（`setup.py:77-88,7736-7745,7772-7776`）。
- macOS の Control setup は `main()` から `mac_control_setup()` に分岐し、別の engine 不在処理を使います。この変数を読む `control_engine_step()` の判定は通りません（`setup.py:9068-9069,9220-9223`; macOS 側の engine 処理: `setup.py:8860-8864,8910-8925`）。
- engine 解決が成功した場合、この変数は参照されません。`EngineMissing` 以外の失敗もこの判定の対象ではありません（`setup.py:7741-7753`）。
- 停止を解除するには `STRATA_NEED_ENGINE` と `STRATA_ALLOW_NO_ENGINE` の両方が厳密に文字列 `"1"` である必要があります。`STRATA_NEED_ENGINE` が `"1"` でない場合は、この変数の値にかかわらず該当の停止条件は成立しません（`setup.py:7753`）。
- `strata launch` は親プロセス環境をコピーして子環境を作ります。launch 内で `engine_problem` が設定されている場合は子環境の `STRATA_ALLOW_NO_ENGINE` を `"1"` に設定し、`STRATA_NEED_ENGINE` は削除します。engine 問題がなく、DeepSeek の複数ファイル経路でもない場合は `STRATA_NEED_ENGINE="1"` を設定します。親環境から継承した `STRATA_ALLOW_NO_ENGINE` は明示的には削除されないため、engine 解決の不一致などで setup 側が `EngineMissing` になれば、その継承値も判定に使われます（`strata_cli/launch/runner.py:674-679,1142-1153`）。
- `strata launch` の DeepSeek 複数ファイル経路は Strata engine を使わず、runner はこの engine 必須判定を設定しません（`strata_cli/launch/runner.py:718-722,1145-1149`）。

## 実行時の詳細

engine 不在で、`STRATA_NEED_ENGINE="1"` かつ `STRATA_ALLOW_NO_ENGINE` が `"1"` でなければ、setup は `fail()` に理由と案内を渡します。出力には `[X]` のエラー、`nothing was downloaded and files already downloaded are kept` の案内、`Setup stopped...` が含まれ、プロセスは終了コード 1 で終了します。runner は子 setup の出力を読み、非ゼロ終了を `setup_failure()` に渡して launch の失敗として返します（`setup.py:904-909,7753-7759`; `strata_cli/launch/runner.py:1197-1212`）。

続行する場合、setup は `home() / "engine"` を仮の engine パスとして扱い、`component: missing` の metadata を作ります。stderr ではなく setup の標準出力に `[!] no engine is installed for this PC yet (...)` の警告を出し、「モデルを準備し、読み込み前に engine component をインストールする」よう案内します。Control モードの run config は engine 名 `component:strata-engine` を記録します（`setup.py:7751-7769,6643-6645`）。

ただし、`strata launch` 自体は setup 続行後に設定ファイルを作成しても serving を開始しません。`engine_problem` が残っていると final warning を出し、`serving=False` の結果で終了します（`strata_cli/launch/runner.py:2294-2309`）。つまり、この環境変数が許可するのはモデルの準備までです。

## 根拠

- 環境変数の読み取りと `EngineMissing` 時の分岐、警告・fallback: `setup.py:7736-7763`。
- Control install の判定と engine component 名の run config: `setup.py:77-88,6643-6645`。
- `strata launch` の子プロセス環境の生成と両変数の設定: `strata_cli/launch/runner.py:674-679,1142-1153`。
- engine 確認、確認応答、engine 問題後の未起動終了: `strata_cli/launch/runner.py:718-748,826-842,2286-2309`。
- setup 失敗の出力・終了と runner の非ゼロ終了処理: `setup.py:904-909`; `strata_cli/launch/runner.py:1197-1212`。
