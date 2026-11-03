# `DS4_MARKS_INSIDE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 (`strata-dsv41`) の prompt 読み込みで、複数の復元点（restore point）を個別に止めながら保存する代わりに、残りの prompt を一度に読み、読み込み途中の状態をまとめて保存する経路を許可します。これは prompt 処理の経路選択です。通常の読み込み結果そのものを変更する設定とは説明されていません。

`DS4_MARKS_INSIDE` は旧名として読み取られます。優先名は `STRATA_DS4_MARKS_INSIDE` で、優先名が未設定のときだけ `DS4_MARKS_INSIDE` が参照されます。

## 値と判定

| `STRATA_DS4_MARKS_INSIDE` | `DS4_MARKS_INSIDE` | 判定 |
|---|---|---|
| 未設定 | 未設定 | 有効（既定） |
| 未設定 | 設定あり | `std::atoi` の結果が 0 でなければ有効 |
| 設定あり | 任意 | `std::atoi` の結果が 0 でなければ有効。旧名は参照しない |

選ばれた値は文字列全体との比較ではなく `std::atoi` で整数化されます。したがって空文字、整数に変換できない文字列、先頭の整数部分が 0 の値（例: `0`, `0tail`）は無効になり、非ゼロの整数部分を持つ値（例: `1`, `-1`, `2tail`）は有効になります。`atoi` に渡す文字列の厳密な妥当性検査や明示的な範囲制限はありません。

`STRATA_DS4_MARKS_INSIDE` が空文字で設定されている場合も優先名が選ばれ、その `atoi` 結果が 0 となるため無効です。旧名に `1` を設定しても上書きされません。

## 有効になる条件

値が有効でも、`Model::marks_inside()` は `chunk` が正、restore point の相対位置 `rel` が空でなく、点の数が snapshot 上限内（snapshot は 8 枠なので内側の点は最大 7 個）、最初の点が読み込み先頭より後、最後の点が末尾より前の場合にだけ追加判定へ進みます。さらに、long prompt の skip（YOCO）が成立し、その各 restore point 間で一括読み込みが余分に処理する行数を合計した `inner_cost` が `chunk` 以下の場合に限り `true` を返します。計算では各区間の `len - keep` が 1024 行以上の場合だけその行数を加算します。YOCO が無効、対象レイヤー配置が不適合、またはコストが上限を超える場合は一括保持を選びません。

呼び出し側にも条件があります。残りの prompt に未処理 restore point があり、`DS4_LAST_WINDOW` が未設定で、共有 prefix を先に止める／保持する状況でなく、今回の piece が残り全体を含み、残りの長さが `feed_unit()` 以下であるときだけ `marks_inside()` を問い合わせます。これらの条件外ではこの環境変数による経路選択は行われません。

CMake の `strata-dsv41` ターゲットは `STRATA_BUILD_DSV41` が有効な場合に追加され、この option の既定値は OFF です。該当ターゲットは CUDA/HIP を使う CMake 節内にあり、`STRATA_HIP_GFX906` では除外されます。環境変数の読み取り自体に別の backend や OS 分岐はありません。

## 実行時の詳細

読み取りは `Model::marks_inside()` 内の function-local `static const bool` で一度だけ評価されます。先行する chunk・restore point の形式チェックを通った最初の呼び出しで初期化され、以後同じプロセスで環境を変更しても判定は変わりません。CLI 引数や設定ファイルによる上書きは、この判定箇所にはありません。`STRATA_DS4_MARKS_INSIDE` が設定されている場合の優先と、未設定時に `DS4_MARKS_INSIDE` を読む順序は同関数内で決まります。

一括経路を選ぶと、呼び出し側は残っている restore point を `inner` に集め、`feed_marks()` で残り全体を読みます。成功時はそれらの点を読み込み中に保存済みとして扱い、次の point を末尾まで進めます。判定が偽なら、通常の feed / feed_mark 経路を使い、point ごとに停止して保存する処理が残ります。この環境変数専用のログや警告はありません。

読み込み自体が失敗した場合は通常の prompt エラー経路に入り、stderr に `ds4: <error>`、stdout に `ERR<tag> <error>` と `DONE<tag> ...` を出し、モデル状態を reset します。restore point の位置不正なら `feed_marks: a restore point that is not inside the read, or out of order` が返ります。これらは環境変数の値を直接報告する失敗ではありません。

## 根拠

- `src/dsv41/ds4_model.cu:14927-14937` — 先行条件、優先名と旧名の読み取り、既定値、`atoi` 判定、`inner_cost <= chunk`。
- `src/dsv41/ds4_main.cpp:1223-1263` — 呼び出し側の条件、一括経路の `feed_marks()`、成功時の restore point 消費。
- `src/dsv41/ds4_model.cu:12864-12889` — `inner_cost` と YOCO 適用条件。
- `src/dsv41/ds4_model.cu:804,1094` — snapshot 枠数（8）と YOCO skip をコストに数える最小行数（1024）。
- `src/dsv41/ds4_model.cu:14894-14925` — `feed_marks()` が点の位置・順序を検証し、chunk 経路または段階的 feed で保存する処理。
- `src/dsv41/ds4_model.hpp:136-145` — `feed_marks()` / `marks_inside()` の契約。
- `src/dsv41/ds4_main.cpp:1314-1342` — prompt 読み込み失敗時のログ、出力、reset。
- `CMakeLists.txt:931-945` — `STRATA_BUILD_DSV41` の既定値と `strata-dsv41` ターゲットの追加条件。
