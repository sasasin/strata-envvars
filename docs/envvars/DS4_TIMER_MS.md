# `DS4_TIMER_MS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Windows で `strata-dsv41` を起動するとき、`DS4_TIMER_MS` を正の整数に変換できれば `timeBeginPeriod()` に渡します。実装コメントでは、DS4 の CPU lane service thread が token 間に 20 µs sleep する一方、次 token の device wait が Windows の 15.6 ms tick を待つ場合があるとして、プロセス実行中の timer period を 1 ms にする目的を説明しています。これは `strata` 本体全般の設定ではなく、独立した DeepSeek-V4.1 実行ファイルの設定です。

## 値と判定

値は文字列全体との比較ではなく `std::atoi()` で `int` に変換し、変換後が `0` より大きいときだけ API を呼びます。

| 環境の状態 / 例 | 処理 |
|---|---|
| 未設定 | `ms = 0`。呼び出さない |
| 空文字、数値に変換できない文字列 | `atoi()` の結果は `0`。呼び出さない |
| 正の数値文字列（例: `1`, `2`, `1ms`） | `atoi()` の結果が正なら、その整数を `UINT` に cast して `timeBeginPeriod()` に渡す |
| `0`, `-1`, `-2ms` | 結果が正でないため呼び出さない |

`atoi()` のため、先頭の空白や符号を含む文字列も数値変換規則に従い、数値の後ろにある文字列は検査されません。例えば `1ms` は `1` として扱われます。整数として変換できない入力は有効な設定エラーにはならず、`0` 扱いとなります。`atoi()` の `int` 範囲外入力の結果はコードで検査されていません。

根拠: `src/dsv41/ds4_os.hpp:45-50`。

## 有効になる条件

- `_WIN32` のときだけ環境変数を読み、`timeBeginPeriod()` を呼ぶコードがコンパイルされます。Windows 以外では `fine_timer()` は空関数です。
- `fine_timer()` は `strata-dsv41` の `main()` 冒頭から呼ばれます。`strata-dsv41` は CMake の `STRATA_BUILD_DSV41` オプションが有効な場合に作られる独立ターゲットで、このオプションは既定で `OFF` です。
- 値が正でも、`timeBeginPeriod()` の戻り値は確認・報告されません。値が不正または非正なら警告、エラー、代替設定を行う処理もありません。

根拠: `src/dsv41/ds4_main.cpp:1187-1189`, `src/dsv41/ds4_os.hpp:45-50`, `CMakeLists.txt:797-810`。

## 実行時の詳細

設定は `main()` の開始時に `fine_timer()` が一度実行され、その呼び出しの中で `getenv()` と `atoi()` により読み取られます。static cache は使われていませんが、プログラム中に同関数を再度呼ぶ箇所はありません。したがって、起動後に環境を書き換えても、この設定は再評価されません。

正の値では `timeBeginPeriod((UINT) ms)` を一度呼びます。Strata 側は呼び出し結果のログを出さず、対応する `timeEndPeriod()` 呼び出しもこのソースにはありません。実装コメントは 1 ms をプロセス実行中に使う意図を述べていますが、個々の Windows バージョンでの API の実効性やスケジューラの挙動はこの Strata コードからは確認できません。

根拠: `src/dsv41/ds4_main.cpp:1187-1189`, `src/dsv41/ds4_os.hpp:41-50`。

## 根拠

- `src/dsv41/ds4_os.hpp:41-50` — Windows 限定の判定と API 呼び出し、目的を説明するコメント。
- `src/dsv41/ds4_main.cpp:1187-1189` — `main()` 冒頭での呼び出し。
- `CMakeLists.txt:797-810` — `strata-dsv41` の説明、既定 OFF のビルドオプション、ターゲット生成。

`docs/DETAILS.md` と `src` / `docs` の完全一致検索では、この変数に関する追加の説明や測定条件は確認できませんでした。ヘッダーコメントにある「owner PC, shipped profile, 3 pairs」の比較結果は、測定条件の詳細をコードから確認できないため、性能上の効果としては記載していません。
