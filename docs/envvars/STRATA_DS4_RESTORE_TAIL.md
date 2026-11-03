# `STRATA_DS4_RESTORE_TAIL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 のサーバーが、長い prompt の末尾から何 token 手前に restore point を要求するかを指定します。サーバーは値を prompt ごとに読み、条件を満たすと `tail=<位置>` を engine の `GEN` 行へ加えます。engine はその位置まで prompt を読んだ時点の状態を restore point として保持し、後続の prompt がそこから続く場合に再利用できるようにします。C++ engine はこの環境変数自体を読みません。

## 値と判定

サーバーの `restore_point_settings()` は `str(value).strip()` を `int()` に渡し、負数を `max(0, ...)` で 0 にします。未設定時の既定値は `512` です。空文字・空白だけ・整数に変換できない文字列は `ValueError` となり、既定値 `512` に戻ります。空白で囲んだ整数や符号付き整数は受け付けられます。上限 clamp はありません。

| 値 | 判定結果 |
|---|---|
| unset | 512 token |
| `512`、`+512`、` 512 ` | 512 token |
| `0`、負数 | 0。tail point を要求しない |
| 空文字、空白のみ、`x`、`1.5` など | 変換失敗として 512 token |
| 任意の非負整数 | prompt の末尾からその token 数前を候補位置にする。上限なし |

この値だけでは restore point を有効化しません。別変数 `STRATA_DS4_RESTORE_POINTS` がサーバー側で正数と判定されることも必要です（既定値 4）。

## 有効になる条件

- `serve/server.py` の `Service.set_restore_points()` が使われる DeepSeek-V4.1 のリクエストであること。その他の model family では読み取った設定を適用しません。
- リクエストに画像がないこと。DeepSeek の画像も対象外です。
- `STRATA_DS4_RESTORE_POINTS` が正数で、tokenizer から user-turn token を得られ、prompt が少なくとも 2 token あること。
- 候補位置 `len(ids) - tail` が 1024 以上で、最後の user/system turn の位置より後にあり、tail が 0 より大きいこと。したがって短い prompt、末尾に近すぎる user turn、`tail=0` では tail key を作りません。
- engine 側の restore point 上限が 0 より大きいこと。`STRATA_DS4_RESTORE_POINTS` は engine で `DS4_RESTORE_POINTS` より優先され、どちらも未設定なら上限 4 です。server 側で restore points を有効にしていても、`DS4_RESTORE_POINTS=0` かつ `STRATA_DS4_RESTORE_POINTS` 未設定なら engine 側の上限が 0 となり、restore point は処理されません。

候補位置は `mark_plan()` に渡され、prompt の終端より前か、現在の読み取り位置以降か、他の mark と十分離れているかなどの規則でさらに選別されます。engine の既定 `STRATA_DS4_RESTORE_TAIL_AUTO` は有効です。tail point の停止コストが測定上、通常読みより高いと判断された場合は要求を省きます。`STRATA_DS4_RESTORE_TAIL_AUTO=0` はその自動除外を無効にします。この別変数は unset でも自動判定が有効です。

## 実行時の詳細

サーバーは各リクエストの `Service.prepare()` から `set_restore_points()` を呼び、`restore_point_settings()` で `os.environ` を再評価します。値を static cache するコードはありません。設定値が有効なら prompt token ID 列から最後の user turn 等を調べ、条件に合う tail 位置を `_restore` に格納します。`StrataEngine.restore_keys()` は正の位置を `tail=<位置>` として `GEN` の sampling key に追加し、engine の `parse_gen()` が `atoll()` で読み取ります（この場合、Python が生成した十進整数が渡ります）。`STRATA_DS4_RESTORE_TAIL` は engine の環境へ値として転送されるのではなく、要求ごとの key に変換されます。

engine は `marks_cap() > 0` の場合にだけ要求位置を plan に渡します。自動判定が許せば prompt read はその位置で止まり、`m.mark()` が状態を保存します。後続 prompt の再開では、engine は利用可能な checkpoint / mark から再利用位置を選び、そこへ状態を復元します。自動判定が有効なときは、tail の読み取りコストを計測し、2 回の測定後に比率が 2 を超えた場合、次回以降は通常 tail を省き、32 回に 1 回を再測定用に残します。計測結果に応じて stderr に `ds4 serve: the tail restore point is left out on this PC: ...` または `ds4 serve: the tail restore point is kept...` が出ます。前者は engine process あたり一度だけです。値の変換失敗や 0 について、この環境変数専用の警告・終了経路はありません。

## 根拠

- `serve/server.py:753-770` — 既定値、値の整数変換と clamp、`STRATA_DS4_RESTORE_POINTS` との有効判定。
- `serve/server.py:773-804` — tail 候補位置の計算、1024 token の最小位置、user turn と重なる候補の除外。
- `serve/server.py:5691-5699,5714-5730` — `prepare()` からの呼び出し、DeepSeek-V4.1・画像なしの条件、設定に基づく `_restore` 作成。
- `serve/server.py:1630-1644` — `_restore` の tail を `GEN` key に変換。
- `src/dsv41/ds4_main.cpp:462-510` — engine の GEN key parser と `tail` の `atoll()` 変換。
- `src/dsv41/ds4_main.cpp:536-542,1153-1183,1282-1294` — 別変数 `STRATA_DS4_RESTORE_TAIL_AUTO` の既定動作、tail 候補の採否・計測・ログ。
- `src/dsv41/ds4_model.cu:7165-7173` — engine 側 restore point cap と `STRATA_DS4_RESTORE_POINTS` / `DS4_RESTORE_POINTS` の優先順位。
- `src/dsv41/ds4_model.cu:7202-7214,7247-7256` — checkpoint / mark の選択と状態復元。
- `src/dsv41/ds4_marks.hpp:37-70,73-110` — mark の選別条件と tail cost の自動判定規則。
