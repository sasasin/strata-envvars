# `STRATA_DUMP_SEL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の prompt prefill で、最終 chunk における最初の QSA layer の選択 cell ID と各位置の選択幅をバイナリファイルへ出力する診断用変数。attention の入力となる選択結果を記録するだけで、選択や生成の計算を変更しない。`Prefill::run_impl` 内で、QSA attention を実行する直前に読み取り・出力する（`engine/sycl/src/prefill/prefill.cpp:2693-2700, 3849-3873`）。

## 値と判定

`std::getenv` の戻り値を関数内 `static` ポインターに一度保存し、null かどうかだけで有効性を判定する。内容の parse、空白除去、大文字小文字比較、数値変換はしない。未設定（null）は無効。空文字を含め、設定されていれば出力先パスとして扱う。空文字は `fopen` に渡されるが通常開けず、出力も成功ログもない。`fopen` が成功する文字列なら、相対パスはプロセスの作業ディレクトリから解決される（`engine/sycl/src/prefill/prefill.cpp:3854-3862, 3869-3870`）。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL の prompt prefill が該当 QSA 箇所に到達 | 出力しない | `fopen(path, "wb")` が成功する任意のパス文字列。例: `sel.bin`、`/tmp/sel.bin` | 値の形式による無効値判定はない。`fopen` に失敗するパス（空文字を含む）は出力しない |

## 有効になる条件

- `engine/sycl` の prefill 実装を使う実行経路であること。CUDA 実装や decode の各 token 処理からこの変数を読む箇所はない（この名前の実行時読み取りは `engine/sycl/src/prefill/prefill.cpp:3856` のみ）。
- モデルの prefill に QSA layer があり、そのうち `qsa_index == 0` の layer の処理まで到達すること。`qsa_index` は現在の stage より前にある QSA layer 数から始まるため、モデル全体の最初の QSA layer だけが対象（`engine/sycl/src/prefill/prefill.cpp:3027-3029, 3559-3562`）。
- 現在の chunk が prompt の最終 chunk であること（`c0 + T >= n`）。最終 chunk の全 `T` 位置を記録する（`engine/sycl/src/prefill/prefill.cpp:2826-2829, 3854-3856`）。
- 出力先を `wb` で開けること。別の CLI 引数や環境変数による上書き条件はこの処理にない。

## 実行時の詳細

環境値は条件式に初めて到達した時に `static const char*` として評価され、その後は再度 `getenv` しない。したがって同じプロセス内で後から環境を変更しても、この箇所は値を読み直さない（`engine/sycl/src/prefill/prefill.cpp:3856`）。

条件成立時、まず SYCL queue を待ち、device 上の `m.sel_ids`（`T * cap` 個）と `m.steps_dev`（各位置の step 情報）を host にコピーして待機する。ファイルを `"wb"` で開き、順に `int32_t` のヘッダー `{T, cap}`、`T * cap` 個の cell ID、各位置の `kStepWidth` の値を `T` 個書く。`fopen` が成功すれば毎回同じファイルを切り詰めて出力するため、複数回の prefill では以前のダンプを上書きする。`fopen` 失敗時は何も書かず、明示的なエラー処理もない。`fwrite` の戻り値も確認しない。出力後の attention 計算は通常どおり続く（`engine/sycl/src/prefill/prefill.cpp:3856-3874`）。

## ログと測定値

ファイルを開けた後に書き込み処理を通ると、stderr に `strata: selection of %lld positions dumped to %s\n`（実際の `%lld` は `T`）を出す。ファイルを開けなかった場合のこの変数固有の警告・エラー出力はない。測定値を示す Strata 資料は該当しない（`engine/sycl/src/prefill/prefill.cpp:3861-3870`）。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:2693-2702` — SYCL `Prefill::run_impl` の実装。
- `engine/sycl/src/prefill/prefill.cpp:2826-2829` — prompt を chunk 単位で処理し、`T` と `n` を定める。
- `engine/sycl/src/prefill/prefill.cpp:3027-3029, 3559-3562` — QSA layer index と QSA 処理。
- `engine/sycl/src/prefill/prefill.cpp:3854-3874` — 変数の読み取り、対象条件、バイナリ出力、ログ、および後続 attention。
