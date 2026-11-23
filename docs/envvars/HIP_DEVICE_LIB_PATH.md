# `HIP_DEVICE_LIB_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 本体の HIP 設定値や GPU 計算を切り替える環境変数として読む箇所は見つからない。Strata の Python サーバーが HIP エンジン用の子プロセス環境を組み立てるとき、この変数が空でなく、指すパスが存在しない場合に限り、その子プロセスへ渡さないよう削除して stderr に知らせる。パスが存在すれば値を変更せず子プロセスへ渡す。実装は `child_env` と `hip_env_guard`（`terminal/serve/server.py:3870-3925`, `3928-3958`）。

## 値と判定

変数値自体の数値・真偽値変換はない。`hip_env_guard` は `env.get(k)` の Python truthiness と `Path(v).exists()` で判定する。`HIP_DEVICE_LIB_PATH` の文字列をパスとして扱い、ファイルかディレクトリかは区別しない。

| 条件 | unset | 設定時に維持してエンジンへ渡す値 | 削除して警告する値 |
|---|---|---|---|
| サーバー設定の `backend` が `hip` | 辞書にキーがなく、何もしない | 空文字以外で `Path(value).exists()` が真となる値（既存のファイルまたはディレクトリなど）。`0` や `false` も、同名パスが存在すれば維持する | 空文字以外で指すパスが存在しない値。例: `0`、`false`、`0anything` は通常は存在しないパスとして削除される（同名パスがあれば削除されない） |
| `backend` が `hip` 以外 | 元の環境にキーがなければキーなし | `child_env` はこの変数を検査しないため、元の環境または設定の値をそのまま保持 | 該当なし |

明示的な空文字は Python で偽となるため、HIP の場合も削除・警告されず、空文字のまま子プロセス環境に残る。空白だけの値は真となり、その文字列をパスとして存在確認する。大文字小文字、前後空白、数値としての妥当性は別途検証しない。相対パスはサーバーの現在の作業ディレクトリ基準で `Path.exists()` に渡される。 (`terminal/serve/server.py:3936-3940`)

## 有効になる条件

- サーバーが `--engine strata` 経路で Strata エンジンを起動し、子環境の `backend` が文字列 `hip` の場合に検査する。通常起動の `child_env` に加え、レプリカ・split・fallback のエンジン起動も同関数を呼ぶ（`terminal/serve/server.py:8297-8308`, `8333-8336`, `8396-8403`, `8870-8878`）。
- `backend` が HIP 以外ならこの検査は行わない。OS やビルド macro による追加条件はこの処理にはない。
- サーバー設定の `env` に同名キーがあれば、親プロセス環境をコピーした後に設定値で上書きされる。その後 HIP 判定が行われるため、設定値が優先される。設定値が空文字なら、親環境に有効な値があっても空文字が残る（`terminal/serve/server.py:3873`, `3890-3891`, `3917-3919`）。
- `HIP_PATH` と `LLVM_PATH` も同じループで個別に検査されるが、それらの値から `HIP_DEVICE_LIB_PATH` を補完・上書きする処理はない（`terminal/serve/server.py:3936-3940`）。CLI 引数によるこの値の変換・優先指定は確認できない。

## 実行時の詳細

`child_env` 呼び出し時に `dict(os.environ)` で親環境のスナップショットを作り、サーバー設定の `env` を反映する。HIP の場合はその辞書を `hip_env_guard` に渡す。パスが存在しなければ辞書からキーを削除し、存在すれば値をそのままにする。親サーバープロセスの `os.environ` 自体は変更しない（`terminal/serve/server.py:3870-3925`, `3928-3940`）。

作成した環境辞書は `StrataEngine` 起動時に `popen(..., env=env)` で子プロセスへ渡される（`terminal/serve/server.py:827-830`）。この変数用の static cache やリクエスト単位の再読込はない。値は `child_env` を呼んだ時点で決まり、同じ起動処理内の再試行は既に作られた `env` を使う。新しいエンジン起動で `child_env` が再度呼ばれれば、その時点の親環境と設定から作り直される。

## ログと測定値

HIP の子環境から値を削除した場合、stderr に `strata serve: AMD: HIP_DEVICE_LIB_PATH=<値> does not exist: not passed to the engine` と出す。値が空、またはパスが存在する場合、この変数についての警告は出ない（`terminal/serve/server.py:3936-3940`, `3956-3957`）。

この処理自体は変数を削除して警告するだけで、終了・fallback・再試行を起こさない。Strata 所有ソースに、この変数をエンジン内部で直接読む箇所は確認できなかったため、エンジンや外部 HIP runtime が受け取った後に行う処理・失敗条件は本書では説明しない。

## 根拠

- `terminal/serve/server.py:3870-3925` — 子プロセス環境の作成、設定 `env` の優先、HIP 条件、guard 呼び出し。
- `terminal/serve/server.py:3928-3958` — 3 変数の存在確認、削除、stderr 警告。
- `terminal/serve/server.py:827-830` — 作成済み環境辞書をエンジン subprocess に渡す箇所。
- `terminal/serve/server.py:8297-8308`, `8333-8336`, `8396-8403`, `8870-8878` — 通常・fallback・replica・split の起動経路。
