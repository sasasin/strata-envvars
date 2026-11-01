# `STRATA_BIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_BIN` は Strata engine の一般設定ではなく、SYCL のプロンプト回帰スクリプト `sycl/tools/test_prompt_deadlock.sh` が起動する実行ファイルのパスです。このスクリプトは `STRATA_BIN` を `BIN` に取り込み、その実行ファイルを `MODEL_ARGS` と固定引数で呼びます。server、CLI 本体、C++/SYCL engine にこの環境変数を読む実装は見つかりませんでした。候補一覧には同梱テストツール用の参照として該当します。

## 値と判定

| 状態 | スクリプトの判定・結果 |
|---|---|
| 未設定または空文字 | `${STRATA_BIN:-}` により `BIN` は空になり、使用法を表示して終了コード 2 |
| 非空だが実行可能ファイルでないパス | `[ -x "$BIN" ]` が偽となり、同じく使用法を表示して終了コード 2 |
| 非空かつ実行可能ファイル | `BIN` を実行対象にする。パス文字列自体の形式検証・変換・正規化はしない |

パスはスクリプト起動時の作業ディレクトリを基準に解決されます（例の `build-jit/strata`）。実行時は `"$BIN"` と引用されるため、パス内の空白は保持されます。値はスクリプト実行のたびに展開され、cache されません。環境変数を実行中に変えた場合の再評価処理はありません。根拠: `sycl/tools/test_prompt_deadlock.sh:14-18`。

## 有効になる条件

`sycl/tools/test_prompt_deadlock.sh` を直接実行し、`STRATA_BIN` が実行可能なファイルを指し、さらに `MODEL_ARGS` が空でない場合にだけ engine を起動します。script は backend や build macro を調べません。コメントは A750 の回帰スクリプトとして説明し、呼び出し例に SYCL 用のモデル引数を示しますが、どの実行ファイルが正しいかを `STRATA_BIN` 自体から判定する処理はありません。関連記述: `sycl/tools/test_prompt_deadlock.sh:2-12`、`docs/INTEL.md:511-515`。

## 実行時の詳細

起動したコマンドには、`MODEL_ARGS` の展開結果に続けて `--tokens-file "$HERE/data/prompt_deadlock_2744.tok" --max-new 4 --greedy` を渡し、標準出力と標準エラーを一時ファイルへまとめます。`MODEL_ARGS` は引用符なしで展開されるため、shell の単語分割と pathname expansion を受けます。`DEADLOCK_TIMEOUT` は別変数で、未設定または空なら `timeout` に `900` 秒を渡します。

コマンド終了後、終了コードより先に一時ファイル内の `^prefill  *2743 tokens` を検索します。一致すれば `PASS: the 2,743-token prompt was read (...)` を出して一時ファイルを削除し、終了コード 0 にします。一致しなければ engine の終了コードを含む `FAIL: no prefill line (engine exit code ...)` を表示し、末尾 5 行を出して一時ファイルを残し、終了コード 1 にします。したがって、script の PASS 条件は engine の終了コード 0 ではなく prefill 行の出力です。使用条件を満たさない場合の使用法表示と終了コード 2 も同じファイルにあります。根拠: `sycl/tools/test_prompt_deadlock.sh:16-25`。

## 根拠

- `sycl/tools/test_prompt_deadlock.sh:7-8,15-25` — 例、値の展開・検査、engine 呼び出し、観測可能な PASS/FAIL/usage 経路。
- `docs/INTEL.md:511-515` — このスクリプトを A750 prompt 回帰テストとして挙げる文書上の参照。
