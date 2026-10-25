# `STRATA_PIPELINE_SNAP_OVERLAP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の speculative decode で使う GDN 状態スナップショットを、窓の実行と並行して別 stream / queue でコピーするかを選びます。有効なら窓の parity ごとに2つのスナップショット領域を使い、side stream / queue でコピーします。無効なら1つの領域を使い、スナップショットを critical path 上でコピーします。パイプライン自体の有効・無効や `--pipeline-windows` の値はこの変数では変更しません。

これは `STRATA_PIPELINE_*` の開発・調整用フックです。製品資料はこれらの値を `STRATA_PIPELINE_DEBUG=1` のときだけ読むと説明しています。

## 値と判定

| 状態 | 結果 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が未設定、空、または先頭文字が `0` | helper が対象変数を未設定として扱う。重ね合わせは既定で有効 |
| debug gate が有効で、対象変数が未設定 | `atoi` の結果を使わず、既定で有効 |
| debug gate が有効で、対象変数の `atoi` 結果が 0 | 無効 |
| debug gate が有効で、対象変数の `atoi` 結果が非0 | 有効 |

`STRATA_PIPELINE_DEBUG` は空でなく、先頭文字が `0` でなければ有効です。文字列全体の比較ではありません。対象変数は C の `atoi` で変換されるため、空文字、`false`、数字で始まらない文字列は 0 となり無効です。`0`, `0abc`, `-0` も無効です。`1`, `2`, `-1`, `1abc` は非0となり有効です。数値の後ろは検査されません。

## 有効になる条件

- `--pipeline-windows` が有効で、実行時に `pipe` が成立していること。
- `--pipeline-windows` の値が2以上であること。
- 投機窓の GDN snapshot 用バッファを確保できること。
- `STRATA_PIPELINE_DEBUG` gate が有効な場合だけ、明示した対象変数の値が判定に使われること。

値が有効でも、CUDA では overlap 用の第2バッファ、side stream、event の確保のいずれかに失敗すると `pl_snap_overlap` を false にし、critical path 上のコピーに戻ります。基本スナップショット領域の確保に失敗すると `pl_snap_ok` が false となり、decode は serial になります。SYCL 実装でも overlap 用領域・queue・event が揃わなければ overlap を無効にします。基本領域の確保失敗時はパイプライン decode が成立しません。

この変数で重ね合わせを無効にしても、基本 snapshot 領域が確保できれば pipeline windows は実行されます。逆に `--pipeline-windows` が無効、または2未満なら、この設定による処理はありません。

## 実行時の詳細

CUDA と SYCL の `pipe_dbg_env()` は `STRATA_PIPELINE_DEBUG` の判定を関数内 static に保存します。プロセス内の最初の呼び出し後に debug gate の環境値を変えても反映されません。対象の `STRATA_PIPELINE_SNAP_OVERLAP` は `pipe && pipeline_windows >= 2` の pipeline 初期化時に取得し、`atoi` した結果を `pl_snap_overlap` に保持します。この初期化はリクエスト処理ループより前に一度行われるため、起動後に対象変数を変えても反映されません。

CUDA では overlap 時に各 front stage の parity ごとにコピー先を選び、window stream 上の event を side stream が待って GDN state を device-to-device copy し、完了 event を記録します。commit 側はその event を待ちます。無効時は speculative commit の直前に1つの buffer へコピーし、取り消し時もその buffer から状態を復元します。処理に失敗したときは stderr に snapshot allocation failure、または `the GDN snapshot failed` / `restoring the GDN snapshot failed` 等を出してエラー経路へ進みます。pipeline 初期化時には `decode too; the GDN snapshots beside the window` または `decode too; the GDN snapshot on the critical path` と出力されます。

SYCL 実装も同じ選択をしますが、overlap 用の別 queue と event を使い、snapshot copy は `sycl::malloc_device` の領域間で行います。

## 文書との照合

`docs/MULTI_GPU.md` は、`STRATA_PIPELINE_*` の tuning / test variables は `STRATA_PIPELINE_DEBUG=1` のときだけ読み込むと説明しています。実装では helper の判定は文字列 `"1"` との一致ではなく「空でないかつ先頭文字が `0` でないか」です。また `STRATA_PIPELINE_SNAP_OVERLAP` 自体が未設定のときは overlap が既定で有効です。

## 根拠

- `src/program/generate.cpp:340-346`, `sycl/src/program/generate.cpp:296-301`: debug gate と動的 helper。
- `src/program/generate.cpp:9105-9162`, `sycl/src/program/generate.cpp:7452-7503`: pipeline window の snapshot 準備、既定値、リソース確保、状態ログ。
- `src/program/generate.cpp:14067-14090`, `sycl/src/program/generate.cpp:10755-10777`: serial 条件と pipeline decode の有効条件。
- `src/program/generate.cpp:14117-14127,14394-14409,14517-14535`, `sycl/src/program/generate.cpp:10800-10845,11138-11157,11251-11279`: snapshot copy、event 待ち、復元経路。
- `docs/MULTI_GPU.md:498-502`: tuning / test variables に関する文書上の説明。
