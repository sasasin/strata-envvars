# `STRATA_PIPELINE_SNAP_OVERLAP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の speculative decode で、検証中の window が読む GDN 状態のスナップショットを、window の実行と並行してコピーするかを選びます。既定の overlap 経路では window の parity ごとに別バッファを使い、window の実行 stream に置いた event を合図に side stream でコピーします。無効にするとバッファを1つにし、window を commit する直前にその window の GDN 状態をコピーします。この変数が選ぶのはコピーの時期とバッファ構成です。

対象は `src/program/generate.cpp` の CUDA 実装と `sycl/src/program/generate.cpp` の SYCL 実装です。どちらも Strata 所有コード内で明示的に読みます。

## 値と判定

値の判定は `pipe_dbg_env()` を通した後の `std::atoi(v) != 0` です。文字列全体の数値検証ではなく、`atoi` が変換した整数が0かどうかで決まります。数値変換できない文字列や空文字は0になり無効、`1` や `-1` は有効です。先頭の空白と符号は `atoi` の変換規則に従い、数値の後ろの文字列は判定に使われません。

ただし、`STRATA_PIPELINE_DEBUG` が有効でない場合、helper は対象変数を読まず `nullptr` を返します。その結果、対象変数は未設定扱いとなり、overlap は既定で有効です。

| `STRATA_PIPELINE_DEBUG` の状態 | `STRATA_PIPELINE_SNAP_OVERLAP` | overlap 判定 |
|---|---|---|
| unset、空文字、または先頭文字が `0` | 任意 | 既定で有効（対象変数を無視） |
| 先頭文字が `0` 以外 | unset | 有効 |
| 先頭文字が `0` 以外 | `atoi` の結果が0 | 無効 |
| 先頭文字が `0` 以外 | `atoi` の結果が非0 | 有効 |

`STRATA_PIPELINE_DEBUG` も `pipe_dbg_env()` 内で最初に呼ばれた時の値を static cache します。対象変数の判定は pipeline 初期化時に行われ、プロセス稼働中に環境変数を書き換えても現在の設定には反映されません。CLI オプションによる値の上書きはありませんが、`--pipeline-windows 2` を含む pipeline 経路に入らなければ対象変数の効果はありません。

## 有効になる条件

- `--pipeline-windows` が2以上で、pipeline の stage 構成が作られていること。通常は複数 GPU の layer split の serve 経路です。
- GDN snapshot 用の最初の GPU buffer を確保できること。確保できない場合、CUDA は `pl_snap_ok=false` として pipeline decode を選ばず、SYCL も snapshot buffer を null のままにして pipeline decode を選びません。
- overlap を有効と判定した場合、CUDA では追加 buffer、side stream、parity ごとの event を作成できること。SYCL では追加 buffer、side queue、event を作成できること。これらの確保・作成に失敗した場合は overlap が無効化されますが、最初の snapshot buffer が残っていれば pipeline decode 自体は続き、snapshot は commit の直前にコピーされます。

## 実行時の詳細

CUDA では front stage ごとの `PlSnap` が、GDN state、snapshot buffer、side stream、および2組の `pre` / `ev` event を保持します。overlap 経路の `snap_take()` は window の parity (`seq & 1`) に対応する buffer を使い、window の stream に `pre` event を記録してから side stream に待たせ、GDN state を device-to-device copy し、完了 event を記録します。後続 window の commit 前には、その parity の完了 event を window stream に待たせます。推測 window が外れて state を戻すときも、window の parity に対応する保存先から復元します。overlap 無効時は parity バッファを使わず、commit 直前に1個の buffer へ状態をコピーしてから commit します。根拠: `src/program/generate.cpp:7678-7724,11352-11365,11630-11646,11757-11774`。

起動時の serve stderr には、snapshot が確保され pipeline が使える場合、`(decode too; the GDN snapshots beside the window)` または `(decode too; the GDN snapshot on the critical path)` が付きます。追加の overlap resource が作れず fallback した場合も後者の表示になります。最初の buffer が確保できない場合は `the GDN snapshot ... does not fit; the decode stays serial` と表示します。根拠: `src/program/generate.cpp:7705-7730`。

SYCL も同じ値ゲートと既定動作を使い、side queue と event を用いた snapshot copy を行います。値判定と初期化は `sycl/src/program/generate.cpp:7276-7327`、copy と event 同期は `sycl/src/program/generate.cpp:10519-10559` にあります。SYCL 側の表示文言は CUDA 側と同じ説明句を使いますが、実装は DPCT/SYCL queue・event API です。

## 根拠

- `src/program/generate.cpp:251-257`: `STRATA_PIPELINE_DEBUG` を使う helper。未設定・空・先頭 `0` なら debug gate は閉じ、pipeline tuning variable を未設定扱いにする。
- `src/program/generate.cpp:7678-7730`: snapshot の目的、対象条件、値判定、allocation fallback と起動ログ。
- `src/program/generate.cpp:11352-11365,11630-11646,11757-11774`: snapshot の取得、rollback 復元、commit 前の同期。
- `sycl/src/program/generate.cpp:293-298,7276-7327,10519-10559`: SYCL 側の helper、初期化、copy/event 同期。
- `docs/MULTI_GPU.md:258-271`: `--pipeline-windows 2` が次の speculative window を先行実行し、予測が外れた場合に先行 stage の recurrent state を戻す設計の説明。測定値はこの変数の効果を分離して示していないため、本書では性能向上を主張しない。
