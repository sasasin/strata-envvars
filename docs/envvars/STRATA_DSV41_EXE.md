# `STRATA_DSV41_EXE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数動作は対象外です。

## 役割

DeepSeek-V4.1 用の `strata-dsv41` 実行ファイルを指定します。Strata のセットアップ処理と `strata launch` がこの値を読み、指定ファイルが存在すれば同梱 package の探索より優先して使います。環境変数自体を一般のモデル engine に設定する機能ではなく、DeepSeek engine の実行ファイルの場所を Strata 側で選ぶ指定です（`setup.py:8222-8230`, `strata_cli/launch/runner.py:2192-2198`）。

## 値と判定

両方の読み取り箇所で `os.environ.get(...) or ""` の後に `.strip()` を適用します。値は空白を除去した文字列をパスとして扱い、真偽値や数値への変換はありません。大文字小文字は関係しません。

| 環境値 | 判定と結果 |
|---|---|
| 未設定、空文字、空白だけ | 空として扱う。通常の package／engine 隣接ファイル探索へ進む。 |
| 空白除去後にパスが残り、そのパスが通常ファイル | そのパスを選ぶ。セットアップは `Path` を返し、launch は config の `exe` をそのパスに差し替える。実行可能属性や engine の内容・版はこの判定時には検査しない。 |
| 空白除去後にパスが残るが、パスがファイルでない | setup の探索関数は `None` を返し、launch の探索関数も engine 未発見 (`None, True`) を返す。指定値があるため package 探索にはフォールバックしない。 |

根拠: `setup.py:8222-8228`, `strata_cli/launch/runner.py:2192-2198`。

## 有効になる条件

- `setup.py` では DeepSeek engine を扱うセットアップ経路で `dsv41_exe(eng)` が呼ばれます（`setup.py:8615-8629`）。有効な指定があると、そのファイルを engine として採用します。`--dsv41-package` は環境変数より先に評価されず、`dsv41_exe` が `None` を返した場合の取得引数になります（`setup.py:8173-8183,8222-8230,8624-8629`）。非空の不正な環境値では package をインストールしても再度の `dsv41_exe` が引き続き環境値を優先するため、指定 package は最終的な選択を上書きできません。有効な `STRATA_DSV41_EXE` がある場合は `--dsv41-package` の取得経路に入りません。
- `strata launch` では run config の `arch` が `deepseek41` のときだけ差し替えを試みます。他の model では `use_own_dsv41_engine()` が戻り、値は engine 選択に使われません（`strata_cli/launch/runner.py:1438-1448,2149-2157`）。
- launch で指定ファイルが見つかれば、それを使い、起動時自動更新をスキップします。`--dsv41-package` が指定されている場合も自動更新をスキップします（`strata_cli/launch/runner.py:2155-2169,2171-2179`）。
- 指定が空なら setup は `engine-dsv41` package と旧形式の engine 隣接ファイルを探索し、launch は Strata install／model 設定／data folder の package を探索します（`setup.py:8228-8236`, `strata_cli/launch/runner.py:2199-2253`）。この通常探索で見つかった engine は、setup/launch の条件を満たすと feed による更新対象になります。

## 実行時の詳細

値を読むのは setup の `dsv41_exe()` 呼び出し時と launch の `dsv41_engine_found()` 呼び出し時です。結果を保持する static/global cache はこのコードにはありません。setup は engine の有無確認後に必要なら取得処理を行い、再度同じ関数を呼ぶため、各呼び出しで現在の process environment を読み直します（`setup.py:8619-8630`）。launch は config 作成中に `use_own_dsv41_engine()` から探索し、見つけた実行ファイルに config の `exe` を差し替え、該当 package の library directories も config に設定します（`strata_cli/launch/runner.py:1438-1448,2149-2169`）。起動した engine の版や実行結果の検査は、この変数の値判定とは別の後続処理です。

非空の不正パスは通常探索を止めます。setup では engine が未発見のままなら build 指定がない限り package 取得を試み、再探索後も見つからなければ `fail()` で `DeepSeek's engine is not available for this computer yet` を出します。詳細案内は `STRATA_VERBOSE=1` または `--verbose` のときに表示されます（`setup.py:8620-8627,8640-8651`）。指定ファイルが存在しても起動できない場合、この変数を読む箇所では判定されず、後の起動失敗経路が報告します（`strata_cli/launch/runner.py:1826-1833`）。

launch の設定探索では、指定パスが無効なら `(None, True)` が返ります。`use_own_dsv41_engine()` は `found is None` のとき config を変更せず戻るため、既存 config に有効な `exe` が残っていればそれが維持されます。既存 exe がなく DeepSeek engine も見つからない場合、model 準備に進み、setup 側で上記の未発見経路になることがあります（`strata_cli/launch/runner.py:1125-1128,2149-2157,2192-2198`）。launch が setup 子プロセスを起動する環境は親の `os.environ` をコピーしており、この値も削除・上書きされません（`strata_cli/launch/runner.py:675-679,1142-1153`）。

## ログと根拠

有効な engine を launch で選び、選択情報が記録されている場合は `DeepSeek engine: <path> (<理由>).` の engine イベントが出ます。config の以前の `exe` と選択値が異なり、以前の値が非空なら notice に「this install's own engine package」を使う旨が追加されます（`strata_cli/launch/runner.py:2158-2169`）。setup は成功時に `engine: <path>` を表示し、engine が得られない場合は上記の `fail()` 経路を通ります（`setup.py:8640-8652`）。

`docs/DEEPSEEK41.md:92-94` も setup が `strata-dsv41` または `STRATA_DSV41_EXE` を必要とすることを案内しています。候補一覧の完全一致参照は `docs/envvars/000_envvers.md:739`。ソース全体の参照には、上記の実装のほか、コメント／文書、テスト用環境設定があります。テストと文書は実装根拠には使っていません。調査対象 commit での環境読み取りは `setup.py:8225,8629` と `strata_cli/launch/runner.py:2176,2196` です。
