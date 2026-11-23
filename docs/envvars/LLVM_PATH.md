# `LLVM_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`LLVM_PATH` は Strata の推論設定や LLVM の場所を選ぶための変数ではない。`strata serve` が HIP backend 用の子プロセス環境を組み立てる際、値が空でなく、指すパスが存在しない場合に限り、その変数をエンジンへ渡さないよう削除する。削除対象を AMD runtime 起動前に取り除くガードである（`terminal/serve/server.py:3870-3925,3928-3940`）。

## 値と判定

`child_env()` は呼び出しごとに親プロセス環境を辞書へコピーし、設定の `env` があればその値を文字列化して上書きした後、HIP backend なら `hip_env_guard()` を呼ぶ。helper は `env.get("LLVM_PATH")` の真偽値を確認し、真なら `Path(v).exists()` を調べる。文字列の parse や大文字小文字の比較はしない（`terminal/serve/server.py:3873,3890-3891,3917-3918,3935-3940`）。

| 条件 | unset | 値の扱い | 無効・境界の例 |
|---|---|---|---|
| `backend == "hip"` | 子環境にも未設定 | 空でない値のパスが存在すれば、その値を保持してエンジンへ渡す | 空文字は未設定と同様に保持。`0`、`false`、空白だけの文字列も非空なのでパスとして調べ、存在しなければ削除 |
| backend が `hip` 以外 | 親環境または設定 `env` の値をそのまま子環境に含める | このガードによる存在確認・削除なし | このガードでは値を判定しない |

`Path.exists()` はファイルとディレクトリを区別せず存在を判定する。相対パスはサーバープロセスの現在の作業ディレクトリを基準に解決される。`LLVM_PATH` 固有の既定値や別値への fallback はない（`terminal/serve/server.py:3936-3940`）。

## 有効になる条件

- `child_env()` の呼び出し設定で `cfg.get("backend") == "hip"` の場合にだけガードが動く。ソースに OS 判定はない（`terminal/serve/server.py:3917-3918`）。
- `strata serve --engine strata` のエンジン起動環境で使われる。レプリカ、split、fallback の各エンジンも `child_env()` から環境を作る（`terminal/serve/server.py:8870-8878,8304-8308,8334-8336,8402-8403`）。
- 親プロセスから継承した値より設定の `env` が優先され、その後に HIP ガードが適用される。したがって設定側が存在しないパスで上書きした場合も削除対象になる（`terminal/serve/server.py:3873,3890-3891,3917-3918`）。
- エンジンを直接起動する場合や、HIP backend 以外の場合、この `hip_env_guard()` による処理はない。

## 実行時の詳細

値はプロセス起動時に一度固定されるのではなく、`child_env()` がエンジン用の環境辞書を作るたびに、その時点の `os.environ` のコピーから評価される。関数内 cache はない。チェック後は親の `os.environ` を変更せず、子に渡す辞書だけから不在パスを除く（`terminal/serve/server.py:3873,3935-3940`）。

存在する値または空文字は子環境に残り、存在しない非空値は削除される。`StrataEngine` にはこの環境辞書が渡される（`terminal/serve/server.py:8279-8280,8307-8308,8334-8336,8402-8403,8877-8878`）。Strata ソースが記述している効果は、この値を除去または転送するところまでであり、外部 runtime が値をどう解釈するかはここでは扱わない。

## ログと測定値

存在しない非空値を削除した場合、stderr に `strata serve: AMD: LLVM_PATH=<値> does not exist: not passed to the engine` を出す。未設定、空文字、存在するパスではこの変数についてログは出ない。削除自体は終了や失敗ではなく、子プロセスへの引き渡し方の変更である（`terminal/serve/server.py:3938-3940,3956-3958`）。該当する測定値はない。

## 根拠

- `terminal/serve/server.py:3870-3925` — 子環境の生成、設定値の上書き、HIP 条件でのガード呼び出し。
- `terminal/serve/server.py:3928-3958` — パスの存在判定、値の削除、stderr 通知。
- `terminal/serve/server.py:8272-8308,8334-8336,8402-8403,8870-8878` — ガード済み環境をエンジンへ渡す経路。
- `docs/TROUBLESHOOTING.md:304-309` — Windows AMD の起動問題についての利用者向け説明。実際の適用条件と分岐は上記コードに従った。
