# `MALLOC_ARENA_MAX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの名前の値を数値として読んだり検証したりせず、Linux で Strata が起動する子プロセスの環境に `MALLOC_ARENA_MAX=2` を既定として追加します。環境辞書に同名キーがすでにあれば、その値（空文字を含む）を保持します。serve の engine 用環境では、設定の `env` 項目がこの既定値を後から上書きできます。これは Strata が環境を組み立てる処理であり、外部 allocator が値をどう解釈するかはここでは扱いません。実装は `terminal/strata_control/childenv.py:18-33`、serve の適用箇所は `terminal/serve/server.py:3870-3873,3890-3891` です。

子プロセスを起動せず手動で動かした runtime host と serve server では、起動処理がこのキーの有無を調べ、未設定かつ Linux の場合にだけ `mallopt(-8, 2)` を試します。Strata は `mallopt` の戻り値を呼び出し元へ返すだけで、成功・失敗をログにしません（`terminal/strata_control/childenv.py:24,36-46`）。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux 上で Strata が作る子環境 | `MALLOC_ARENA_MAX` キーがなければ文字列 `"2"` を設定 | Strata 側では値の検証なし。`"2"` を追加し、既存なら既存値をそのまま渡す | Strata 側で無効値判定なし。`""`、`"0"`、`"1"`、`"true"`、`"0anything"` も既存値として保持 |
| Linux 上で手動起動された runtime host / serve server 自身 | キーがなければ `ctypes.CDLL(None).mallopt(-8, 2)` を呼ぶ | 既存値の内容にかかわらず、この処理は呼ばない（`"2"` などを parse しない） | キーが存在すれば空文字を含めて処理を呼ばない。`mallopt` の呼び出し失敗も例外を捕捉して `False` で終わる |
| Linux 以外 | 子環境に既定値を追加せず、自プロセスへの `mallopt` 呼び出しも行わない | 該当なし | 該当なし |

子環境を作る helper は `ARENA_VAR not in target` という辞書キー存在判定だけを行い、値の文字列比較、数値変換、大小文字変換、空白処理、範囲制限はしません。手動起動用 helper も `ARENA_VAR in os.environ` の有無だけを調べます（`terminal/strata_control/childenv.py:27-46`）。

## 有効になる条件

- 既定の `"2"` を子環境へ追加するには `sys.platform.startswith("linux")` であり、その子環境辞書に `MALLOC_ARENA_MAX` キーがないことが必要です（`terminal/strata_control/childenv.py:30-33`）。
- 手動起動プロセス自身に `mallopt` を試すのも Linux かつ `os.environ` にキーがない場合だけです。キーがある場合、値が `"2"` でなくても Strata は変更しません（`terminal/strata_control/childenv.py:36-46`）。
- serve の engine 子環境ではプロフィール設定の `env` が最後に通常の代入で適用されるため、同じキーを設定すると helper が追加した `"2"` や継承値を上書きします。関連する CLI 引数による上書きはこの経路にありません（`terminal/serve/server.py:3870-3873,3890-3891`）。
- GPU backend、モデル状態、server/CLI モードによる条件分岐は helper にありません。runtime host の起動、管理対象 server の起動、server から engine を起動する経路で呼び出されます（`terminal/strata_control/runtime.py:717-720,1054-1066`、`terminal/serve/server.py:3870-3873`）。
- 手動起動時の `mallopt` は `ctypes.CDLL(None)` 上の `mallopt` を呼びます。シンボル解決等で `OSError`、`AttributeError`、`ValueError` が起きた場合は捕捉され、適用されません（`terminal/strata_control/childenv.py:42-46`）。

## 実行時の詳細

管理対象 runtime host を起動する launcher は `os.environ.copy()` に `arena_env` を適用して subprocess に渡します。host は server を起動するときにも環境コピーへ同 helper を適用し、server の `child_env` は engine 起動向けに現在の `os.environ` のコピーへ適用します（`terminal/strata_control/runtime.py:717-720,1047-1066`、`terminal/serve/server.py:3870-3873`）。これらは子プロセスを作る直前に環境辞書へ適用され、helper 内に値を保存する cache はありません。したがって次の子環境作成では、その時点の辞書内容が使われます。

手動起動の runtime host は `runtime.main()` で、手動起動の server は `main` の処理で、それぞれ `limit_own_arenas()` を呼びます（`terminal/strata_control/runtime.py:1650-1658`、`terminal/serve/server.py:8480-8482`）。起動時にキーが存在する場合は何もせず、未設定なら固定引数 `-8, 2` で試します。両呼び出し元は戻り値を使わないため、適用できなかった場合に Strata が終了したり fallback したりする経路はありません。

## ログと測定値

この helper は環境変数の設定、`mallopt` の結果、例外捕捉についてログを出しません。ソース内コメントには l620 の serve soak（120 分、同じ head・engine・schedule）について既定時の server RSS 312 MiB / 増加率 +4.5 %/h、`MALLOC_ARENA_MAX=2` 時の 252 MiB / +0.69 %/h と記載されていますが、これはコメントに記録された測定であり、この調査で再測定・独立検証した値ではありません（`terminal/strata_control/childenv.py:18-21`）。

## 根拠

- `terminal/strata_control/childenv.py:18-46` — 定数、Linux 判定、既存キーの保持、子環境への値追加、手動起動時の `mallopt` と例外処理。
- `terminal/strata_control/runtime.py:717-720` — launcher から runtime host への環境引き渡し。
- `terminal/strata_control/runtime.py:1047-1066` — managed host から server への環境引き渡し。
- `terminal/strata_control/runtime.py:1650-1658` — 手動起動 host の適用時点。
- `terminal/serve/server.py:3870-3891` — engine 環境の組み立てとプロフィール `env` による上書き。
- `terminal/serve/server.py:8480-8482` — 手動起動 server の適用時点。
