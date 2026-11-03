# `STRATA_INJECT_FATAL_ONCE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。作業開始時の Strata status は `## main...origin/main`。

## 役割

`STRATA_INJECT_FATAL` によるテスト用 fatal GPU error 注入を、ファイルで一度だけに制限します。値は marker file のパスです。この変数だけを設定しても注入は起きず、`STRATA_INJECT_FATAL` の正数指定と、その値に達する fatal-check 呼び出しが必要です。実装は `src/program/generate.cpp` の `exit_if_gpu_fatal()` にあります。

## 値と判定

この変数は文字列として読み、数値変換やトリミングはしません。

| 値 | 判定と動作 |
|---|---|
| 未設定 | ファイル判定をせず、注入を発火する。 |
| 空文字 | `getenv()` は非 null ですが `*once` が false のため、ファイル判定をせず発火する。 |
| 空でない文字列 | その文字列をパスとして `fopen(path, "rb")` で開く。開けた場合は閉じて `fire=false` とし、注入を抑止する。開けなかった場合は `fopen(path, "wb")` を試み、作成できれば閉じるが、いずれの場合も `fire` は true のままなので今回の注入は発火する。 |

範囲・数値境界・大文字小文字の判定はありません。相対パスの基準はこのプロセスの作業ディレクトリです（`fopen` にパスをそのまま渡します）。ファイル作成に失敗しても注入を抑止する分岐はありません。

## 有効になる条件

- `STRATA_INJECT_FATAL` が未設定でないだけでは足りず、同変数を `std::atol` で変換した値が 0 より大きい必要があります。未設定は 0、変換できない文字列も `atol` の結果が 0 となり、注入分岐に入りません。正数の場合、プロセス内の `windows` カウンターが一致するチェックでこの変数が参照されます。
- その一致時に marker file が `"rb"` で開けると注入だけがスキップされ、その後通常の sticky GPU error 判定へ進みます。
- 実装は `src/program/generate.cpp` のデコード経路にあり、別の CLI 引数による上書きや、他環境変数による marker 判定の変更はありません。`STRATA_INJECT_FATAL` の値は最初のチェック時に `static const` としてキャッシュされますが、`STRATA_INJECT_FATAL_ONCE` は一致時ごとに `getenv()` されます。

## 実行時の詳細

通常の decode loop では、各 window の `ver.run()` 前に `exit_if_gpu_fatal("")` が呼ばれ、ここでテスト hook のカウントが進みます。検証・commit の失敗経路でも同じ関数が呼び出されます。指定回数に一致して marker file がまだ開けなければ、`exit_gpu_fatal()` が `injected (STRATA_INJECT_FATAL): an illegal memory access was encountered` を理由にエンジンプロセスを終了コード 3 で即時終了します。`STRATA_INJECT_FATAL_ONCE` が空または未設定の場合も同じ注入です。

発火時には stderr に `strata serve: fatal GPU error (...)`、stdout に `ERR fatal GPU error: ...` が出ます。Strata server はこの `ERR` を fatal GPU error として認識し、実行中の request を engine death として扱います（503）。次の request で engine を再起動し、同じ marker path が残っていて再び `"rb"` で開ければ、そのプロセスでは以降の該当注入を抑止します。これは Strata がファイルを確認・作成する動作の説明であり、GPU runtime の挙動については述べていません。

## 根拠

- 候補名の全参照は `src/program/generate.cpp:3157-3164` のコメントと直接読み取りだけです。helper 経由・動的な名前の渡し先はありません。
- `STRATA_INJECT_FATAL` の `atol`、プロセス内カウンター、ONCE marker の読み書き、注入理由は `src/program/generate.cpp:3153-3165`。
- `exit_gpu_fatal()` の stderr/stdout 文言と終了コード 3 は `src/program/generate.cpp:3146-3151`。window 前のチェックと失敗時・commit 後の呼び出しは `src/program/generate.cpp:18467-18470,18512-18516,18678-18681`。
- server が fatal 行を検出し engine death にする処理は `serve/server.py:1782-1791`、request の 503 は `serve/server.py:7986-7988`、engine 再起動時に同じ command を使う処理は `serve/server.py:1450-1467`。
- `docs/DETAILS.md` にこの変数の記載は見つかりませんでした。
