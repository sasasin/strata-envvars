# `STRATA_REPO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

この変数は Strata の通常の CLI・engine・server 設定ではない。調査対象 commit では、ベンチマーク／研究用 Python スクリプトが、作業対象 checkout の位置を指定するために読む。値は `REPO` に保存され、`sys.path` への追加や設定ファイル既定パスの組み立てに使われる。engine の実行時動作を直接変更する読み取りは見つからなかった。

用途は次のとおり。

- `docs/bench-results/2026-10-06-community-rtx4090-opt-ins/conc_bench.py` は `REPO` を `STRATA_CFG` 未設定時の既定設定ファイル `REPO + "/strata-200k.json"` に使う（同ファイル:33-35）。
- `tools/research/tools/live-probes-2026-10/` の3スクリプトと `tools/research/tools/ab-harnesses-2026-10/idle_gpu_ab.py` は checkout の `tools` とルートを `sys.path` に加え、そこから tokenizer や serve 関連モジュールを import する（`session_pressure_test.py:14-18`、`cancel_park_test.py:17-20`、`batch_groups_cache_test.py:16-20`、`idle_gpu_ab.py:144-149`）。
- `engine/metal/tests/serve_probe.py` は checkout の `terminal/tools` とルートを `sys.path` に加え、同じ checkout の tokenizer と serve モジュールを import する（同ファイル:15-19）。

## 値と判定

値は文字列として読む。真偽値・数値・大小文字・空白の parse や妥当性検査はない。未設定時の処理は読み取り箇所ごとに異なる。

| 読み取り箇所 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `conc_bench.py:33` | `"/home/dgbox/Strata"` を使用 | 任意の文字列をそのまま `REPO` とする。例: `/work/Strata` | 値の形式による無効判定なし。空文字も受理し、`STRATA_CFG` も未設定なら設定パスは `/strata-200k.json` になる（33-35行） |
| live-probes の3スクリプト | `Path(__file__).resolve().parents[3]` を使用 | 任意の文字列を `Path` に渡す。例: `/work/Strata` | 値の形式による無効判定なし。空文字は `Path("")`、すなわち現在ディレクトリ相対の `.` になる（`session_pressure_test.py:14-15`、`cancel_park_test.py:17-18`、`batch_groups_cache_test.py:16-17`） |
| `idle_gpu_ab.py:145`、`serve_probe.py:15` | `os.environ["STRATA_REPO"]` が `KeyError` を送出 | 任意の文字列を `Path` に渡す。例: `/work/Strata` | 値の形式による無効判定なし。空文字は `Path("")`（`.`）。unset は起動時例外になる |

パスが存在するか、必要なファイルを含むかは `STRATA_REPO` の値判定時には検証しない。`Path` 化と `sys.path` 追加の後、実際の import やファイルアクセスで問題が表面化する。`conc_bench.py` では独立した `STRATA_CFG` が設定されていればそちらが優先され、`STRATA_REPO` は設定ファイル既定値に使われない（`conc_bench.py:33-35`）。

## 有効になる条件

- 影響するのは、上記の該当 Python スクリプトを実行する場合だけ。OS や CUDA/HIP/SYCL build macro による `STRATA_REPO` 自体の分岐はない。
- `idle_gpu_ab.py` は `--summary` を指定すると `summary(...)` の後に `sys.exit(0)` するため、その経路では `STRATA_REPO` の読み取り箇所（145行）に到達しない（同ファイル:140-147）。
- checkout のルート構成に依存する import を行うスクリプトでは、指定先に期待する `tools` 等の構成が必要。値が設定されても checkout が異なる、またはパスが不正なら、後続の import／ファイル利用は成功すると保証されない。
- 通常の Strata CLI・engine・server プロセスがこの名前を読む箇所はない。対象スクリプトは値を engine の CLI 引数へ変換していない。関連する server 呼び出しには別途 `child_env(cfg)` 等を渡すが、`STRATA_REPO` の engine 側制御を示すものではない（`session_pressure_test.py:28-30`、`cancel_park_test.py:29-31`、`batch_groups_cache_test.py:31-33`、`idle_gpu_ab.py:145-149`、`serve_probe.py:15-23`）。

## 実行時の詳細

すべて Python モジュールのトップレベルで `REPO` に代入されるため、スクリプトの import／実行時に評価される。各プロセス内で環境を再読する関数や cache 更新処理はない。実行中に環境変数を変更しても、既に代入された `REPO` は変わらない。

live-probes と `serve_probe.py` は `REPO` 由来のディレクトリを `sys.path` に追加してから Strata 内の Python モジュールを import する。`idle_gpu_ab.py` も同様に `tools` とルートを追加する。`conc_bench.py` は環境変数から `REPO` を一度取得し、`STRATA_CFG` 未設定の場合に限って設定 JSON の既定パスに使う。これらの読み取りは引数や別環境変数との併合、Strata engine への値の転送を行わない（各該当箇所は「役割」「根拠」参照）。

## ログと測定値

`STRATA_REPO` の値を出す専用ログ、警告、終了コード処理は読み取り箇所にない。`idle_gpu_ab.py` と `serve_probe.py` の必須参照で未設定なら、Python の `os.environ` 添字参照により `KeyError` となる。任意参照の3スクリプトと `conc_bench.py` は未設定時に表の既定値を使う。測定値はこの変数の挙動の根拠として記載していない。

## 根拠

- `docs/bench-results/2026-10-06-community-rtx4090-opt-ins/conc_bench.py:33-35` — 既定 checkout と `STRATA_CFG` の既定値。
- `tools/research/tools/live-probes-2026-10/session_pressure_test.py:14-18` — optional read、checkout 既定値、import path。
- `tools/research/tools/live-probes-2026-10/cancel_park_test.py:17-20` — optional read、checkout 既定値、import path。
- `tools/research/tools/live-probes-2026-10/batch_groups_cache_test.py:16-20` — optional read、checkout 既定値、import path。
- `tools/research/tools/ab-harnesses-2026-10/idle_gpu_ab.py:140-149` — summary の早期終了、必須 read、import path。
- `engine/metal/tests/serve_probe.py:6-19` — 使用方法、必須 read、import path。
