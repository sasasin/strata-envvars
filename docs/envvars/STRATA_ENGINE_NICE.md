# `STRATA_ENGINE_NICE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata サーバーが engine 子プロセスを起動する際、Linux でその子プロセスに適用する nice 増分を選ぶ。正の値なら engine のプロセス優先度を下げる。明示値は GPU/backend や engine の CLI 引数を変えず、`os.nice(nice)` を `preexec_fn` から呼ぶことで起動時のプロセス nice を設定する。サーバーは適用値が 0 より大きいときだけ標準出力に案内を出す（`terminal/serve/server.py:817-829`）。

未設定時の Linux 既定値は、KFD topology から得た GPU arch のいずれかが `HIP_IGPU_ARCHS` に含まれると `5`、それ以外は `0`。対象 arch 一覧は `terminal/serve/server_parts/engines.py:1017`。この判定は engine の backend 設定ではなくホストの topology を調べるため、GPU を使わない経路や別 backend の engine でも条件が一致すれば値を返す（`terminal/serve/server.py:3736-3737`）。

## 値と判定

判定は Linux の engine 起動ごとに行う。OS が Linux でなければ環境変数を参照せず `0` を返す。Linux では `env` 引数（通常は `child_env` が作った子プロセス環境。`terminal/serve/server.py:3870-3891`）から取得し、値を文字列化して前後の空白を除いた後 Python の `int()` で変換する。変換できた値は `0..19` に clamp される。大文字小文字の概念はなく、`true` / `false` は数値として変換できない。`0anything` のような末尾文字付きも変換エラーとなる。空文字または空白だけは unset と同じ自動判定に進むが、その他の無効値は `0` を返して自動判定を抑止する（`terminal/serve/server.py:3723-3737`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・特別扱いとなる値 |
|---|---|---|---|
| Linux | KFD topology に `HIP_IGPU_ARCHS` の arch があれば `5`、なければ `0` | `int()` で読める整数。結果を `0..19` に clamp（例: `9` → `9`、`20` → `19`、`-1` → `0`） | 空文字・空白のみは unset と同じ。`x`、`true`、`0anything` は変換エラーで `0`。符号付き整数や前後空白は `int()` が受理し、変換後 clamp |
| Linux 以外 | `0` | なし（環境変数を読む前に返る） | すべて実質無視 |

値の既定判定は `/sys/class/kfd/kfd/topology/nodes` を読む `hip_gpu_archs()` に依存する。ディレクトリがない、node 情報を取得できない、または有効 node がない場合は arch 判定用データが `None` となり、既定値は `0`（`terminal/serve/server.py:3736-3757`）。

## 有効になる条件

- Strata の Python サーバーが `StrataEngine` を起動する経路で適用される。通常起動、分割 engine、replica engine、役割別 engine は `StrataEngine(..., env=...)` を使う（`terminal/serve/server.py:8277-8280`, `8303-8308`, `8331-8336`, `8399-8404`）。
- Linux であること。`platform.startswith("linux")` で判定し、Windows / macOS では `0`（`terminal/serve/server.py:3728-3729`）。
- 明示値がある場合、その clamp 後の値が `0` より大きいときだけ `os.nice()` が呼ばれる。明示 `0`、負値、無効値は変更を行わない（`terminal/serve/server.py:3731-3735`, `817-820`）。
- unset / 空白のみの場合、`hip_gpu_archs()` が返す arch のうち一つでも `HIP_IGPU_ARCHS` に入っていることが自動既定値 `5` の条件。該当 arch 一覧は gfx1035 / gfx1036 / gfx1037 / gfx1103 / gfx1150 / gfx1151 / gfx1152 / gfx90c（`terminal/serve/server.py:3736-3737`, `terminal/serve/server_parts/engines.py:1017`）。topology を読めない場合は機能は有効にならない。
- サーバーから engine へ渡す環境は親プロセス環境のコピーを起点にし、設定の `env` 項目で同名キーを後から上書きする。そのため設定 `env` に `STRATA_ENGINE_NICE` があれば親の値より優先する（`terminal/serve/server.py:3870-3873`, `3890-3891`）。CLI 引数による上書き処理はこの判定箇所にはない。

## 実行時の詳細

`StrataEngine.__init__` は spawn 情報に `env` を保持し、各起動時に `engine_nice(env)` を呼ぶ。engine の再起動も保存した spawn 情報から `__init__` を呼び直すため、保存済み環境を使って再判定する（`terminal/serve/server.py:755-761`, `817`, `terminal/serve/server.py:1201-1212`）。関数内 static cache はなく、`engine_nice` は呼び出しごとに環境値を読み、unset / 空白の場合はその時点で `hip_gpu_archs()` を呼ぶ。既に作成された子プロセスの nice は後から環境を変更しても変化しない。

返り値が正なら、サーバーは既存の CPU affinity 設定があればそれを先に実行し、その後 `os.nice(nice)` を子プロセス起動前処理で呼ぶ。環境変数自体は `Popen` の `env` として子へ渡される（`terminal/serve/server.py:814-829`）。この変数を読むのはサーバー側であり、engine の C++ 実装に同名変数を読む参照はない。

## ログと測定値

適用値が正のとき、サーバーは stdout に `[strata] engine priority: nice +N (this PC has built-in Radeon graphics that usually draw the desktop; STRATA_ENGINE_NICE=0 turns it off)` を出力して flush する。値が `0` のときはこの行を出さない（`terminal/serve/server.py:817-822`）。nice 設定専用の警告・fallback ログ・性能測定値は確認できない。engine 起動時の `Popen` が `OSError` で失敗する経路では、サーバーは loading event とログ handle を処理して例外を再送出する（`terminal/serve/server.py:826-834`）。nice 設定失敗に固有のメッセージはこの箇所にない。

## 根拠

- `terminal/serve/server.py:3723-3737` — OS 分岐、環境値の取得・変換・clamp、自動 arch 判定。
- `terminal/serve/server.py:3740-3757` — Linux KFD topology からの GPU arch 取得と読み取り失敗時の扱い。
- `terminal/serve/server_parts/engines.py:1017` — 自動判定に使う `HIP_IGPU_ARCHS` 一覧。
- `terminal/serve/server.py:3870-3891` — 子環境の作成と設定 `env` による上書き。
- `terminal/serve/server.py:755-761`, `817-834`, `1201-1212` — 起動・再起動時の判定、`os.nice` 適用、失敗処理。
