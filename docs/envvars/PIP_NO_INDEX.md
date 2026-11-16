# `PIP_NO_INDEX`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 自身がこの変数を読み取って動作を分岐する箇所は確認できない。`serve --offline` が有効なとき、Strata はエンジン子プロセスへ `PIP_NO_INDEX=1` を設定して渡す。通常モードでは Strata はこの変数を設定せず、親プロセスまたは設定ファイル由来の値を環境に残す。Strata が pip の動作やネットワーク要求を直接制御するものではない。`serve/server.py` の `child_env` と `strata_control/offline.py` の `OFFLINE_ENV` が実装箇所である（`serve/server.py:4428-4454`、`strata_control/offline.py:42-59`）。

## 値と判定

Strata は `PIP_NO_INDEX` の入力値を parse しない。`--offline` が有効なら既存値やプロファイルの `env` 値を `"1"` で上書きし、無効なら `child_env` はこのキーを特別扱いせず、`os.environ` からコピーした値（または `cfg["env"]` で上書きされた値）をそのまま渡す（`serve/server.py:4431-4448`）。

| 条件 | 親環境・設定の値 | Strata が子へ渡す値 |
|---|---|---|
| `serve --offline` あり | 未設定、空文字、`0`、任意の文字列 | 常に `1` |
| `serve --offline` なし | 親環境で未設定、設定 `env` にも指定なし | 未設定 |
| `serve --offline` なし | 親環境に値あり | その値を維持。ただし設定 `env` に同名キーがあればその文字列値で上書き |

この変数自体に Strata 側の無効値・境界値規則はない。`0`、`true`、空文字なども Strata による判定には使われず、offline モード時は `1` に置き換えられる（`serve/server.py:4440-4448`）。

## 有効になる条件

- `serve` の `--offline` が有効であること。オプションは `store_true` で、Strata は `a.offline` をエンジン環境の構築へ渡す（`serve/server.py:9985-9986`, `10180-10183`, `10258-10263`）。
- 製品エンジン経路（`--engine strata`）であること。mock engine の分岐では Strata エンジン子プロセスを起動しないため、この経路で `PIP_NO_INDEX` を渡す処理はない（`serve/server.py:10175-10183`, `10270-10275`）。
- 対象は Strata が起動するエンジン子プロセスの環境。通常起動に加え、分割エンジンの fallback、replica、split の各起動経路も `child_env(..., offline=offline)` から環境を作る（`serve/server.py:9546-9550`, `9555-9578`, `9625-9645`）。
- vision encoder を起動する構成でも同じ環境辞書が渡る（`serve/server.py:10208-10209`, `3195-3205`, `3341-3348`）。
- offline ポリシーモジュールの import に失敗した場合、`child_env` は `STRATA_OFFLINE`、`HF_HUB_OFFLINE`、`TRANSFORMERS_OFFLINE` のみを追加設定する fallback に入り、`PIP_NO_INDEX=1` への上書きは行わない。先に組み立てた親環境または設定値は残る（`serve/server.py:4431-4454`）。通常の配布構成でこの import 失敗が起こるかは、このコードからは確認できない。
- `--offline` は MCP サーバーや `before_load` コマンドを使うプロファイルを拒否する。さらに offline ポリシーが strict offline と両立しない profile 要件を検出した場合、引数エラーで停止する（`serve/server.py:10162-10173`）。

## 実行時の詳細

Strata サーバーは `child_env` で親プロセス環境をコピーし、プロファイルの `env` を文字列化して反映した後、offline の場合は offline 環境一式を最後に適用する。この順序により、offline 時の `PIP_NO_INDEX=1` は親環境やプロファイルで指定した同名値より優先される（`serve/server.py:4431-4448`）。

作成された環境辞書は `StrataEngine` に渡され、エンジン起動時に `popen(..., env=env)` で子プロセスへ渡る。エンジンの再起動用情報にも同じ環境が保持される（`serve/server.py:1101-1103`, `1161-1165`）。vision encoder を起動する場合も、同じ環境（必要な GPU 可視性だけを調整した辞書）が `popen` に渡る（`serve/server.py:4608-4623`, `10208-10209`, `3341-3348`）。この変数について Strata が実行中に再読込する処理や static cache はない。サーバー起動時の環境辞書作成時に値が決まり、後から親プロセス環境を変えても既存の子プロセス環境は変わらない。

## ログと測定値

`PIP_NO_INDEX` の設定値や設定有無を示す専用ログ、警告、終了経路は確認できない。`--offline` の profile 不適合は `argparse` の引数エラーとなるが、これは `PIP_NO_INDEX` の値判定ではなく、offline 機能全体の事前条件である（`serve/server.py:10162-10173`）。関連する測定値はない。

## 根拠

- `strata_control/offline.py:42-59` — 子プロセス用 offline 環境に `PIP_NO_INDEX: "1"` を定義。
- `serve/server.py:4428-4454` — 子環境の生成、プロファイル値の反映、offline ポリシーの上書きと import fallback。
- `serve/server.py:9985-9986`, `10162-10183`, `10258-10263` — CLI フラグ、profile の事前判定、engine 起動への適用。
- `serve/server.py:1101-1103`, `1161-1165` — 環境を engine 起動・再起動情報に保持し、子プロセスへ渡す箇所。
- `serve/server.py:9546-9550`, `9555-9578`, `9625-9645` — fallback、replica、split engine の環境適用箇所。
- `packaging/smoke_terminal.py:78-80` — 別用途として terminal archive smoke-test の環境に同名キーを固定値で加える箇所。製品の環境読み取りではない。
