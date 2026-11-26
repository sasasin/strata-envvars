# `STRATA_LOGPOS_EXTRA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_LOGPOS` が出力する prompt の teacher-forced log-probability 行に、指定 token ID の log-probability と、その token の確率質量を除いた正解 token の log-probability を追加するための token ID を指定する。既定値は `248046`（コードコメント上の `<|im_end|>`）である。対象コードは CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` にあり、どちらもサーバーの prompt verify windows を読む経路で使われる。値は診断出力の計算だけに渡され、生成 token や verifier の採用結果を変更しない（`engine/src/program/generate.cpp:20453-20467`、`engine/sycl/src/program/generate.cpp:11303-11317`、`engine/src/core/verify.cpp:4482-4503`）。

## 値と判定

両実装とも `std::getenv` で取得し、未設定なら `248046`、設定されていれば `std::atoi` の結果を `int32_t` にして使う。文字列全体の検証、clamp、別値への fallback はない。`atoi` は先頭の空白と符号を許し、先頭から数値として読める部分を変換するため、`"  -3tail"` は `-3`、`"17x"` は `17`、空文字や数字で始まらない文字列は `0` になる。大文字小文字の区別は該当しない。変換結果が token ID として語彙範囲外なら、その追加 log-probability 欄は `NaN` になる。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 系・SYCL 系共通 | `248046` | 語彙サイズを `V` としたとき `0` から `V-1`。例: `0`、`248046`（そのモデルの語彙内の場合） | 負値、`V` 以上。例: `-1`、`V`。変換後に範囲外なら追加欄は `NaN` |

明示的な空文字、`abc`、`0anything` は `atoi` により `0` となるため、token ID 0 が語彙内なら有効な ID である。`1` と `true` はそれぞれ ID 1 と 0 として扱われ、真偽値として判定されない。整数の後ろに続く文字は無視される。`atoi` の整数型の範囲を超える入力は C/C++ の変換規則で結果が保証されないため、使用可能な境界値として扱えない（読み取りコードに範囲検査はない）。根拠: `engine/src/program/generate.cpp:20461-20464`、`engine/sycl/src/program/generate.cpp:11311-11314`、範囲判定と出力は `engine/src/core/verify.cpp:4482-4503`、`engine/sycl/src/core/verify.cpp:3116-3137`。

## 有効になる条件

- `STRATA_LOGPOS` が設定され、その値で追記モード (`"ab"`) の出力ファイルを開ける必要がある。未設定または `fopen` が失敗した場合は `logpos == nullptr` となり、`window_logprobs` は呼ばれず、この変数の値は出力に影響しない。空文字なら空のパスが `fopen` に渡され、戻り値が null のときは同じく行出力されない（`engine/src/program/generate.cpp:20457-20465`、`engine/sycl/src/program/generate.cpp:11307-11315`）。
- サーバーの prompt が `read_windows` の verify-window 経路を通る必要がある。バッチ化された `read_part` 経路ではこの箇所の行出力は行われない（`engine/src/program/generate.cpp:21551-21555`、`engine/sycl/src/program/generate.cpp:11642-11653`）。
- `STRATA_LOGPOS` があると、パイプラインの prompt windows も並列の `read_windows_pl` を避けて serial な窓読み取りへ進む。これはログ取得側の条件であり、`STRATA_LOGPOS_EXTRA` 自体がこの経路を選ぶわけではない（`engine/src/program/generate.cpp:20416-20419`、`engine/sycl/src/program/generate.cpp:11277-11281`）。
- CLI 引数や別設定による `STRATA_LOGPOS_EXTRA` の上書きはこの読み取り箇所にはない。値は各 backend の `read_windows` 内の function-local `static const` として初回到達時に一度だけ読み取られ、その後の環境変更は同プロセス内で反映されない。CUDA/HIP 系と SYCL 系では別々の実行ファイル・実装に属する（同上）。

## 実行時の詳細

各 verify window の `ver.run` 後、prompt の次 token ID 配列 `nxt` を教師あり正解として `window_logprobs` に渡す。この関数は head logits を読み、各行について通常の正解 token の log-probability、top token、指定 token ID の log-probability、指定 token ID の確率質量を除いて再正規化した正解 token の log-probability を TSV 行に出す。指定 ID が語彙範囲外なら指定 token の欄は `NaN`、正解 token 自身が指定 ID の場合は「除外後」の欄も `NaN` になる。各行の出力後に flush する。`STRATA_LOGPOS_TOPK` が有効なら上位 token 欄も追加されるが、これは別変数の制御である（`engine/src/core/verify.cpp:4482-4521`、`engine/sycl/src/core/verify.cpp:3116-3155`）。

ログ計算が失敗すると窓読み取りが失敗する。CUDA/HIP 系では `strata serve: <error>` を stderr、`ERR <error>` を stdout に出す失敗経路があり、SYCL 系にも同形式の serve エラー出力がある（`engine/src/program/generate.cpp:20465-20467, 21593-21596`、`engine/sycl/src/program/generate.cpp:11315-11317, 11659-11662`）。ファイルを開けない場合はこの変数に関する明示的な警告はなく、logprob 行も書かれない。

## ログと測定値

Strata の `docs/DETAILS.md`、`docs/QUANTS.md`、`docs/UNSLOTH_Q4.md` は `STRATA_LOGPOS` による log-probability 計測を説明するが、`STRATA_LOGPOS_EXTRA` 固有の測定値は記載していない。ソースコメントが示す用途は `<|im_end|>` の確率質量を別欄に出し、その質量を除いた正解 token の値を得ること。コメント以外に、この変数による性能・精度の測定結果は確認できない。関連する出力形式と測定手順の資料: `docs/QUANTS.md:56-66`、`docs/UNSLOTH_Q4.md:224-226`。

## 根拠

- `engine/src/program/generate.cpp:20416-20419, 20453-20467` — CUDA/HIP 系の prompt window 経路、ログ出力ファイルと環境変数の読み取り。
- `engine/sycl/src/program/generate.cpp:11277-11281, 11303-11317` — SYCL 系の対応経路。
- `engine/src/core/verify.cpp:4435-4466, 4482-4521` — CUDA/HIP 系の log-probability 算出、語彙範囲判定、TSV 出力と flush。
- `engine/sycl/src/core/verify.cpp:3105-3115, 3116-3158` — SYCL 系の同処理。
- `engine/src/program/generate.cpp:21551-21555, 21593-21596`、`engine/sycl/src/program/generate.cpp:11642-11662` — window 経路の呼び出しと失敗表示。
- `docs/QUANTS.md:56-66`、`docs/UNSLOTH_Q4.md:224-226` — 関連する Strata の計測方法。
