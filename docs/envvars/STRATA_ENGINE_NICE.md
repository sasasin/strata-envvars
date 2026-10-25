# `STRATA_ENGINE_NICE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata serve` が起動するエンジン子プロセスの nice 値を調整します。Linux で、KFD の GPU topology に内蔵 Radeon（iGPU）が見つかり、変数が未設定または空なら `+5` で起動します。目的は、内蔵 GPU がデスクトップを描画する PC で、CPU を使うエンジンの worker とデスクトップ側が競合する際に、デスクトップ側へ CPU の実行機会を残すことです。

## 値と判定

Linux 以外では環境変数を読み取らず、常に `0` を返します。Linux では `str(env_value).strip()` を Python の `int()` に渡し、全体を整数として変換します。変換できた値は `0`〜`19` に clamp されます。先頭だけの数値変換ではないため、たとえば `5junk` は無効です。

| 環境変数の状態 | Linux での結果 |
|---|---|
| 未設定 | KFD topology に内蔵 Radeon があれば `5`、なければ `0` |
| 空文字または空白だけ | 未設定と同じ自動判定 |
| 整数 `N` | `N` を `0`〜`19` に clamp（例: `-2` → `0`、`25` → `19`）|
| 整数に変換できない文字列 | `0`。自動判定には戻らない |

`+5` などの符号付き整数も `int()` で解釈されます。大文字小文字の比較はありません。`child_env()` が環境変数をコピーした後に設定ファイルの `env` 項目を反映するため、設定ファイルからこの変数を渡した場合は子プロセス用環境にその値が入ります。

## 有効になる条件

- nice 値の決定と `os.nice()` の適用は Linux のみです。Windows / macOS では無効です。
- 自動設定は `/sys/class/kfd/kfd/topology/nodes` を読める場合に限られます。GPU node の `properties` から有効な `gfx_target_version` と `simd_count > 0` が得られ、そのアーキテクチャが `gfx1035`, `gfx1036`, `gfx1037`, `gfx1103`, `gfx1150`, `gfx1151`, `gfx1152`, `gfx90c` のいずれかなら内蔵 Radeon と判定します。KFD topology が読めない、該当アーキテクチャがない場合、自動値は `0` です。
- 有効な明示値は自動判定より優先されます。明示値 `0`、負値を clamp した `0`、不正値による `0` は、いずれも追加の nice 調整を行いません。

## 実行時の詳細

サーバーがエンジンを起動するたびに `engine_nice(env)` を評価します。戻り値が 0 以外なら `subprocess.Popen` の `preexec_fn` で、replica 用 CPU affinity の設定があれば先に適用し、その後 `os.nice(nice)` を呼びます。これはエンジン子プロセスの起動時の処理であり、稼働中の子プロセスを後から変更する処理ではありません。変数の変更は、次のエンジン起動（サーバーによる再起動を含む）時に反映されます。

追加調整が適用されるとサーバー stdout に `[strata] engine priority: nice +N ...` が出ます。値が 0 ならこのログも `os.nice()` 呼び出しもありません。したがって `STRATA_ENGINE_NICE=0` はサーバーの nice 値を絶対値 0 に設定する操作ではなく、この機能による nice 増分を行わない指定です。親サーバーが既に nice 値を持つ場合、子はその状態を継承します。

## 根拠

- `serve/server.py:1017-1027` — nice 値の決定、非ゼロ時の affinity と `os.nice()`、ログ、エンジン子プロセス起動。
- `serve/server.py:3154-3168` — Linux 限定、値の parse と clamp、不正値処理、自動値の決定。
- `serve/server.py:3171-3187` — KFD topology の読み取りと GPU architecture 名の生成。
- `serve/server.py:3266-3267` — 内蔵 GPU として扱う architecture の一覧。
- `serve/server.py:3349-3362` — 子環境の複製と、設定の `env` による上書き。
- `docs/STRIX_HALO.md:155-156` — Linux の内蔵 Radeon 向け nice +5 と明示設定の説明。性能効果の数値測定はこの変数について記載されていません。
