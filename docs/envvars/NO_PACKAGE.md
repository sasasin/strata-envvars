# `NO_PACKAGE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux AMD HIP 用の engine package build script で、engine component の package 化を省き、組み立て済みの stage folder を残して正常終了するための build-time 環境変数です。通常の Strata 実行時設定ではありません。対象は `packaging/build_hip_linux.sh` と `packaging/build_dsv41_hip_linux.sh` の二つです。

## 値と判定

両 script は `set -u` の下で、stage folder の準備と tuning table の処理を終えた位置で `[ -n "${NO_PACKAGE:-}" ]` を評価します。変数が未設定または空文字なら条件は偽で、package 化へ進みます。空でない値なら条件は真です。値の数値変換、文字列比較、許容値検証はありません。そのため `1` だけでなく `0`、`false`、その他任意の非空文字列でも package 化を省略します（`packaging/build_hip_linux.sh:116-123`; `packaging/build_dsv41_hip_linux.sh:74-81`）。

| `NO_PACKAGE` | 判定 | 結果 |
| --- | --- | --- |
| 未設定 | 偽 | 通常の package 化へ進む |
| 空文字 | 偽 | 通常の package 化へ進む |
| 空でない任意の文字列（`0` や `false` を含む） | 真 | `STAGE-DONE` を記録して終了コード 0 で終了 |

## 有効になる条件

- `packaging/build_hip_linux.sh` または `packaging/build_dsv41_hip_linux.sh` を実行し、stage 処理と tuning table 処理の後にある判定箇所まで進む必要があります。library collection の失敗は `chk`、tuning 処理の失敗は終了コード確認で script を終了するため、これらの失敗時は判定に到達しません。一方、stage directory 作成や `cp` にはこの箇所で個別の終了コード確認がありません（`packaging/build_hip_linux.sh:45-48,92-118`; `packaging/build_dsv41_hip_linux.sh:33-35,61-76`）。
- `build_hip_linux.sh` は `VISION_ONLY` が非空の場合、reader の build 後に `VISION-DONE` を記録して終了します。この経路は stage folder を作らず、`NO_PACKAGE` の判定にも到達しません（`packaging/build_hip_linux.sh:78-92`）。
- `build_hip_linux.sh` では判定時点までに `DSV41` が有効なら `strata-dsv41` も stage にコピーされています。`NO_PACKAGE` はその stage 一式を残してから package 化を省略します（`packaging/build_hip_linux.sh:41-42,92-118`）。専用の `build_dsv41_hip_linux.sh` では DeepSeek-V4.1 engine の stage を対象に同じ判定をします（`packaging/build_dsv41_hip_linux.sh:61-76`）。
- この名前の参照は上記二つの Linux HIP build script に限られます。Strata の実行時 engine、Windows/CUDA/SYCL の package script に同名の読み取りはありません（`rg -F 'NO_PACKAGE'` による候補名全体の確認）。

## 実行時の詳細

環境値は shell が script 内の条件を評価する際に参照されます。この変数専用に子プロセスへ値を export・転送する処理や、後から再評価・cache する処理はありません。非空なら、通常 `package_engine.py` を呼び出す直前に `st "STAGE-DONE"` を実行して終了します。`st` は時刻付きメッセージを `$OUT/build.status` に追記します（既定の `$OUT` は `build_hip_linux.sh` で `$PWD/work-$V`、専用 DSV41 script で `$PWD/work-dsv41-$V`）。この分岐は終了コード 0 であり、後続の `components` 作成、`package_engine.py` 実行、`BUILD-DONE` 記録を行いません（`packaging/build_hip_linux.sh:29,45-46,118-126`; `packaging/build_dsv41_hip_linux.sh:21,33-35,76-84`）。

## 根拠

- `packaging/build_hip_linux.sh:17` — script の用途説明。実際の値判定はコメントの `=1` 例ではなく、同ファイル `:118` の非空判定。
- `packaging/build_hip_linux.sh:78-92,107-126` — `VISION_ONLY` の早期終了、stage 作成、`NO_PACKAGE` 分岐、通常 package 化との順序。
- `packaging/build_dsv41_hip_linux.sh:10,61-84` — 専用 DSV41 script の stage 処理と同じ分岐。
- `packaging/build_hip_linux.sh:46-48`; `packaging/build_dsv41_hip_linux.sh:33-35` — build status への追記形式と先行処理の失敗記録。

`strata_control/engine_component.py` の `NO_PACKAGE_HIP` は同じ部分文字列を含む Python 定数名で、環境から `NO_PACKAGE` を読む処理ではありません。テストの参照も定数の確認です。環境値の読み取り根拠には含めていません。
