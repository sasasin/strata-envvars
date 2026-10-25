# `STRATA_NAN_INJECT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA verifier の非有限 logits ガードを試験するデバッグ用フックです。指定したウィンドウ番号で、実際に logits が有限でも row 0 を非有限として記録します。これにより、serve / batch 側のエラー処理経路を人工的に起動できます。実際の logits やサンプリング結果を書き換える処理ではありません。

## 値と判定

値は最初に `Verifier::note_nonfinite()` がガード有効・head stage で呼ばれたときに一度読み取られ、`static const std::vector` に保存されます。以降の環境変更は反映されません。

| 設定 | 動作 |
|---|---|
| unset / 空文字 | 対象番号なし。注入カウンターは進まない |
| 正の10進整数（例: `1`） | その番号のウィンドウを注入対象にする |
| カンマ区切りの正整数（例: `1,60`） | 複数のウィンドウを対象にする |
| 0または負数 | 数値として読み取られるが、対象リストには入らない |
| 数値として読めない文字列の先頭 | 解析をそこで終了し、それ以降は無視 |

各項目は `strtoll(..., 10)` で読みます。先頭の空白や符号は `strtoll` の規則で許容され、変換後に `n > 0` のものだけを採用します。数値の後がカンマなら次の項目へ進み、それ以外なら同じ位置から次の変換を試みます。したがって `1x,2` は `x` で次の変換に失敗して終了し、`2` は採用されません。オーバーフロー時の `errno` は確認していません。重複番号は許容されます。

## 有効になる条件

- `STRATA_NAN_GUARD` が有効であること。ガードは未設定なら有効で、`std::atoi(value) != 0` で判定されます。従って `STRATA_NAN_GUARD=0` や空文字では無効です。
- `note_nonfinite()` が呼ばれること、mapped flag 領域 `h_nf_` が存在すること、Verifier が head を持つ最終 stage であること。
- まだリストに指定番号が残っていること。

`STRATA_NAN_GUARD=0` の場合、または head stage 以外・flag 領域なしの経路ではカウンターは進みません。実測フラグが既に非有限を示すウィンドウでは、注入で row 0 を追加設定せず、注入ログも出しません。実装根拠は CUDA verifier (`src/core/verify.cpp`) です。SYCL 実装にこの変数の読み取りは見つかりませんでした。

## 実行時の詳細

カウンターは `src/core/verify.cpp` 内のプロセス共有 atomic で、1から始まります。番号は verifier の呼び出し回数ではなく、ガードが実際に確認した各ウィンドウに割り当てられます。呼び出し元には通常の verify、batch slot、pipelined window があり、プロンプト末尾・decode・batch のウィンドウが同じカウントに含まれます。候補番号に達し、実際の非有限フラグがなければ、`nf_mask_` の bit 0 を立て、stderr に次の形式で出します。

```text
strata verify: STRATA_NAN_INJECT: window <番号> reported as non-finite
```

その後は通常のガード結果と同じ `nonfinite_row()` / `nonfinite_in()` 経路を使います。serve の通常リクエストでは当該ウィンドウの token を出力せず `DONE ... nonfinite` とし、batch では該当 slot を終了して `BDONE ... nonfinite` を出します。ログと結果の根拠は `src/program/generate.cpp` にあります。

## 資料との照合

`docs/DETAILS.md` は `STRATA_NAN_INJECT=<n>[,<n>...]` を、プロンプト末尾・decode・batch を通した engine process 内のウィンドウ番号を非有限として報告させる debug switch と説明し、`=1,60` の試験例を記載しています。本調査で確認した実装のカウント条件は上記のとおりで、ガードを無効にした場合や head stage でない場合は番号に含まれません。性能・正確性の測定値はこの変数について記載しません。

## 根拠

- 値の読み取り、`strtoll` による解析、リストの static cache、process-wide カウンター、注入条件と stderr: `src/core/verify.cpp:3115-3154`。
- ガードの既定と `STRATA_NAN_GUARD` の判定、GPU 側チェックの記録: `src/core/verify.cpp:1794-1795,3106-3113`。
- 非有限状態を公開する API と対象ウィンドウの説明: `include/strata/core/verify.hpp:100-112`。
- verifier の各呼び出し元: `src/core/verify.cpp:2343,2877,2941,3098,3416`。
- serve / batch で非有限結果を処理する箇所: `src/program/generate.cpp:7991-8000,9438-9445,11668-11678,11942-11949`。
- 文書上の debug switch と試験例: `docs/DETAILS.md:767-771`。
