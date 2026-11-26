# `STRATA_FOLLOW_LOGPOS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` の decode verify window で、`STRATA_FOLLOW` から読み込んだ強制 continuation がある場合に、各 window の有効行について forced token の log-probability などをファイルへ追記する診断・測定用の出力先です。CUDA/HIP は `engine/src/program/generate.cpp`、SYCL は `engine/sycl/src/program/generate.cpp` で読み取ります。変数単独では出力せず、forced continuation を使う処理も通常の token 生成に置き換えません（CUDA/HIP: `engine/src/program/generate.cpp:21681-21708,23018-23040`、SYCL: `engine/sycl/src/program/generate.cpp:11750-11766,12780-12792`）。

## 値と判定

値は数値や真偽値として parse されず、ファイルパスとして `std::fopen(path, "ab")` に渡されます。`"ab"` は追記モードです。読み取り結果の `FILE*` は関数内 `static` に保持され、ファイルを開けなかった場合は null のままです。

| 実装 | unset | 空文字 | ファイルを開く条件 | 無効な値・開けないパス |
|---|---|---|---|---|
| CUDA/HIP (`engine/src/program/generate.cpp`) | 出力先なし | `p[0] != '\0'` を満たさず出力先なし | 非空文字列。文字列全体を検証せずパスとして `fopen` する | `fopen` が失敗すると null。警告や fallback はない |
| SYCL (`engine/sycl/src/program/generate.cpp`) | 出力先なし | unset と区別されず `fopen("", "ab")` を試みる | `getenv` が null でないこと。値の文字列を検証せずパスとして `fopen` する | `fopen` が失敗すると null。警告や fallback はない |

したがって `1`、`true`、`0` なども特別扱いされず、その文字列をファイル名として使います。空白や大文字小文字の比較、パス形式の事前検査はありません。実行時にファイルを開けなかった場合も Strata 独自のエラーは出しません（CUDA/HIP: `engine/src/program/generate.cpp:21703`、SYCL: `engine/sycl/src/program/generate.cpp:11763-11766`）。この読み取り箇所には同名の CLI 上書きや別環境変数への fallback はありません。

## 有効になる条件

- 対応する CUDA/HIP または SYCL の server decode 実装を使うこと。ここで確認できる読み取りは `engine/src/program/generate.cpp` と `engine/sycl/src/program/generate.cpp` のみで、他 backend の実装は確認できません。
- `STRATA_FOLLOW` が有効で、decode loop が forced continuation を読み込めていること。CUDA/HIP は `STRATA_FOLLOW` の空でない値から読み込んだ行を comma-separated token ID として扱い、空行の request は force しません（`engine/src/program/generate.cpp:21686-21708`）。SYCL は同変数で指定されたファイルから整数を読み、読み込みに成功したファイルを削除します（`engine/sycl/src/program/generate.cpp:11754-11762`）。どちらも forced token がなければ本変数の出力処理には入りません。
- ファイルを開けていること。開けなければ log-probability 出力はスキップされます。
- `STRATA_LOGPOS_TOPK` は出力の追加列だけに関係します。`window_logprobs` が初回にこの値を `atoi` し、0〜256 に clamp した top-k token/log-probability 列を付けます。未設定は 0、空文字・非数値は `atoi` により 0、数値の後ろの文字列は変換後に無視され、負値は 0、256 超は 256 です（CUDA/HIP: `engine/src/core/verify.cpp:4504-4517`、SYCL: `engine/sycl/src/core/verify.cpp:3138-3150`）。この変数自体のパス判定には影響しません。

## 実行時の詳細

出力先は最初に該当する decode request の処理が通ったときに一度だけ `static` 初期化され、プロセス内で保持されます。以降の request ごとに環境変数を読み直したり、ファイルを開き直したりしません。環境変数が後から変わっても既存の `FILE*` には反映されません。ファイルは `"ab"` で開き、通常の既存内容を切り詰めずに追記します（CUDA/HIP: `engine/src/program/generate.cpp:21703`、SYCL: `engine/sycl/src/program/generate.cpp:11763-11766`）。

forced continuation がある request では、Strata は verify window を実行してから、対応する出力 token を forced token に置き換え、draft がその forced continuation と一致する範囲を判定します。出力対象はその window の有効行であり、実装は `a + 1` 行を `Verifier::window_logprobs` に渡します。CUDA/HIP では forced token が不足する行に `-1` を渡し、SYCL でも不足時に `-1` を設定します。`window_logprobs` は target ID が負または語彙範囲外の行を出力せず、その他の行について position、target ID、target の log-probability、argmax ID と log-probability、一致フラグなどを書き、`STRATA_LOGPOS_TOPK` が正なら top-k 列も追加して flush します。CUDA/HIP は extra-token 列の対象 ID に `248046` を渡しますが、SYCL は `-1` を渡すため extra 関連の2列は `NaN` になります（CUDA/HIP: `engine/src/program/generate.cpp:23031-23040`、`engine/src/core/verify.cpp:4482-4518,4520`、SYCL: `engine/sycl/src/program/generate.cpp:12780-12792`、`engine/sycl/src/core/verify.cpp:3116-3154`）。

出力記録は token 選択そのものを変える設定ではありませんが、`STRATA_FOLLOW` が有効な場合は同変数が forced continuation を decode loop の出力 token として使うため、通常の argmax と異なる token を出力し得ます。本変数が有効でも `STRATA_FOLLOW` が未設定、空、読み込み失敗、または当該 request に forced token がない場合、log-probability 行は書かれません。

## ログと測定値

出力ファイルを開けない場合の警告はありません。CUDA/HIP では `window_logprobs` が失敗した場合、stderr に `strata serve: STRATA_FOLLOW_LOGPOS: <error>` を出しますが、その失敗だけでは decode を中断しません（`engine/src/program/generate.cpp:23038-23040`）。SYCL では失敗時に stdout へ `ERR <error>` を出し、request 処理から `return 1` します（`engine/src/program/generate.cpp:4435-4465`、`engine/sycl/src/program/generate.cpp:12790-12792`）。両 backend の `window_logprobs` は head logits が無い場合に `window_logprobs: no head logits for this window` を返します。CUDA/HIP は logits copy 失敗時に `window_logprobs: the head logits copy failed` を返し、SYCL は SYCL exception を `window_logprobs: ` に続けた文字列へ変換します（`engine/src/core/verify.cpp:4452-4465`、`engine/sycl/src/core/verify.cpp:3109-3115,3156-3158`）。

Strata の設計資料にこの変数固有の性能測定値は見つかりませんでした。`terminal/tools/force_check.py` の decode score 経路は `STRATA_FOLLOW`、本変数、`STRATA_LOGPOS_TOPK=2` を設定してサーバープロセスを起動し、この出力を採取します（`terminal/tools/force_check.py:189-208`）。

## 根拠

- 候補名の実参照: `engine/src/program/generate.cpp:21703`、`engine/sycl/src/program/generate.cpp:11763-11766`。
- forced continuation と記録条件: `engine/src/program/generate.cpp:21681-21708,23018-23040`、`engine/sycl/src/program/generate.cpp:11750-11766,12780-12792`。
- 行の形式、top-k、flush: `engine/src/core/verify.cpp:4482-4520`、`engine/sycl/src/core/verify.cpp:3116-3154`。
- score 用プロセスへの設定例: `terminal/tools/force_check.py:189-208`。
- Strata 資料では `STRATA_LOGPOS_TOPK` が `docs/SETTINGS.md:158` に列挙されていますが、本変数そのものの説明や測定値は見つかりませんでした。
