# `DF2B_HEAD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`metal/tests/df2_bench.cpp` の DFlash2 Metal ベンチマークで、head 行列の計測に `df2_mma8` 経路を使うかを切り替えます。`DF2B_HEAD=mma` の場合、このベンチマークは Q8_0 形式の合成 head データを作り、half 変換と `df2_mma8` dispatch を計測します。それ以外の値では通常の合成 head 行列を `DF2B_HEADR` で指定された `df2_mm` variant に渡します。

この変数の読み取りは `metal/tests/df2_bench.cpp` に限られます。同ファイルはベンチマーク用の `main` を実装しています。通常の Strata 実行経路がこの変数を読む根拠は見つかりませんでした。

## 値と判定

| 値 | 判定と処理 |
|---|---|
| 未設定 | 無効。通常の head 経路を使う |
| 空文字 | 無効。通常の head 経路を使う |
| `mma` | 有効。Q8_0 head 用の合成バッファを作り、`df2_mma8` 経路を使う |
| その他すべて | 無効。通常の head 経路を使う |

値は `std::string(getenv(...)) == "mma"` で文字列全体を大文字小文字を区別して比較します。数値変換、空白除去、部分一致、無効値の警告やエラーはありません。たとえば `MMA`、`mma `、`1` は有効になりません。未設定と明示的な空文字はいずれも条件を満たしません。

## 有効になる条件

- `metal/tests/df2_bench.cpp` から作られたベンチマークを実行する必要があります。これは Metal コンテキストを使うベンチマークで、通常の Strata CLI やサーバー機能を制御するものではありません。
- `DF2B_HEAD` の値が正確に `mma` である必要があります。
- `DF2B_ONLY` が `ctx`、`block`、`soak` の各モードでは head 計測を通りません。`head` モードでは head だけを計測し、それ以外の通常モードでは単独の head 計測と full round 内の head 計測に使われます。
- 有効時に使うカーネル variant は別の `DF2B_HEAD8` で選ばれ、未設定時の値は `1_8` です。通常経路では `DF2B_HEADR`（未設定時 `4_8`）が使われます。`DF2B_HEAD` 自体に CLI 引数による上書きはありません。コマンドライン引数は任意の kernel directory として処理されます。

## 実行時の詳細

変数は `main` の初期化中に一度評価され、`const bool HEADMMA` に保持されます。実行中に環境を変更して再評価する処理はありません。`HEADMMA` が真なら、ベンチマークはランダム値を埋めた Q8_0 head バッファを確保します。head 計測を組み立てる際、入力を `df2_f16` で half に変換し、`df2_mma8_<DF2B_HEAD8>` を dispatch します。偽なら通常の `mm(...)` 経路を使います。

観測可能な出力はデバイス名、共通設定行、各段階の GPU 時間・wall 時間の統計です。設定行に出る head variant は `DF2B_HEADR` の値であり、`DF2B_HEAD=mma` や `DF2B_HEAD8` の選択は表示されません。無効値に対する専用ログや Strata 側の fallback 通知はありません。GPU dispatch や Metal API の失敗時の扱いはこの変数の分岐からは確認できず、ここでは断定しません。

## 根拠

- `metal/tests/df2_bench.cpp:62-82` — ベンチマークの `main`、起動引数と関連環境変数の読み取り。
- `metal/tests/df2_bench.cpp:200-212` — `DF2B_HEAD` の完全一致判定、合成 Q8_0 head バッファの生成、`DF2B_HEAD8` の既定値。
- `metal/tests/df2_bench.cpp:391-416` — head 計測時の `df2_f16` / `df2_mma8` 経路と通常経路。
- `metal/tests/df2_bench.cpp:441-464` — 出力と `DF2B_ONLY` による head 計測の実行条件。
