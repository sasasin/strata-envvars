# `STRATA_NEED_ENGINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata Control モードのセットアップで、モデル準備を始める前に Strata engine component の存在を必須にします。engine が見つからない場合、通常はモデルのダウンロード・準備を続けて警告しますが、この変数が文字列 `1` で、かつ `STRATA_ALLOW_NO_ENGINE` が `1` でなければ、セットアップを終了します。

主な設定元は `strata launch` です。通常の標準モデルのセットアップ子プロセスに `STRATA_NEED_ENGINE=1` を渡し、セットアップ側でも engine component が見つからない場合に、モデルのダウンロードより先に停止させます。Strata engine を使わない DeepSeek-V4.1-Flash や、ランチャーが engine 不在のまま準備を許可した場合は設定しません。

## 値と判定

`setup.py` は `os.environ.get("STRATA_NEED_ENGINE") == "1"` と比較します。数値変換や trim、大文字小文字変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 必須扱いにしない。engine がなければ警告してセットアップを続ける |
| 空文字 | 必須扱いにしない。未設定と同じ経路 |
| `1` | `STRATA_ALLOW_NO_ENGINE` が `1` でなければ、engine 不在時に終了 |
| `01`、`true`、` 1`、`1 `、その他 | 必須扱いにしない。engine 不在時は警告して続ける |

ただし `STRATA_ALLOW_NO_ENGINE=1` の場合は `STRATA_NEED_ENGINE=1` でも終了条件を満たしません。こちらも文字列の完全一致です。空文字や `true` は `1` と同じ扱いにはなりません。

根拠: `setup.py:7751-7763`。

## 有効になる条件

- `setup.py` が Control モードで engine component の確認処理を実行し、`EC.resolve(full=False)` が `EngineMissing` を送出する必要があります。engine が見つかる場合、この変数による停止はありません (`setup.py:7736-7753`)。
- 通常の `strata launch` は、モデル準備が必要な場合に `setup.py` を子プロセスとして起動します。モデルが既に適合する形でインストール済みなら `ensure_model()` はそこで返り、子プロセスもこの判定もありません (`strata_cli/launch/runner.py:1119-1129,1142-1153`)。
- `strata launch` は標準モデルでは子プロセス環境から継承した `STRATA_NEED_ENGINE` を一度削除し、engine 不在を許容する `engine_problem` 状態でない場合に、DeepSeek 以外なら `1` を設定します (`strata_cli/launch/runner.py:1142-1149`)。したがって、呼び出し元がこの変数を別の値にしていても、この経路では上書きされます。
- `engine_problem` がある場合、ランチャーは `STRATA_NEED_ENGINE` を除いたまま `STRATA_ALLOW_NO_ENGINE=1` を子プロセスへ渡し、モデル準備を許します (`strata_cli/launch/runner.py:1145-1148`)。一方、通常の標準モデル経路では `STRATA_ALLOW_NO_ENGINE` を消していません。親環境にこれが既に `1` なら、子プロセスにも残り、セットアップ側の停止を抑制します (`strata_cli/launch/runner.py:674-679,1142-1153` と `setup.py:7753`)。
- DeepSeek-V4.1-Flash は `multi_file()` の場合に Strata engine の取得を省き、`ensure_model()` でも `STRATA_NEED_ENGINE` を設定しません (`strata_cli/launch/runner.py:717-722,1146-1149,1495-1500`)。
- 対象の停止判定は Control モード内の engine component 確認に限られます。通常の `setup.py` は `CONTROL` が有効でなければ別の engine セットアップを行います (`setup.py:77-83,7772-7777,8018-8019`)。macOS は通常セットアップで Metal 用スクリプトへ移り、Control モードでも専用の Mac セットアップへ分岐するため、この `control_engine_step()` の判定を通りません (`setup.py:9062-9069,9220-9223`)。

## 実行時の詳細

この名前を環境から読む実装箇所は `setup.py:7753` の一箇所です。関数呼び出し時に `os.environ.get()` を評価し、値を module-level の定数や cache に保存しません。`strata launch` は `subprocess.Popen(..., env=env)` で、その起動時点の環境辞書をセットアップ子プロセスへ渡します (`strata_cli/launch/runner.py:674-684,1142-1153`)。

`EC.resolve(full=False)` が成功すれば、engine component の確認ログを出して通常の処理へ進みます。`EngineMissing` かつ停止条件成立時には、例外の `plain_notice` または `driver_notice`（どちらもなければ `no engine is installed for this PC`）を `fail()` に渡します。`fail()` は `[X]` 行と案内文 `get the engine that matches this graphics card (...)`、`nothing was downloaded and files already downloaded are kept` を出し、`Setup stopped...` の後に終了コード 1 で止めます。モデルのダウンロード手順は engine step より後です (`setup.py:7751-7759,8018-8031,904-909`)。

停止条件を満たさない場合、仮の `eng` / `meta` を設定し、`no engine is installed for this PC yet (...)` と engine をインストールするよう促す警告を出して続行します (`setup.py:7760-7763`)。ランチャー経由でセットアップが非ゼロ終了した場合、ランチャーは出力中の `[X]` 行を拾い、セットアップ失敗として扱います (`strata_cli/launch/runner.py:1197-1212`)。

## 根拠

- 値判定、`STRATA_ALLOW_NO_ENGINE` との優先関係、停止・警告経路: `setup.py:7736-7769`。
- Control モードの判定と、標準セットアップの engine step: `setup.py:77-83,7772-7777,8018-8031`。
- `strata launch` の子プロセス環境、継承値の削除・設定、起動: `strata_cli/launch/runner.py:674-684,1119-1153`。
- DeepSeek の別経路と `multi_file()` 判定: `strata_cli/launch/runner.py:717-722,1495-1500`。
- macOS の分岐: `setup.py:9062-9069,9220-9223`。
- 起動後に既存モデルが使われてセットアップを省略する条件: `strata_cli/launch/runner.py:1119-1129`。
