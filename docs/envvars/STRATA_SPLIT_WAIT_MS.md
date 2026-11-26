# `STRATA_SPLIT_WAIT_MS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

異なる GPU に分けた layer split で stage 間の処理を重ねるとき、後段 GPU の graph が前段からの hand-off flag を待つ時間の上限をミリ秒で指定する。未設定時は 30000 ms、`0` は上限なし。待ち時間を変えるだけで、split の有効化や実行順序はこの変数では選ばない。値は `engine/src/core/verify.cpp` のプロセス内定数に読み込まれ、CUDA の `wait_handoff` に渡される（`engine/src/core/verify.cpp:658-664,1642-1649`）。

## 値と判定

`std::getenv` が null の場合だけ既定値 30000 を使い、設定値は `std::atoll` で変換する。変換エラーの検査、範囲チェック、clamp、警告はない。`atoll` は十進数の先頭部分を読むため、先頭の空白と符号を許し、最初の非数字以降は無視する。数字が始まらない文字列や空文字は 0 になる。その結果は `unsigned long long` に変換してから `1000000` 倍され、ns 単位で GPU wait に渡される（`engine/src/core/verify.cpp:661-664`）。

| 条件 | unset | 設定時に有効になる値 | 境界・無効値の例 |
|---|---|---|---|
| 通常の CUDA / HIP 経路 | 30000 ms | `250` → 250 ms、`  +12tail` → 12 ms | `0`、空文字、`true`、`0anything`、数字で始まらない文字列 → 0（無期限）; `-1` は符号付き値から unsigned へ変換されるため巨大な上限になる |
| HIPCC の Windows build | まず同じ変換（既定 30000 ms） | カーネルに変換後の ns 値を渡す | カーネルが 0 または 1.2 秒超を 1.2 秒に制限するため、0 を指定しても無期限にはならない（`engine/src/kernels/cuda/verify_kernels.cu:1417-1422`） |

正の値の後ろに単位を付けても全体の妥当性は検証されず、たとえば `250ms` は 250 として扱われる。負値を含め、`atoll` の戻り値が `long long` の範囲外になる入力は安全な設定値として定義されていない。設定値に対して Strata が無効値の警告を出す処理はない（`engine/src/core/verify.cpp:661-664`）。

## 有効になる条件

- Engine が CUDA/HIP の verifier 経路を使い、layer split の次 stage に hand-off flag が設定されている必要がある。後段 graph は `hflag_in_d_ != nullptr && !batch_rec_` のときだけ `wait_handoff` を呼ぶ（`engine/src/core/verify.cpp:1642-1649`）。
- overlapped hand-off は `STRATA_SPLIT_OVERLAP` が非ゼロで、同一 GPU split ではなく、`--pipeline-windows` が 0 のときだけ選ばれる。`STRATA_SPLIT_OVERLAP` の判定は `atoi != 0`（`engine/src/program/generate.cpp:13351-13362`）。したがって `STRATA_SPLIT_WAIT_MS` 単独では overlapped hand-off は有効にならず、serial split や pipeline-windows の独自 hand-off 待ちにはこの値は適用されない。
- `--pipeline-windows` が正のときに `STRATA_SPLIT_OVERLAP` も指定されていると、Strata は `STRATA_SPLIT_OVERLAP is off beside --pipeline-windows ...` と stderr に出して overlap を無効にする（`engine/src/program/generate.cpp:13358-13362`）。
- HIPCC の Windows build では GPU wait の上限は 1.2 秒。これは環境変数値が 0 または 1.2 秒超でも適用される（`engine/src/kernels/cuda/verify_kernels.cu:1417-1422`）。

## 実行時の詳細

値は `verify.cpp` の namespace static 初期化ラムダで一度読み取られ、プロセス実行中に環境を変更しても再読込されない（`engine/src/core/verify.cpp:661-664`）。overlapped split では後段の graph 内で hand-off flag が 1 以上になるまで GPU が spin wait し、指定時間を超えると `herr_d_` に 1 を記録して wait を抜ける。タイムアウト後も graph 内の後続 kernel は実行されて stream を完了させる。host 側は stream sync 後に `handoff_failed` を確認し、その window を失敗扱いにする（`engine/src/kernels/cuda/verify_kernels.cu:1414-1433,1467-1469`; `engine/src/core/verify.cpp:1647-1649,4130-4139,4163-4167`）。

## ログと測定値

hand-off timeout が確認されると、`handoff_failed` は次のエラー文字列を作る。これは環境変数値を記録した起動時ログではなく、失敗した window のエラー経路である（`engine/src/core/verify.cpp:3696-3702`）。

```text
verify: layer split: the hand-off into layer <layer> did not arrive within <ms> ms (STRATA_SPLIT_WAIT_MS); the window was not used. STRATA_SPLIT_OVERLAP=0 runs the serial order
```

`strata generate` の呼び出し側は window 失敗時に `strata generate: <error>` を stderr に出す（`engine/src/program/generate.cpp:25130-25140`）。serve の decode window 呼び出し側は `ERR <error>` を stdout に出してその処理から失敗を返す（同 `22990-22993`）。timeout 自体を知らせる専用ログは `handoff_failed` にはなく、error 文字列に timeout と設定名が含まれる。Strata の資料にはこの変数に対応する性能測定値はない。

## 根拠

- `engine/src/core/verify.cpp:658-664` — 未設定既定値、`atoll`、ns 変換、static cache。
- `engine/src/core/verify.cpp:1642-1649` — 後段 stage の graph が hand-off を待つ条件と timeout 値の引き渡し。
- `engine/src/kernels/cuda/verify_kernels.cu:1414-1433,1467-1469` — flag wait、timeout 時の error flag、後続処理と HIP Windows 上限。
- `engine/src/core/verify.cpp:3696-3702,4130-4139,4163-4167` — timeout error と window 失敗判定。
- `engine/src/program/generate.cpp:13351-13362,22990-22993,25130-25140` — overlap の有効条件と caller 側の失敗表示。
