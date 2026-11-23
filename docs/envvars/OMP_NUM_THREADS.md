# `OMP_NUM_THREADS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の serve 起動処理は、engine の子プロセス向け環境を作る際に、親プロセスの `OMP_NUM_THREADS` を保持します。さらに CPU worker 数が設定され、環境にこのキーがまだ無い場合は、その数を `OMP_NUM_THREADS` に設定します。Strata の Python コードはこの変数の値を数値として解釈せず、OpenMP runtime のスレッド数を直接制御するコードもありません。したがって、Strata が行うのは serve から engine への値の引き継ぎ・補完までです（`terminal/serve/server.py:3870-3896`）。

この処理は `--engine strata` の serve 起動経路、および serve が replica・split engine 等を作る経路で `child_env` を使う場合に適用されます。変数自体の値による Strata の計算内容・生成結果の変更は確認できません（`terminal/serve/server.py:8304-8308`, `8313-8336`, `8383-8403`, `8870-8878`）。

## 値と判定

Strata は親環境を `dict(os.environ)` にコピーし、その後設定プロファイルの `env` をキー・値とも文字列化して上書きします。`OMP_NUM_THREADS` の処理では値の変換・数値妥当性検査をせず、子環境にキーが存在するかだけを確認します（`terminal/serve/server.py:3873`, `3890-3896`）。

| 条件 | unset | 明示値の扱い | 補完される値 |
|---|---|---|---|
| serve が `child_env` を作成 | 親環境と設定 `env` のどちらにもキーがなければ未設定 | `""`, `"0"`, `"1"`, `"true"`, `"false"`, `"0anything"` など、キーがあれば値をそのまま保持。空白・大文字小文字・数値としての妥当性も Strata は検査しない | `_configured_pool_workers` が正の整数を返す場合のみ、その整数の十進文字列表現 |

設定 `env` に同名キーがあれば親環境の値を上書きし、その値が空文字でも後段の自動補完を抑止します。設定 `env` にキーがなければ親環境から継承した値が優先されます。どちらにもキーがない場合、`--pool-workers N` または `--threads N` の引数（正の整数）、それらがなければ `cfg["threads"]` の正の `int`（`bool` は除外）が補完値の候補になります。引数からは各フラグの最後の出現を後ろから探します。`--pool-workers` が `--threads` より先に評価され、該当フラグの値が不正または非正ならそのフラグの探索を打ち切って次のフラグへ進みます（`terminal/serve/server.py:3682-3704`, `3890-3896`）。

## 有効になる条件

- Serve の `child_env` が呼ばれる実行経路でのみ、この補完処理が行われます。server 自身が `OMP_NUM_THREADS` を読み取ってスレッド数を変える処理はありません（`terminal/serve/server.py:3870-3896`）。
- 自動設定には、親環境にも設定プロファイルの `env` にも `OMP_NUM_THREADS` キーがなく、かつ `_configured_pool_workers(cfg)` が正の整数を得ることが必要です。既存キーがあればその内容が優先されます（`terminal/serve/server.py:3890-3896`）。
- `--pool-workers` / `--threads` が見つからず、または有効な正整数でなく、`cfg["threads"]` も正の整数でなければ、自動設定しません（`terminal/serve/server.py:3691-3704`）。
- engine 起動時には作成済み環境を `env=` として渡します。engine 起動時の `OSError` は `StrataEngine` の起動失敗経路へ進みますが、`OMP_NUM_THREADS` 固有の警告・エラー処理はありません（`terminal/serve/server.py:827-834`）。
- OS・backend・build macro による `OMP_NUM_THREADS` 固有の Strata 側分岐は見つかりません。外部 OpenMP/BLAS runtime が受け取った値をどう扱うかは調査範囲外です。

## 実行時の詳細

`child_env` は呼び出しごとに親の `os.environ` のコピーを作り、プロファイルの `env` を反映した後、worker 数を必要に応じて補完します。固定値の cache はありません。これは server の起動・engine 子プロセスの起動時に行われるため、起動後に親プロセスの環境を変えても、すでに起動した engine の環境は変わりません。後から新しい engine 用に `child_env` が呼ばれれば、その時点で再度環境を組み立てます（`terminal/serve/server.py:3870-3896`, `827-829`）。

通常の engine 起動では `[exe, "--serve", ...]` に `env=env` を渡します。replica、split、fallback の起動も同じ `child_env` を使います。Vision encoder にも別経路で `vision_env` を渡しますが、`OMP_NUM_THREADS` をそこで独自に判定・変更する処理は確認できません（`terminal/serve/server.py:827-829`, `8304-8308`, `8333-8336`, `8396-8403`, `8897-8907`）。

## ログと測定値

`OMP_NUM_THREADS` の保持・補完について専用の stdout/stderr ログ、警告、終了コード分岐はありません。設定値の効能や性能測定値をこの変数に結び付ける記述は行いません。`docs/DETAILS.md` の CPU worker 節は `--pool-workers` の engine 側説明であり、`OMP_NUM_THREADS` の Strata 側処理を裏付けるものではありません（`docs/DETAILS.md:1350-1360`）。

## 根拠

- `terminal/serve/server.py:3682-3704` — `--pool-workers`、`--threads`、`cfg["threads"]` から worker 数を決める規則。
- `terminal/serve/server.py:3870-3896` — 親環境のコピー、設定 `env` の反映、`OMP_NUM_THREADS` のキー有無判定と補完。
- `terminal/serve/server.py:827-834` — serve engine の subprocess に `env` を渡す箇所と起動失敗処理。
- `terminal/serve/server.py:8304-8308`, `8333-8336`, `8396-8403`, `8870-8878` — fallback、replica、split、serve 本体からの環境生成・適用経路。
- `terminal/serve/server.py:8897-8907` — Vision encoder の worker 数継承と環境引き渡し。
- `docs/DETAILS.md:1350-1360` — `--pool-workers` に関する資料との照合。環境変数の動作根拠には使用していない。
