# `KV_STREAMING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で変更なし。

## 役割

Docker イメージの `docker-entrypoint.sh` が読む環境変数。モデルの初回セットアップ、または `REINSTALL=1` による再セットアップ時に `setup.py --kv-streaming` へ渡し、セットアップが生成するエンジン引数 `--kv-resident 32768` の有無を選ぶ。これは QSA 層の KV キャッシュについて、全セルを VRAM に置くか、RAM にホストコピーを持ち attention が読む窓だけを VRAM に常駐させるかを決める。`setup.py` 自体が `KV_STREAMING` 環境変数を読む箇所はなく、Docker 起動ラッパー専用の入力である。

## 値と判定

| `KV_STREAMING` の状態 | Docker ラッパーの処理 | セットアップでの意味 |
| --- | --- | --- |
| 未設定または空文字 | `--kv-streaming` を付けない | `setup.py` の既定値 `auto` |
| `auto` | `--kv-streaming auto` を渡す | 64K 以上の context で RAM 条件を満たす場合に有効 |
| `on` | `--kv-streaming on` を渡す | 64K 以上なら RAM 条件を越えても有効化を要求。足りない場合は警告 |
| `off` | `--kv-streaming off` を渡す | 64K 以上でも無効 |
| 上記以外の非空文字列 | その文字列をそのまま渡す | `argparse` の `choices=["auto", "on", "off"]` に合わず、セットアップは引数エラーで終了する |

値は小文字の完全一致で判定される。`ON` や前後に空白を含む値は受け付けられない。シェルの `${KV_STREAMING:-}` 展開と `[ -n ... ]` 判定により、未設定と空文字は同じ扱いになる。

## 有効になる条件

- `docker-entrypoint.sh` がセットアップを実行する必要がある。既存モデルの設定があり `REINSTALL` が `1` でない場合はセットアップを飛ばすため、環境変数を変更しても既存設定には反映されない。反映には `REINSTALL=1` が必要。
- `CONFIG` が設定されている場合、ラッパーはその設定ファイルを選び、セットアップ用引数を組み立てない。そのため `KV_STREAMING` はその起動時のセットアップ判断には使われない。
- context が 65,536 未満ならストリーミングしない。`on` でも警告 `--kv-streaming on: a context under 64K is not streamed (the attention's window holds all of it): off` を出す。
- WSL では 64K 以上でも無効。`on` 指定時は pinned RAM の制約を伝える警告を出す。セットアップ後の設定移行でも WSL 上の `--kv-resident` を削除する。
- `auto` の RAM 条件は `RAM >= MODELS[model]["ram_gb"] + kv_streaming_ram_gb(context, kv) + 1`。KV 分は `context * (13 * KV_CELL_BYTES.get(kv, 1056)) / 1e9` GB と見積もられる。KV 形式でセル当たりの見積もりが変わり、さらに 1 GB の余裕を加える。

## 実行時の詳細

Docker ラッパーは `KV_STREAMING` が空でなければ、初回セットアップまたは再セットアップの `setup.py --setup --yes` 呼び出しに `--kv-streaming VALUE` を追加する。セットアップは RAM 条件・context・WSL 判定に応じて `args` に `--kv-resident 32768` を追加し、生成する config にエンジン引数を保存する。以後のサーバー起動は保存済み config を使い、環境変数を毎リクエストや起動のたびに読み直して設定を再計算する経路はない。

有効化時のセットアップログは `KV streaming on: the context's KV cache lives in RAM (...)`、無効化時は選択理由に応じて `KV streaming off, as you chose (--kv-streaming off): ...` または RAM 条件を示す `KV streaming off: it needs ...`。`on` で RAM 見積もりを超えた場合は、ページングまたは RAM 不足のおそれを知らせる警告も出す。エンジン側は `--kv-resident` を整数として読み、負数なら `strata generate: --kv-resident must be >= 0` を stderr に出して終了コード 2 とする。セットアップが渡す値は固定の `32768`。

## 文書との照合

`docs/DETAILS.md` は 64K 以上、KV 全体を RAM に置き attention が読む部分を VRAM に置くこと、RAM に余裕がある場合の自動有効化、`on|off` による上書き、WSL での無効化を説明しており、現行コードの判断と一致する。同文書の性能値は参考記述として存在するが、本調査ではその測定を再現・検証していない。

## 根拠

- `docker-entrypoint.sh:34, 55-86, 89-94`: 環境変数の空値処理、既存 config / `CONFIG` 時にセットアップを飛ばす分岐、セットアップ CLI への受け渡し。
- `setup.py:4923-4925`: CLI の許容値と既定値 `auto`。
- `setup.py:3518-3531, 5646-5680`: RAM 見積もり、64K 条件、WSL・`on`・`off`・自動判定、生成引数とログ。
- `setup.py:4250-4256`: WSL で既存 config から `--kv-resident` を削除する移行処理。
- `src/program/generate.cpp:1894, 2500-2504`: 実行時の CLI 読み取り、負値エラー、KV resident 設定。
- `docs/DETAILS.md:79-84`, `docs/INSTALL.md:133-134`: 説明文との照合、および Docker での環境変数利用案内。
