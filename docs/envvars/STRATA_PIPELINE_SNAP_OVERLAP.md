# `STRATA_PIPELINE_SNAP_OVERLAP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の speculative decode で使う GDN state snapshot のコピーを、window の実行と重ねるかを選びます。ON の場合は parity ごとの二つの snapshot buffer、別 stream/queue、event を用意し、window 実行中に snapshot をコピーします。OFF の場合は buffer を一つにし、commit 前のクリティカルパス上で snapshot をコピーします。これは window 間の snapshot の取り方を変える設定です。

この値を読むのは CUDA/HIP 共用の `src/program/generate.cpp` と SYCL の `sycl/src/program/generate.cpp` です。両方とも `pipe_dbg_env()` 経由で読みます。同 helper は `STRATA_PIPELINE_DEBUG` が有効でないとき対象名を未設定として扱います（`src/program/generate.cpp:461-467`, `sycl/src/program/generate.cpp:298-303`）。

## 値と判定

有効値を文字列全体として検証せず、`std::atoi(v) != 0` で判定します。`atoi` が整数として読める先頭部分を使うため、たとえば `1abc` と `-1` は ON、`0abc`、空文字、整数に変換できない文字列は OFF です。未設定時は ON です。ただし `STRATA_PIPELINE_DEBUG` が無効なら helper が `nullptr` を返すので、`STRATA_PIPELINE_SNAP_OVERLAP=0` を設定していても未設定時と同じ ON になります。

| `STRATA_PIPELINE_DEBUG`（helper の初回評価時） | 対象変数 | 判定結果 |
|---|---|---|
| unset、空文字、先頭文字が `0` | 任意 | helper は `nullptr` を返し、既定で ON |
| 空でなく先頭文字が `0` 以外 | unset | ON |
| 同上 | `atoi` の結果が 0 | OFF |
| 同上 | `atoi` の結果が 0 以外 | ON |

大小文字の比較は行いません。空白の完全一致、数値範囲、文字列全体の妥当性も検査しません。実際の判定式は `src/program/generate.cpp:10281-10284` と `sycl/src/program/generate.cpp:7585-7598` にあります。

## 有効になる条件

- `--serve` の layer split で pipeline windows が有効であり、`--pipeline-windows 2` 相当であること。pipeline 自体は MTP drafter と `--spec >= 2` を必要とし、batch slots、peer device、helper caches など非対応条件で無効になります（CUDA/HIP: `src/program/generate.cpp:5005-5020`; SYCL: `sycl/src/program/generate.cpp:3449-3470`）。
- CUDA/HIP 側は `pipe` が真、すなわち pipeline windows が正、stage 数が 2 以上、同一 GPU split でなく stage vector が stage 数に対応する場合に pipeline loop に入ります（`src/program/generate.cpp:10005`）。snapshot overlap の値自体はさらに `o.pipeline_windows >= 2` のときだけ読みます（`src/program/generate.cpp:10279-10285`）。
- SYCL 側は `pipe` が真、すなわち pipeline windows が正、stage 数が 2、同一 GPU split でなく一つの後段 stage がある場合に pipeline loop に入ります（`sycl/src/program/generate.cpp:7329`）。snapshot overlap の値はさらに `o.pipeline_windows >= 2` のときだけ読みます（`sycl/src/program/generate.cpp:7580-7598`）。
- `--pipeline-windows 1` では pipeline 自体を使えてもこの変数は読まれず、GDN snapshot の二重化を行う `>= 2` の処理には入りません。

この設定は `--pipeline-windows` の可否や自動選択を上書きしません。pipeline が無効、または window 数が 2 未満なら設定値は snapshot 動作に影響しません。

## 実行時の詳細

snapshot setup 時に、まず一つ目の GDN snapshot buffer を確保します。overlap 判定が ON なら、二つ目の buffer と別 stream/queue、parity ごとの event も確保します。CUDA/HIP では追加リソースの確保に失敗すると `pl_snap_overlap` を OFF にして一 buffer 経路へ fallback します（`src/program/generate.cpp:10282-10310`）。SYCL でも追加 buffer、queue、event の確保結果を `pl_snap_overlap` に反映し、失敗時は OFF の経路になります（`sycl/src/program/generate.cpp:7585-7621`）。一つ目の snapshot buffer 自体が確保できなければ、stderr に `the GDN snapshot ... does not fit; the decode stays serial` を出します（CUDA/HIP: `src/program/generate.cpp:10292-10298`; SYCL: `sycl/src/program/generate.cpp:7588-7596`）。

pipeline の初期化時には stderr に `two verifiers per stage ...` と、snapshot が window と並行する場合の `(decode too; the GDN snapshots beside the window)`、またはクリティカルパス上の場合の `(decode too; the GDN snapshot on the critical path)` が出ます（CUDA/HIP: `src/program/generate.cpp:10313-10317`; SYCL: `sycl/src/program/generate.cpp:7623-7627`）。したがって、要求値が ON でも追加リソースの確保に失敗すれば後者の表示になります。

overlap 経路では snapshot を parity に対応する buffer へ別 stream/queue でコピーし、その完了 event を speculative commit 側が待ちます（CUDA/HIP: `src/program/generate.cpp:16127-16139,16532-16548`; SYCL: `sycl/src/program/generate.cpp:11074-11100,11526-11548`）。OFF 経路では speculative commit 前に通常 stream/queue から単一 buffer へコピーします（同上）。実行中に target 環境変数を変更しても、setup 済みの `pl_snap_overlap` は再評価されません。

helper の `STRATA_PIPELINE_DEBUG` 判定は `static const bool` であり、プロセス内で helper が最初に呼ばれた時点の値をキャッシュします。target 変数そのものは snapshot setup の呼び出しで `getenv` され、`atoi` された結果が `pl_snap_overlap` に保存されます（`src/program/generate.cpp:464-466,10284`; `sycl/src/program/generate.cpp:300-302,7597-7598`）。この環境変数の値判定に伴う専用警告や終了経路はありません。snapshot コピー処理そのものが失敗すると `the GDN snapshot failed`、復元処理なら `restoring the GDN snapshot failed` を decode loop の失敗として返します（CUDA/HIP: `src/program/generate.cpp:16412-16414,16537-16548`; SYCL: `sycl/src/program/generate.cpp:11420-11425,11531-11548`）。

## 根拠

- helper による debug gate とその cache: `src/program/generate.cpp:461-467`; `sycl/src/program/generate.cpp:298-303`。
- CUDA/HIP での値読み取り、初期化、割当 fallback、状態ログ: `src/program/generate.cpp:10279-10317`。
- SYCL での値読み取り、初期化、割当 fallback、状態ログ: `sycl/src/program/generate.cpp:7576-7627`。
- overlap/off のコピーと復元: `src/program/generate.cpp:16127-16139,16406-16424,16532-16548`; `sycl/src/program/generate.cpp:11074-11100,11408-11431,11526-11552`。
- `docs/DETAILS.md` にこの変数の挙動や測定値の説明は見つかりませんでした。
