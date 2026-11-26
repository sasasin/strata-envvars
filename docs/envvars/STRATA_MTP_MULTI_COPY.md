# `STRATA_MTP_MULTI_COPY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の `strata::kernels::copy_from_mapped_multi` が、複数の mapped input を 1 個の CUDA kernel launch でまとめてコピーするか、各入力に個別の copy kernel を launch するかを選びます。未設定時はまとめてコピーする経路です。MTP の draft-round 入力 7 件と batch MTP の入力コピーから呼ばれます（`engine/src/kernels/cuda/elementwise.cu:423-447`、`engine/src/core/mtp.cpp:1595-1616,2674-2718`）。この分岐はコピーの launch 構成だけを変え、MTP の候補 token や検証・採用処理を直接変更しません。

この環境変数を実際に読む製品コードは CUDA 版です。SYCL 版の同名関数は環境変数を読まず multi kernel を起動し、Metal の実装は missing stub です（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:894-920`、`engine/metal/src/engine/stubs.cpp:144`）。したがって CUDA 以外ではこの変数による分岐はありません。

## 値と判定

CUDA 実装は `std::getenv` の結果を毎回取得し、未設定なら ON、設定済みなら値の先頭文字が `'0'` 以外の場合に ON とします。文字列全体の parse、数値変換、空白除去、大文字小文字変換はありません（`engine/src/kernels/cuda/elementwise.cu:423-428`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA `copy_from_mapped_multi` の呼び出し | multi kernel を使う | `1`、`true`、`false`、空文字、` 0`、`00`（先頭文字が `0` でない） | `0`、`0anything`（先頭文字が `0`） |
| SYCL 版 | 環境変数を参照せず multi kernel を使う | 該当なし | 該当なし |

「無効」は個別コピー経路を選ぶ意味です。値の妥当性検査や無効値の警告、fallback はありません。空文字は設定済みですが `e[0]` が終端文字 `\0` なので multi ON です。判定は大文字小文字を区別する parse ではなく、文字列の最初の byte と `'0'` の比較です（同:426-436）。

## 有効になる条件

- CUDA backend で、MTP コードから `copy_from_mapped_multi` が呼ばれること。通常の draft round は `--mtp` と `--spec`（2 以上）が使われ MTP drafter がロードされる経路で呼ばれます。`--mtp` 単独で `--spec` が 2 未満なら MTP は無視されます（`engine/src/program/generate.cpp:8243-8264`）。
- Batch MTP のコピーでは、`--batch-mtp`（または `STRATA_BATCH_MTP=1`）を使う batch 経路が必要です。CLI の説明では `--batch`、`--mtp`、`--spec` が条件として示されています（`engine/src/program/generate.cpp:1317-1322,17429-17433`）。
- `STRATA_MTP_MULTI_COPY` はこれらの機能を有効化しません。MTP や batch MTP の呼び出し自体がなければ、この値は読み取られず効果もありません。
- 呼び出し時に `n <= 0` なら helper は環境変数を読む前に戻ります。`n > 8` なら環境変数を読む前に stderr へ `copy_from_mapped_multi: at most 8 copies` を出し、終了コード 1 で終了します（`engine/src/kernels/cuda/elementwise.cu:423-427`）。現在の MTP 呼び出しは 2、3、6、7 件を渡します（`engine/src/core/mtp.cpp:1612-1615,2665-2666,2703-2718`）。

## 実行時の詳細

値は `copy_from_mapped_multi` の呼び出しごとに `getenv` され、関数内 static cache はありません。CUDA 実装では unset または先頭文字が `0` 以外のとき、`MappedCopy` 配列をローカル構造体へコピーし、最大コピー長から grid を決めて 1 launch の `copy_from_mapped_multi_kernel` に渡します。各 copy は 16-byte alignment と word 数が 4 の倍数かで `float4` または `int32` のコピーを選びます（`engine/src/kernels/cuda/elementwise.cu:403-413,438-447`）。

先頭文字が `0` のときは各入力を順に個別の kernel として stream に積みます。`words > 1024` かつ 4 の倍数、src/dst が 16-byte aligned なら `copy_from_mapped`、それ以外は `copy_i32_from_mapped` を使います（同:415-420,428-436）。コピー元・先は同じ `MappedCopy` 配列で、ここで変わるのは launch と要素幅の選択です。

通常の MTP では `capture_round` が round graph をまだ持たないときだけ graph capture を行い、その中で 7 入力コピーを記録します。round graph は `round_exec_` / `round_exec_c_` に保持され、以降は既存 graph を使います（`engine/src/core/mtp.cpp:1595-1616`）。pipeline 用の `prepare_chain` も graph を事前 capture します（同:2091-2097）。Batch MTP は key に対応する graph が未作成の場合にのみ capture し、作成済みなら保存済み graph を返します（同:2674-2732）。そのため設定の切替えが効くのは helper が次に呼ばれる時点であり、すでに capture 済みの graph のコピー経路は環境変数の変更だけでは差し替わりません。関数の呼び出し時にプロセス環境を読むため、読み取り前のプロセス環境変更は反映されます。

## ログと測定値

この変数の値を報告する Strata の通常実行ログ、警告、invalid-value エラーはありません。`n > 8` の共通上限エラーはありますが、現在列挙した MTP 呼び出しの件数では発生しません（`engine/src/kernels/cuda/elementwise.cu:423-427`）。`docs/DETAILS.md` にこの変数の測定値や性能比較は見当たらず、ここでは速度・出力同一性を測定したとは述べません。

## 根拠

- `engine/src/kernels/cuda/elementwise.cu:403-447` — CUDA multi kernel、値判定、個別 copy 経路。
- `engine/src/core/mtp.cpp:1595-1631,1865-1896,2091-2097` — MTP round の capture と再利用、および draft からの呼び出し。
- `engine/src/core/mtp.cpp:2665-2669,2674-2732` — batch MTP のコピーと graph cache。
- `engine/src/program/generate.cpp:1317-1322,8243-8265,17429-17433` — MTP / batch MTP の CLI 条件と利用箇所。
- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:894-920` — SYCL 版 helper に当該環境変数の読み取りがないこと。
- `engine/src/kernels/verify_parity.cpp:107-162` — テスト専用 parity code が変数を設定・復元して両経路を検査する箇所。本番挙動の根拠には使用していません。
