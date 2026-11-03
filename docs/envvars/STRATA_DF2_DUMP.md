# `STRATA_DF2_DUMP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal backend の DFlash2 drafter が受け取った context tap rows と、指定 round の計算結果をバイナリファイルへ一度だけ書き出す診断用フックです。通常の生成結果を切り替える設定ではありません。CUDA/HIP 側ではなく、Metal の decode window に実装されています。

## 値と判定

| `STRATA_DF2_DUMP` の状態 | 動作 |
|---|---|
| 未設定 | パスは空のまま。行の収集もファイル書き出しも行わない。 |
| 設定値が空文字 | `getenv` 自体は成功し、関連する `STRATA_DF2_DUMP_ROUND` も読み得るが、空パスのため行収集・書き出しは行わない。 |
| 空でない文字列 | その文字列を出力パスとして保持し、指定 round の dump を試みる。文字列の trim・展開・形式検査はない。 |

round は `Df2` の初期値 `3` です。`STRATA_DF2_DUMP` が設定されているときだけ `STRATA_DF2_DUMP_ROUND` も読み、`std::atoi` で整数化します。未設定なら 3、空文字や数字で始まらない文字列は 0、先頭空白・符号は `atoi` の規則に従い、数値の後ろの文字は無視されます。値の範囲検査や clamp はありません。round counter は 0 から始まり、各 `draft()` の出力後・counter 増加前に比較されるため、既定値 3 は4回目の draft 呼び出しを指します。負値は通常の非負 counter と一致しません。

## 有効になる条件

- Metal backend の DFlash2 Drafter が使われ、pack が読み込まれて `Window::df2_bind()` に到達する必要があります。環境変数は bind 時に評価されます。Metal の `window.cpp` がこの実装を include しています（`metal/src/engine/window.cpp:238-246,3437-3438`）。
- DFlash2 の bind が成功し、指定 round の `draft()` まで到達する必要があります。Metal の Drafter は未 bind のまま prompt context を受け取った場合にも、その経路で bind します（`metal/src/engine/dflash2.inc:1057-1083`）。
- 変数を bind 後に設定・変更しても、その `Df2` インスタンスの保持値は再評価されません。別の CLI 引数によるパス上書きや子プロセスへの転送は、この実装にはありません。
- context tap rows の位置は 0 から欠けなく連続している必要があります。途中で期待位置と異なる `pos0` を受けると dump は失敗扱いになります。

## 実行時の詳細

bind 時に `STRATA_DF2_DUMP` を読み、存在すれば文字列を `dump_path` に保存します。空でない場合、prompt context と draft 時の新しい context rows を host 側 vector に追加します。指定 round の draft 計算後、全 context rows が 0 から連続していることを確認して `fopen(path, "wb")` で出力します。したがって、同じパスに既存ファイルがあれば切り詰めて書きます。

dump にはヘッダ、蓄積した taps、anchor embedding、mask embedding、最終 normalized rows、selector projection、top-16 候補、picked token と probability、vocabulary map（該当時）、draft head logits が含まれます（`metal/src/engine/dflash2.inc:719-737`）。成功時 stderr に `strata metal: STRATA_DF2_DUMP: <行数> context rows and the answer of round <番号> written to <パス>` を出します。位置が連続しない場合は `strata metal: STRATA_DF2_DUMP: the context rows are not 0..<s>, nothing written`、ファイルを開けない場合は `strata metal: cannot write <パス>` を出します。これらは dump の失敗ログで、関数は `false` を返さず、生成をこの理由だけで中断しません。呼び出し側は試行後にパスを空にするため、再試行もしません。書き込み件数の戻り値検査はありません。

## 根拠

- `metal/src/engine/dflash2.inc:116-121` — dump 状態と既定 round 3。
- `metal/src/engine/dflash2.inc:282-287,405-412` — bind と環境値の読み取り時期。
- `metal/src/engine/dflash2.inc:683-716,740-766` — context/draft rows の収集と位置連続性チェック。
- `metal/src/engine/dflash2.inc:719-738,789-797` — round 判定、バイナリ出力、ログ、試行後の無効化。
- `metal/src/engine/window.cpp:3437-3438` — Metal window からの実装 include。
- `tools/dflash2/check_metal_dump.py:1-11,32-56` — dump の利用目的とフォーマットの読み取り（環境変数の挙動自体の根拠は実装）。

`docs/DETAILS.md` にはこの変数の追加説明は見つかりませんでした。候補一覧には `STRATA_DF2_DUMP_ROUND` もありますが、この調査文書の対象外です。
