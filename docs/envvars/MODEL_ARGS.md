# `MODEL_ARGS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`MODEL_ARGS` は Strata engine 全体の設定ではなく、SYCL の prompt deadlock 回帰スクリプト `sycl/tools/test_prompt_deadlock.sh` に engine 引数を渡すための環境変数です。候補一覧にはこの同梱スクリプト用の参照として該当します。候補名の全参照を調べた範囲では、engine 本体、server、他の Strata ソースが `MODEL_ARGS` を環境から読む箇所は見つかりませんでした。スクリプトのコメントは A750 の回帰テストとして説明していますが、実装は backend やデバイスを判定しません（`sycl/tools/test_prompt_deadlock.sh:2-12,15-18`）。

## 値と判定

| 状態 | スクリプトの判定・結果 |
|---|---|
| 未設定 | `${MODEL_ARGS:-}` は空になり、使用法を表示して終了コード 2 |
| 空文字 | 空として扱われ、同じく使用法を表示して終了コード 2 |
| 非空文字列 | `STRATA_BIN` も実行可能ファイルを指す場合、engine 起動引数として展開する |

文字列の形式、個々の option、値域はスクリプト内で検証・変換されません。変数は引用符なしで展開されるため、shell の単語分割と pathname expansion が行われます。内容を別の shell コマンドとして評価する処理はありません。値はスクリプトの起動時に参照され、cache や起動後の再読込処理はありません（`sycl/tools/test_prompt_deadlock.sh:13-18`）。

## 有効になる条件

`MODEL_ARGS` が非空であることに加え、`STRATA_BIN` が非空で実行可能ファイルを指す必要があります。どちらかを満たさないと使用法 `usage: STRATA_BIN=<strata> MODEL_ARGS="..." $0` を表示して終了コード 2 で終わります。script は OS/backend/build macro、モデル状態、engine option の妥当性を確認しません（`sycl/tools/test_prompt_deadlock.sh:15-16`）。

## 実行時の詳細

スクリプトは `$MODEL_ARGS` の展開結果の後ろに `--tokens-file "$HERE/data/prompt_deadlock_2744.tok" --max-new 4 --greedy` を追加して `"$BIN"` を実行し、stdout と stderr を一時ファイルにまとめます。別変数 `DEADLOCK_TIMEOUT` は未設定または空文字なら `900` を `timeout` に渡します（`sycl/tools/test_prompt_deadlock.sh:14,17-19`）。

engine 終了後は終了コードより先に、一時ファイルに `^prefill  *2743 tokens` があるかを調べます。一致すれば PASS を表示して一時ファイルを削除し、script は終了コード 0 になります。一致しなければ engine の終了コードを FAIL メッセージに含め、出力末尾 5 行を表示して一時ファイルを残し、script は終了コード 1 になります。したがって、このスクリプトの PASS 条件は engine の終了コードではなく prefill 行の出力です。これは回帰スクリプトの判定であり、`MODEL_ARGS` 自体が engine の成功や特定の計算動作を保証するものではありません（`sycl/tools/test_prompt_deadlock.sh:18-26`）。

## 根拠

- `sycl/tools/test_prompt_deadlock.sh:2-12` — A750 の prompt deadlock 回帰テストというコメント、呼び出し例、スクリプトの説明。
- `sycl/tools/test_prompt_deadlock.sh:13-18` — unset/空判定、起動条件、引数展開、固定引数と timeout。
- `sycl/tools/test_prompt_deadlock.sh:19-26` — prefill 行による PASS/FAIL 判定、表示内容、終了コードと一時ファイルの扱い。
- `docs/INTEL.md:511-515` — 同スクリプトを A750 prompt hang の回帰テストとして挙げる記述。
