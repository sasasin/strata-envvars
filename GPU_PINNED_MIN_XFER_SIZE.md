# `GPU_PINNED_MIN_XFER_SIZE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリや GPU runtime がこの変数をどう解釈するかは対象外。

## 役割

Strata は Linux の HIP ビルドで、`STRATA_ARENA_MMAP` が有効な場合に限り、この変数をエンジンプロセスの環境へ既定値として設定します。Strata のソースにこの変数を読み取る箇所や、その値を数値として解析する箇所はありません。実行時の値を判断するのは Strata のコードではなく、外部 runtime 側です。

## 値と判定

Strata が設定する条件と値は次のとおりです。

| 条件 | Strata の処理 |
|---|---|
| HIP 関連 macro（`STRATA_USE_HIP` または `STRATA_HIP_GFX906`）が定義され、Windows ではなく、`STRATA_ARENA_MMAP` の先頭文字が `1` | `setenv("GPU_PINNED_MIN_XFER_SIZE", "1000000", 0)` を呼ぶ |
| 上記以外 | この変数を Strata は設定しない |

`STRATA_ARENA_MMAP` は文字列全体ではなく先頭文字だけで判定されます。未設定・空文字・先頭が `1` 以外なら、この自動設定は行われません。`GPU_PINNED_MIN_XFER_SIZE` 自体には Strata 独自の値検査、変換、範囲制限、fallback はありません。`setenv` の第3引数が `0` のため、呼び出し時点ですでにこの変数が設定済みなら、その値は空文字を含め上書きされません。

## 有効になる条件

- 条件は `--mmap-experts` CLI オプションではなく `STRATA_ARENA_MMAP` の環境値です。両者は別の設定経路です。
- HIP macro のない CUDA ビルド、Windows ビルドでは、この自動設定コードはコンパイル時または OS 条件で除外されます。
- SYCL 側にも同じ条件と処理があります。そこでの適用も、実際に該当 HIP macro が定義され、かつ非 Windows である場合に限られます。
- サーバー設定の `env` にユーザーがこの変数を指定した場合、`serve/server.py` はその値をエンジン子プロセスの環境へコピーします。その値が既に存在するため、上記の自動設定はそれを保持します。直接エンジンを起動する場合も、起動元から継承した設定値が保持されます。

## 実行時の詳細

エンジンの `main` はバージョン表示だけの早期終了を除き、通常の引数処理に入る前にこの条件を評価します。したがってこの自動設定はプロセス起動時に一度だけ行われ、後から Strata が再評価する処理はありません。Strata 自身はこの変数の値をログに出さず、設定の成否に応じたエラーや警告も実装していません。

`src/program/generate.cpp` と `sycl/src/program/generate.cpp` のコメントは、AMD の file-backed arena で起きたホストメモリ問題への対応としてこの値を設定すると説明しています。`docs/AMD_HIP.md` は RX 6800 の単一報告で手動設定値 `1048576` を使った実験的回避策を記録しています。設定値の単位、runtime 内部での閾値処理、各値による効果は外部実装の挙動に属するため、ここでは Strata の動作として断定しません。

## 根拠

- `src/program/generate.cpp:1780-1788` — HIP macro と非 Windows の条件、`STRATA_ARENA_MMAP` の先頭文字判定、上書きなしの `setenv`。
- `sycl/src/program/generate.cpp:1661-1669` — SYCL 側の同じ条件と設定。
- `serve/server.py:2622-2638,6375-6426` — 設定ファイルの `env` を子プロセス環境へ追加し、その環境でエンジンを起動。
- `docs/AMD_HIP.md:244-265` — この変数を用いた単一環境の実験的報告と server JSON の設定例。これは runtime の挙動を Strata ソースで確認した根拠ではありません。
