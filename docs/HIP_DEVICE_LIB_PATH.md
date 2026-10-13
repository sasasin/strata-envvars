# `HIP_DEVICE_LIB_PATH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Strata のエンジンが起動する前に、サーバーが親プロセス環境からこの変数を引き継ぐかを検査します。HIP backend のサーバー起動時、値が空でなく、値をパスとして解決した場所が存在しなければ、エンジンへ渡す環境から変数を削除します。存在する場合はそのまま渡します。

Strata の C++/GPU 実装がこの変数を直接読む箇所は見つかりませんでした。コードコメントとトラブルシューティング文書は、削除済み ROCm build を指す `HIP_PATH` / `HIP_DEVICE_LIB_PATH` / `LLVM_PATH` が AMD runtime の起動を妨げるケースに対するサーバー側の修復として説明しています。runtime 内部の変数の意味や挙動はここでは扱いません。

## 値と判定

| サーバーが作る子プロセス環境の値 | 判定・処理 |
|---|---|
| 未設定 | `env.get()` は `None`。処理なし。 |
| 空文字 | 偽値としてスキップ。空文字のまま子プロセスへ渡す。 |
| 空で、参照先が存在する値 | `Path(v).exists()` が真なら変更せず渡す。ディレクトリに限る検査ではなく、`exists()` の結果だけを見る。 |
| 空でなく、参照先が存在しない値 | 子プロセス用辞書からキーを削除し、stderr に `strata serve: AMD: HIP_DEVICE_LIB_PATH=<値> does not exist: not passed to the engine` を出す。 |

値を数値・真偽値として parse せず、trim、大文字小文字比較、存在範囲の追加検査もしません。値は Python の `Path(v).exists()` に渡されます。相対パスの存在確認はサーバープロセスの現在の作業ディレクトリを基準に行われます（この検査より後に engine の `cwd` が指定されます）。

## 有効になる条件

- `child_env(cfg)` が呼ばれ、`cfg["backend"] == "hip"` の場合だけ検査します。CUDA backend などでは、サーバーがこの変数を検査・削除しません。
- 通常の `--engine strata` 起動では、起動時に `child_env(cfg)` が環境を作ります。設定の `env` 項目に同名キーがあれば、親環境をコピーした後にその設定値で上書きされ、それから存在確認されます。従って修復対象には親環境からの値だけでなく、config 由来の値も含まれます。
- データ並列 replicas では、各 replica の設定で `child_env(rc)` が呼ばれ、それぞれのエンジン環境で同じ検査をします。
- サーバーが engine 起動を管理しない直接起動（例: `strata.exe` を手で実行）にはこの修復処理は適用されません。`--engine mock` にも適用されません。

## 実行時の詳細

`child_env()` は `os.environ` のコピーを作り、HIP backend なら `hip_env_guard()` を呼びます。guard は `HIP_PATH`, `HIP_DEVICE_LIB_PATH`, `LLVM_PATH` を順に検査します。対象キーの値が存在しないパスを指す場合だけ `del env[k]` を行い、変更内容を stderr に一度出力します。親 Python サーバーの `os.environ` 自体は変更しません。エンジンはこの辞書を `subprocess.Popen(..., env=env)` に渡されて起動するため、変更は子プロセス環境に適用されます。

同じ `child_env()` が通常 engine と replica engine に使われます。vision encoder が構成されている場合は `child_env()` の結果を `vision_env()` に渡し、その環境を encoder の `Popen` に使います。そのため HIP backend では、存在しないパスを指す値は vision encoder の起動環境からも除かれます。

これは起動ごとの環境辞書作成時に行う検査です。設定を一度辞書にした後、親プロセスの環境変数を変更しても既存 engine の環境は変わりません。モデルの unload / reload に伴う engine 再起動については、`StrataEngine` が生成時に保存した `env` を再利用します。

## ログと資料

削除時の stderr 行は `strata serve: AMD: HIP_DEVICE_LIB_PATH=<値> does not exist: not passed to the engine` です。値が空、未設定、または参照先が存在する場合、この変数についてはログを出しません。`docs/TROUBLESHOOTING.md` は Windows で AMD runtime が起動前に `0xC0000005` で終了する事例について、存在しない ROCm path 環境変数をサーバーがログに示して除去すると説明しており、コードの処理と整合します。資料はこの変数単独の原因性や全環境での効果を保証していません。

## 根拠

- `serve/server.py:2622-2639` — 親環境コピー、config の `env` 上書き、HIP backend 条件での guard 呼び出し。
- `serve/server.py:2650-2680` — 説明コメント、真偽値判定、存在確認、辞書からの削除、stderr 表示。
- `serve/server.py:650-651,697-699` — `StrataEngine` が起動情報（加工済み環境を含む）を保存し、engine を `Popen` で起動する際に渡す。
- `serve/server.py:6222-6238` — replica ごとの環境構築と engine 起動。
- `serve/server.py:6375-6393`, `serve/server.py:2089-2095` — 通常起動での環境構築、および vision encoder への環境引き渡し。
- `docs/TROUBLESHOOTING.md:148-153` — Windows AMD の起動問題に対する利用者向け説明。
- `serve/test_server.py:1706-1709` は修復動作のテストですが、実装根拠には使っていません。
