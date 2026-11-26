# `STRATA_TEST_HANDOFF_DROP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 GPU の layer split を hand-off overlap 付きで実行するとき、指定した 1-based window で書き手側の通知 flag を立てず、読み手側の bounded wait が失敗を処理する経路を起こすテスト用フックである。モデル計算の通常設定ではない。環境変数を読むのは `engine/src/core/verify.cpp` のファイルスコープ初期化で、実際に通知を省くのは `engine/src/kernels/cuda/verify_kernels.cu` の hand-off publish kernel である（`engine/src/core/verify.cpp:665-670, 3003-3008`; `engine/src/kernels/cuda/verify_kernels.cu:1435-1453`）。

## 値と判定

値は `std::getenv` で一度読み、設定されていれば `std::atoll` で `int64_t` に変換する。未設定は 0。空文字、数字で始まらない文字列、`0` は変換結果が 0 となり無効である。`atoll` は文字列全体の厳密な数値検証ではないため、先頭の空白・符号の後に数字があれば数字部分を読む（例: `"  +2tail"` は 2）。正の変換結果だけが選択対象になり、負数は無効。正数に上限 clamp はなく、変換結果がその window 番号と一致したときだけ有効になる。大文字小文字は関係しない（`engine/src/core/verify.cpp:667-670, 3581-3585`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| hand-off overlap を使う書き手 stage | 0（無効） | `1` はその verifier の 1 番目、`2` は 2 番目の window | 空文字、`0`、`true`、`false`、`0anything`、`-1`、非数値文字列 |
| overlap なし、または対象 stage に outgoing hand-off がない | 0（無効） | なし | すべて。フック用 word が割り当てられず適用されない |

## 有効になる条件

- `engine/src/program/generate.cpp` の serve layer-split 経路で `STRATA_SPLIT_OVERLAP` が非ゼロとして解釈され、split が同一 device ではなく、`--pipeline-windows` が 0 であること。`STRATA_SPLIT_OVERLAP` の判定もファイル内 static lambda による `atoi` である。`--pipeline-windows` と併用した場合、Strata は `strata serve: STRATA_SPLIT_OVERLAP is off beside --pipeline-windows %d (that loop overlaps the stages itself)` を stderr に出し、ここで説明する overlap flag の設定は行わない（`engine/src/program/generate.cpp:13351-13371, 13383-13387`）。
- 対象 stage が別 stage へ hand-off すること。outgoing hand-off flag が設定された場合にのみ verifier の初期化で test word を割り当てる（失敗時の初期化エラーは `verify: hand-off test word allocation failed`）。そのため、値が正でも単一 GPU の通常実行、overlap 無効、終端 stage ではフックは動かない（`engine/src/core/verify.cpp:1238-1242`; `engine/src/program/generate.cpp:13363-13387`）。
- 読み手側は hand-off の ready word を待つ GPU graph を実行する必要がある。読み手の wait timeout は `STRATA_SPLIT_WAIT_MS` から設定され、未設定時 30000 ms、0 は無期限（ただし Windows HIP は kernel 内で 1200 ms に上限）。対象変数自体はこの timeout を変更しない（`engine/src/core/verify.cpp:658-664, 1642-1649`; `engine/src/kernels/cuda/verify_kernels.cu:1414-1432`）。

## 実行時の詳細

`g_test_drop` は `verify.cpp` の namespace スコープで一度初期化されるため、プロセス起動後の環境変更は反映されない。各 window の入力 staging 時に outgoing hand-off を持つ verifier は mapped test word を `g_test_drop > 0 && windows + 1 == g_test_drop` のとき 1、それ以外は 0 にする。したがって判定は verifier ごとの window counter に対して行われる（`engine/src/core/verify.cpp:667-670, 3581-3585`）。

overlap 有効時、書き手 stage は payload を mapped hand-off buffer に書き、全 CUDA blocks の payload write 後に test word を確認する。word が 1 なら ready flag の store を省き、0 または test word pointer が null なら flag を通常どおり 1 にする（`engine/src/core/verify.cpp:3003-3008`; `engine/src/kernels/cuda/verify_kernels.cu:1435-1453`）。

読み手 stage の graph は ready flag を待つ。期限までに flag が届かないと kernel は error word を 1 にし、その window の後続 kernel は実行を続けて graph を完了させる。host は window 同期後に error word を検出し、`verify: layer split: the hand-off into layer <layer> did not arrive within <ms> ms (STRATA_SPLIT_WAIT_MS); the window was not used. STRATA_SPLIT_OVERLAP=0 runs the serial order` を error として返し、stale hand-off の window を使用しない。経路によっては `run` から戻った後にも同じ hand-in error を確認する（`engine/src/kernels/cuda/verify_kernels.cu:1414-1432`; `engine/src/core/verify.cpp:3696-3702, 4137-4140, 4163-4168`）。

## ログと測定値

この変数を読み取った、または指定 window で通知を落としたことを示す専用ログはない。timeout 時は上記の hand-off error 文字列が返る。Strata のソースにこのフックの性能測定値は記載されていない（`engine/src/core/verify.cpp:3696-3702`; `engine/src/kernels/cuda/verify_kernels.cu:1444-1453`）。

## 根拠

- `engine/src/core/verify.cpp:665-670` — 値の読み取りと既定値。
- `engine/src/core/verify.cpp:1238-1242, 3003-3008, 3581-3585` — outgoing hand-off 用 word の割り当て、kernel 呼び出し、window 番号による設定。
- `engine/src/kernels/cuda/verify_kernels.cu:1414-1432, 1435-1453` — bounded wait と通知抑止。
- `engine/src/core/verify.cpp:3696-3702, 4137-4140, 4163-4168` — timeout の error と window を使わない処理。
- `engine/src/program/generate.cpp:13351-13371, 13383-13387` — serve layer-split の overlap 条件と設定。
