# `STRATA_Q36_READ_WINDOWS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Qwen 3.8 Flash Next engine の batch serving で、あるセッションのプロンプトを複数チャンクに分けて処理するとき、隣り合うチャンクの間にほかの active session の decode window を最大何回実行するかを指定します。decode 中のセッションがない場合や、処理中のチャンクが最後の場合、この値による window 実行はありません。

## 値と判定

`Serve` のコンストラクターで `std::getenv("STRATA_Q36_READ_WINDOWS")` を一度読みます。未設定なら `read_windows` の初期値 `1` が使われます。設定されていれば `std::atoi` で整数に変換し、その結果を 0〜64 に clamp します。

| 環境変数 | `read_windows` |
|---|---:|
| 未設定 | 1 |
| 空文字、数値に変換できない文字列 | 0 |
| 先頭から変換できる整数がある文字列 | その整数を 0〜64 に clamp |

`atoi` による変換のため、文字列全体の妥当性検査はありません。例えば `4tail` は 4、`-2` は 0、`100` は 64 になります。空白や符号を含む入力も `atoi` の整数変換規則に従います。値の大文字小文字判定はありません。

## 有効になる条件

- Qwen 3.8 Flash Next engine の serving 経路であること（`Serve` の生成時に値を読みます）。
- 少なくとも2つの session が設定されていること。1 session の engine は `BGEN` / `BGENI` を拒否します。
- プロンプト読み込み中に別 session が active であること。
- 現在処理した prompt chunk が最後の chunk ではないこと。

値が 0 なら chunk 間に別 session の window を実行しません。正の値でも、active session がなくなると window loop はそこで止まります。`BGEN` / `BGENI` の prompt に加え、別 batch slot が active の間に処理する `GEN` / `GENI` の複数 chunk prompt にも適用されます。active slot のない単独 prompt や serving 以外の評価用 `process()` 呼び出しでは callback が window を挟まないため影響しません。

## 実行時の詳細

`Engine::process()` は prompt を `tmax` ごとの chunk に分けます。各 chunk の処理後、serving request の callback は、prompt の残りがある場合に control queue を確認し、active session があれば `read_windows` 回を上限として `window()` を呼びます。`window()` は active slot 全体の次 token を進め、batch MTP が有効で条件を満たすと `window_mtp()` を使います。各 window の token は通常の `BT` protocol line として出力されます。

設定は `Serve` インスタンス生成時に整数へ変換され、そのインスタンスの member に保持されます。したがって serving 中にプロセス環境を変更しても再読み込みされません。`STRATA_Q36_READ_WINDOWS` 固有のログ、警告、エラー出力はありません。

## 文書の記載と制限

`docs/QWEN36.md` は、3,008-token prompt の例で、既定値では prompt の6 chunksの間に各 decode slot が20 tokens、`STRATA_Q36_READ_WINDOWS=4` では prompt read が 0.95 s から 1.14 s に伸びる一方で65 tokens進むと記載しています。この記載は資料にある測定結果の紹介であり、本調査では再測定していません。同資料のこの例には、その測定に使った GPU や全設定の記載がありません。

## 根拠

- `src/qwen35/q36_engine.cu:3171-3192`: batch protocol の説明、既定値、環境変数の読み取りと clamp。
- `src/qwen35/q36_engine.cu:2430-2488`: prompt の chunk 処理と、各 chunk 後の callback。
- `src/qwen35/q36_engine.cu:3348-3398,3428-3445,3544-3557`: active session の window、`BGEN` の受付条件、prompt chunk 間での window 実行。
- `src/qwen35/q36_engine.cu:3880-3886`: serving 経路と batch MTP の初期化。
- `docs/QWEN36.md:52-63`: batch serving の説明と `STRATA_Q36_READ_WINDOWS` の測定記載。
