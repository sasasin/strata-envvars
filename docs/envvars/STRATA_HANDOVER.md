# `STRATA_HANDOVER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の Strata 作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

この変数は、Terminal 起動時の Control hand-over を抑止し、また updater が新しい Control を検証起動するときに旧 updater 向けの拒否処理を避けるために使われます。通常の CLI で `STRATA_HANDOVER` が非空なら、より新しい Control がインストール済みでも現在の Control がそのままコマンドを処理します。updater は staged Control の `--version` 起動にこの値を設定します。

## 値と判定

数値や真偽文字列への変換はありません。Python の `environ.get(...)` の戻り値を truthiness で判定します。

| 値 | `maybe_hand_over` / `refuse_old_updater` での扱い |
|---|---|
| 未設定 | 偽。通常の hand-over 判定へ進む。旧 updater 検出の条件次第では拒否処理へ進む |
| 空文字 `""` | 偽。未設定と同じ扱い |
| 非空文字列（例: `"1"`, `"0"`, `"false"`, 空白） | 真。`maybe_hand_over` は直ちに現在の Control を続行し、`refuse_old_updater` は拒否処理を行わない |

大文字小文字、文字列全体、数値としての妥当性は判定されません。`"0"` や `"false"` も非空なので有効です。読み取り結果を static 変数等に cache するコードはなく、起動入口から呼ばれる関数内で環境 mapping を参照します。

## 有効になる条件

- `strata.py` を通常の `__main__` として起動すると、`refuse_old_updater()` の後に `maybe_hand_over()` が呼ばれます。どちらも `os.environ` を参照し、値が非空ならそれぞれの処理を抑止します。
- 通常の `maybe_hand_over()` は `STRATA_NO_HANDOVER` も truthy なら同じく抑止されます。さらに source checkout からの起動では、`STRATA_HANDOVER_IN_CHECKOUT` が truthy でない限り installed Control への hand-over を試しません。従って対象変数が未設定でも、これらの条件や新しい Control がない場合は hand-over しません。
- updater の `_control_version()` は staged Control を `--version` で試験起動する際、`ctx.environ` の他の値を引き継いだ環境に `STRATA_HANDOVER="1"` を上書きして渡します。この試験起動では `STRATA_NO_ACQUIRE="1"` も設定されます。これにより新 Control の起動時 hand-over が止まり、旧 updater 向けの staged 起動拒否も行われません。
- 環境変数の判定自体に OS/backend/build 条件はありません。実際に hand-over する場合の起動方法は OS で異なり、非 Windows では `execve` でプロセスを置き換え、Windows では `subprocess.call` の終了コードを返します。

## 実行時の詳細

`strata.py` は `strata_cli.cli` などの重い import より前に helper を呼びます。`maybe_hand_over()` は最初に `STRATA_HANDOVER` または `STRATA_NO_HANDOVER` が truthy かを確認し、該当すれば `None` を返します。呼び出し元は `None` の場合に preflight と通常 CLI を続けます。値が偽なら、active Control pointer とその Control の version・必要ファイルを確認し、実行中より新しく、かつ完全な Control があるときだけ同じ argv を渡して起動します。

子 Control の環境を作る `_child_env()` も `STRATA_HANDOVER="1"` を設定します。これにより、子側の起動で再度 hand-over するループを防ぎます。非 Windows で新 Control を起動できない場合は stderr に `strata: could not start the updated Control ...; running ... instead.` を出し、旧 Control を続行します。Windows でも起動失敗時に同じ形式の警告を出して旧 Control を続行し、`KeyboardInterrupt` なら終了コード 130 を返します。壊れた pointer/target の理由が得られた場合も警告を出して現在の Control を続行します。対象変数が truthy のときは hand-over 判定そのものを早期終了するため、これらの警告経路には入りません。

旧 updater の staged `--version` 起動については、`refuse_old_updater()` が argv が `--version` のみ、`STRATA_NO_ACQUIRE` が文字列 `"1"`、`STRATA_HANDOVER` が falsy、かつ実行ツリーの親フォルダー名が `.s` という条件をすべて確認します。条件が揃うと stdout に `This Terminal cannot switch to the new Control by itself. Run the Strata install command once more to update it.` を出して終了コード 7 を返します。updater の現行 `_control_version()` は対象変数を `"1"` に設定するため、この拒否条件を回避し、通常の `--version` 結果を検査できます。各試験起動は 240 秒、失敗・timeout・応答なし後の再試行は 360 秒で、updater 側は失敗時に再試行メッセージまたは `TestStartFailed` を扱います。

## 根拠

- 候補一覧: `000_envvers.md:884`。
- 環境名の定義、子環境への設定、truthiness 判定、checkout 条件、新 Control 起動・警告: `strata_cli/handover.py:22-24,117-163`。
- 旧 updater の staged 起動判定、stdout 文言、終了コード: `strata_cli/handover.py:166-187`。
- 起動入口と helper の呼び出し順: `strata.py:30-42`。
- updater が staged Control に `STRATA_HANDOVER="1"` と `STRATA_NO_ACQUIRE="1"` を設定する箇所、および試験結果の確認と失敗処理: `strata_control/updater.py:1303-1324,1337-1360`。
