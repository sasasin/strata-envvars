# `STRATA_TAP_FILE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

speculative decode の CUDA `Verifier` が検証する各入力 token について、指定した層の完了出力をバイナリファイルへ記録する研究用フックです。層出力は residual にその層の FFN write を適用した値を hyper-connection stream 間で平均したものです。通常の生成設定を変える変数ではなく、Verifier の tap 用 GPU/host バッファを有効にし、window ごとの記録を追加します。

## 値と判定

`Verifier::init()` が環境変数を読みます。

| 値 | 動作 |
|---|---|
| 未設定 | ファイル出力用 tap は無効。`set_taps()` も指定されていなければ tap バッファを確保しない |
| 空文字 | 未設定と同じ扱い |
| 空でない文字列 | ファイルパスとしてそのまま使い、`STRATA_TAP_LAYERS` で指定された層を記録する |

値を真偽値や数値として parse しません。空でない値はパスです。ファイルは `fopen(path, "wb")` で開くため、同名ファイルがあれば上書きされます。開けない場合は verifier 初期化に失敗し、呼び出し元は `strata generate: verify: cannot write STRATA_TAP_FILE <path>` を stderr に出します。

対象層は別変数 `STRATA_TAP_LAYERS` で指定します。未設定または空文字なら `5,15,25,35,45` です。カンマ区切りの各要素を `atoi` で整数化し、`0 <= layer < n_layers - 1` の要素だけ採用します。このため数値の後ろの文字列は無視され、数値に変換できない要素は `0` になります。範囲外の要素は捨てられます。採用層が0個の場合や tap バッファを確保できない場合は `verify: the DFlash2 tap buffers could not be allocated` で初期化に失敗します。

## 有効になる条件

- `Verifier::init()` を通る speculative decode の実行経路で使われます。通常の非 speculative decode だけではこの Verifier の記録処理は呼ばれません。
- 層範囲がモデル全体（`lb_ == 0 && le_ == g.n_layers`）である必要があります。layer split の段 verifier では、この環境変数による記録を有効化しません。
- Metal ビルドでは `Verifier::init()` が Metal window 初期化へ先に分岐して戻るため、この CUDA 実装の環境変数読み取り・ファイル出力には到達しません。
- `STRATA_TAP_LAYERS` はこの変数の対象層指定に使われます。DFlash2 drafter が `set_taps()` を指定する経路も同じ tap buffer を使いますが、`STRATA_TAP_FILE` が空ならその別経路の層指定が優先され、ファイルは作りません。
- batch verifier の記録では `batch_rec_` が true の間 tap 取得・ファイル書き出しを抑止します。

## 実行時の詳細

非空パスの場合、初期化時に層一覧を作り、device tap buffer、scratch buffer、mapped host buffer を確保してからファイルを開きます。ファイル先頭には4個の `int32`（magic `0x50415453`、version `1`、embedding 次元 `n_embd`、tap 数）を書き、その後に tap 層番号を `int32` で並べます。各 window の record は各行について `int32` の position、`int32` の入力 token、その後に `tap数 * n_embd` 個の `float` です。値はコードが書き込む順序の説明であり、ソースは別途 byte order やファイル互換性を規定していません。

`record_window()` は指定層の完了出力を GPU buffer に保存します。DFlash2 kernel がビルドに含まれる場合は `df2_tap_gr` を使い、含まれない場合は stream copy、`gr_write`、`hc_mean_streams` の経路を使います。ファイル出力が有効なときは window の出力コピーを mapped host buffer に行い、`run()` が verifier window を実行・同期して出力 token を読み取った後、各行をファイルへ追記して `fflush()` します。各行の token はその window に入力された `tokens[t]` で、位置は `pos0 + t` です。

ヘッダーと row の `fwrite()`、および `fflush()` の戻り値は検査されていません。初期化後の書き込みエラーを verifier のエラーとして報告する処理は確認できません。明示的な終了処理ではファイルを閉じます。

## 根拠

- `src/core/verify.cpp:695-720`: verifier 初期化と Metal 早期分岐。
- `src/core/verify.cpp:785-820`: 環境変数・層リストの parse、適用範囲、バッファ確保、ファイル作成、ヘッダー、初期化ログ。
- `src/core/verify.cpp:664-674`: row の position/token/tap 書き込みと flush。
- `src/core/verify.cpp:2203-2215`: tap の完了出力取得と DFlash2 kernel / fallback。
- `src/core/verify.cpp:2345-2346, 3193-3200`: mapped buffer へのコピー、および window 後のファイル書き込み。
- `src/core/verify.cpp:633-636`: file と tap buffer の解放。
- `src/program/generate.cpp:16095-16140`: speculative decode ループ内での Verifier 初期化。
- `tools/dflash2/README.md:7-10`: 研究用 dump と出力内容の説明。`docs/DETAILS.md` に本変数の追加説明や測定値は見つかりませんでした。
