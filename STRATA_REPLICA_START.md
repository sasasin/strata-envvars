# `STRATA_REPLICA_START`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーがデータ並列 replica 用の複数の `StrataEngine` を作る順序を選びます。値が文字列 `serial` と完全一致すると、replica を番号順に一つずつ初期化します。それ以外は replica ごとにスレッドを作って初期化を並行させます。モデルの計算方法やリクエストの割り当て規則を変える設定ではなく、サーバー起動時の engine 初期化の進め方を変える設定です。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | `os.environ.get(..., "")` が空文字を返し、並行初期化 |
| 空文字 | `"serial"` と一致しないため、並行初期化 |
| 値が `serial` と完全一致 | `for i in range(n)` で番号順に初期化 |
| その他の値 | 並行初期化。例: `SERIAL`、`Serial`、`serial `、`1`、`true` |

数値変換、空白除去、大文字小文字の正規化はありません。設定値は `serve/server.py` の Python サーバープロセスで読みます。

## 有効になる条件

`serve/server.py` が Strata engine を起動する際、`serve/replicas.py:gpu_groups()` が2つ以上の GPU グループを返し、`start_replicas()` が呼ばれた場合に限り参照されます。replica 設定がない場合、`replicas` が `false` または1以下の場合、あるいは設定したグループが1つだけの場合は `groups` が空になり、通常の単一 `StrataEngine` 起動経路に入るため、この環境変数は参照されません。

`lazy` 起動では各 `StrataEngine` のコンストラクターがプロセスを起動せずに戻ります。そのため `serial` は wrapper の生成順を直列化しますが、モデルを要求時にロードする順序を直列化するものではありません。非 lazy 起動では各コンストラクターが engine の `READY` を待つため、`serial` は前の replica が ready になってから次を初期化します。並行モードでは各 replica の初期化を別スレッドで進めます。

## 実行時の詳細

値は `start_replicas()` の呼び出しごとに条件式で読み取られます。通常の起動ではこの関数は一度呼ばれるため、起動時の選択です。サーバープロセス内で後から環境を変更しても、既に開始した replica の順序や進行中の起動には影響しません。

直列・並行のどちらでも、各 replica の初期化例外は `errors` に集められます。どれかが失敗した場合は起動済み engine を閉じ、`[strata] replica {i} did not start: {e}` でサーバーを終了させます。直列モードでも失敗時にループを break しないため、残りの replica の初期化を試みてから共通の失敗処理に進みます。

`child_env()` は親の `os.environ` をコピーして engine 子プロセスの環境を作ります。そのためこの変数も子プロセスへ継承されますが、調査対象 HEAD で `STRATA_REPLICA_START` を読む Strata ソースは `serve/server.py:6243` のみです。engine 側でこの値に基づく処理は確認できません。

この変数に関するログ分岐はありません。通常の replica 起動ログは両モードで出ます。`docs/DETAILS.md` には replica の起動順に関する説明を確認できませんでした。

## 根拠

- `serve/server.py:6222-6262`: replica の engine 構築、環境変数の比較、直列/並行起動、失敗処理。
- `serve/server.py:649-674,697-725`: `StrataEngine` の lazy 時の早期 return と、通常起動時の子プロセス起動・`READY` 待ち。
- `serve/server.py:2622-2639`: 親環境をコピーして子プロセス環境を構成。
- `serve/server.py:6417-6426`: GPU group の取得後、group がある場合だけ `start_replicas()` を呼ぶ。
- `serve/replicas.py:42-71`: replica 設定から GPU group を作り、1つ以下の場合は空リストにする。
- `docs/DETAILS.md`: replica 起動順の説明なし（`replica` の記述は別件の replica cache 消去に関するもの）。
