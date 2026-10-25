# `STRATA_DF2_FORK`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DFlash2 drafter の GPU graph capture で、入力コンテキストの K/V 更新と draft block の計算を別々の GPU stream に分けるかを選びます。有効時は両方を並行して進め、draft block の各 layer の attention の前でその layer の K/V 更新完了を待ちます。無効時は同じ stream でコンテキスト更新を記録してから draft block を記録します。

これは DFlash2 経路内の実行方法を切り替える変数です。DFlash2 自体は CUDA/HIP build に含まれ、実行時にも `--draft dflash2` を指定した CLI 経路でのみ選択されます。

## 値と判定

`capture()` 内の関数ローカル `static const bool` に初回評価結果が保存されます。値は文字列全体や数値として parse せず、未設定・空文字なら backend ごとの既定値を使い、それ以外は先頭文字が `1` の場合だけ有効です。

| build | 未設定 | 空文字 | 非空値で有効 | 非空値で無効 |
|---|---:|---:|---|---|
| CUDA | 有効 | 有効（既定値） | 先頭文字が `1`（例: `1`, `10`, `1abc`） | 先頭文字が `1` 以外（例: `0`, `true`, ` 1`） |
| HIP | 無効 | 無効（既定値） | 先頭文字が `1`（例: `1`, `10`, `1abc`） | 先頭文字が `1` 以外（例: `0`, `true`, ` 1`） |

大文字小文字の変換、空白除去、文字列全体の検証はありません。したがって `true` は有効値ではなく、`1anything` は有効です。空文字は設定ありの明示的な OFF ではなく、既定値に戻ります。

## 有効になる条件

- `STRATA_HAVE_DFLASH2` が定義された CUDA/HIP build であること。CMake は CUDA または HIP が有効な場合に DFlash2 を含め、Metal/SYCL build では含めません。
- CLI で `--draft dflash2` 経路が選択されること。generate 側では MTP fallback と `--spec 2` 以上、native pack、単一 GPU の CLI 実行（`--serve` / `--batch` / layer split ではないこと）、`--draft-model` が必要です。これらを満たさない場合、DFlash2 は選択されず MTP を使います。
- 環境変数の判定結果が有効で、かつ `prof_ == nullptr` と `cs2_ != nullptr` であること。DFlash2 profile 経路は graph を使わず、fork もしません。通常の `load()` は二つの stream を作り、作成に失敗すると `dflash2: stream` エラーを返します。

CUDA では未設定時に fork を試み、HIP では未設定時に同一 stream の経路を使います。実装コメントは、測定結果を理由に HIP では一つの stream を既定としており、この変数で上書きできると説明しています。`STRATA_DF2_PROFILE` は `load()` 時に先頭文字 `1` で profile を有効にし、profile 時は後続処理で graph を作らないため、この変数の fork 効果はありません。

## 実行時の詳細

`Dflash2Drafter::capture()` が graph capture を行う際に環境変数を評価します。関数ローカル static のため、そのプロセスで最初にこの初期化式に到達した時点の値が保存され、以後の capture で環境を書き換えても再評価されません。profile 経路では `capture()` を呼ばず graph を使わないため、この設定は参照されません。

fork が有効なら、capture 中にメイン stream `cs_` から fork event を記録し、コンテキスト更新用 `cs2_` がその event を待ちます。`record_context()` は layer ごとの K/V ring 更新後に event を記録し、`record_block()` は各 layer の attention 前に対応する event を待ちます。最後にメイン stream がコンテキスト更新の join event を待ち、両側の処理が完了する graph を作ります。fork が無効なら `record_context()` と `record_block()` はともに `cs_` に記録されます。

この変数専用のログ出力はありません。DFlash2 が正常に選択・準備された場合は stderr に `strata generate: DFlash2 drafter on (...)` が出ますが、fork の ON/OFF を示す表示ではありません。stream / event 作成や graph capture 自体に失敗した場合は、それぞれ `dflash2: stream`、`dflash2: events`、`dflash2: capture: ...` などのエラー経路になります。

## 根拠

- `CMakeLists.txt:333-340` — DFlash2 を CUDA/HIP build に含める条件と `STRATA_HAVE_DFLASH2` の定義。
- `src/program/generate.cpp:5474-5518` — DFlash2 の選択条件、未選択時に MTP を fallback とする処理。
- `src/program/generate.cpp:16136-16165` — verifier の taps 設定、DFlash2 bind/prepare、準備成功ログ。
- `src/core/dflash2.cpp:195-224` — stream の作成、profile の判定。
- `src/core/dflash2.cpp:346-372,375-437` — context K/V 更新と block attention の layer event。
- `src/core/dflash2.cpp:440-473` — backend 別既定値、環境変数の判定、fork/join event と graph capture。
- `src/core/dflash2.cpp:476-485,504-535` — profile 時は graph capture を行わず、通常時は graph を起動する経路。

`tools/dflash2/README.md` は DFlash2 の acceptance experiment を説明していますが、この環境変数の動作は規定していません。`docs/DETAILS.md` にも `STRATA_DF2_FORK` の個別説明は見当たらず、上記の挙動は対象 commit の実装に基づきます。
