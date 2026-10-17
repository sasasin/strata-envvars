# `STRATA_SPLIT_WAIT_MS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。Strata 所有ソースを対象とし、外部ライブラリや GPU driver の動作は含めない。

## 役割

層分割した GPU 検証 window で、前段ステージから hand-off データが届くのを後段 GPU が待つ時間の上限をミリ秒で指定します。この待ちは `STRATA_SPLIT_OVERLAP` による重ね合わせ経路で使われます。値は待ちに使う nanoseconds に変換され、上限を超えると hand-off エラーを記録します。

## 値と判定

`src/core/verify.cpp` のグローバル初期化で `std::getenv()` を一度呼び、設定値は `std::atoll()` で変換します。文字列全体の検証、範囲検査、clamp、無効値の警告はありません。

| 環境値 | 実装上の結果 |
|---|---|
| 未設定 | 30000 ms（既定値） |
| `0` | 0 ns。GPU の hand-off wait に時間上限を設けない |
| 空文字、数値で始まらない文字列 | `atoll` が 0 を返すため、上限なし |
| 整数で始まり後ろに文字がある値（例: `12ms`） | `atoll` が読んだ整数部分（例: 12）を ms として使う |
| 負数 | `atoll` の負の結果を unsigned に変換してから 1,000,000 を掛けるため、通常の負の timeout にはならず unsigned 演算値になる |

先頭の空白や符号を含む整数は `atoll` の変換規則に従います。`atoll` の変換可能範囲外の値について Strata 側のエラー処理はありません。また、ミリ秒から nanoseconds への unsigned 乗算にも overflow 検査がありません。

## 有効になる条件

値が実際に待ち時間を変えるのは、層分割の後段 stage に入力 hand-off flag があり、`Verifier::run()` が GPU graph に hand-off wait を挿入する経路です。`chain_overlap()` が true になるには、後段 verifier、対応する hand-off buffer と flag があり、隣接 stage が異なる GPU にあり、次 stage が PLE stage でない必要があります。`generate.cpp` は `STRATA_SPLIT_OVERLAP` が要求され、同一 GPU 分割ではなく、`--pipeline-windows` が 0 のときに overlap 用 flag を割り当てます。

`STRATA_SPLIT_WAIT_MS` 自体は機能を有効化しません。分割が通常の逐次 hand-off なら、この timeout の読み取り結果は使用されません。`batch_rec_` の経路では `wait_handoff()` 呼び出しが省かれます。

## 実行時の詳細

値は `src/core/verify.cpp` の namespace-scope `g_split_wait_ns` 初期化時に読み込まれ、プロセス内で保持されます。したがって実行中の環境変更は反映されず、各 window ごとの再読込もありません。

後段 stage の graph は `wait_handoff()` を実行し、GPU kernel が flag の値を待ちます。timeout が 0 なら時刻を見ずに flag を待ち続けます。非ゼロなら GPU 時刻で経過を計り、指定値を超えた時点で mapped error word を 1 にして戻ります。kernel はその後も graph の残りを完了させますが、host は同期後に error word を確認し、その window を使わずに失敗を返します。エラー文字列は `verify: layer split: the hand-off into layer <開始層> did not arrive within <値> ms (STRATA_SPLIT_WAIT_MS); the window was not used. STRATA_SPLIT_OVERLAP=0 runs the serial order` です。

この GPU 側 timeout は host 側の各層待ち（20 秒）より長い既定値 30 秒を持つ backstop です。Strata の `docs/MULTI_GPU.md` は通常は host 側の待ちが先に window を終了し、GPU wait を解放すると説明しています。これは通常の停止検出順序の説明であり、GPU timeout の値を変更するものではありません。

## 根拠

- `src/core/verify.cpp:450-456` — 既定値、`atoll`、ms から ns への変換、namespace-scope 初期化。
- `src/core/verify.cpp:1077-1083` — 後段入力の取り込み前に hand-off wait を graph へ追加する箇所と `batch_rec_` 条件。
- `src/kernels/cuda/verify_kernels.cu:1183-1198,1232-1235` — GPU timeout 判定、エラーワード設定、wait kernel の起動。
- `src/core/verify.cpp:2605-2611,2864-2880,2903-2908` — error word の確認、エラー文、window を失敗扱いにする処理。
- `src/core/verify.cpp:2614-2617` — overlap chain の成立条件。
- `src/program/generate.cpp:8448-8469` — `STRATA_SPLIT_OVERLAP` と pipeline 条件、flag の割り当て。
- `docs/MULTI_GPU.md:218-239` — overlapped hand-off の説明と timeout の既定値・host wait との関係。測定値は本変数の評価に使っていない。
