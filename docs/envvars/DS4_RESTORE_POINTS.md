# `DS4_RESTORE_POINTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジンが、通常の会話 checkpoint 3 個に加えて保持する restore point の最大数を指定します。restore point は GEN 要求が指定した `marks=` / `tail=` / `shared=`（`pin=`）の位置で会話状態を保存し、後続 prompt の再利用時に戻れる地点です。この変数はエンジン側の上限を設定する fallback 名です。優先名は `STRATA_DS4_RESTORE_POINTS` です。

## 値と判定

エンジンは `STRATA_DS4_RESTORE_POINTS` が設定されているかを先に調べ、未設定の場合だけ `DS4_RESTORE_POINTS` を読みます。選ばれた文字列を `std::atoi` で変換し、結果を `0..16` に clamp します。両方未設定なら既定値は `4` です (`src/dsv41/ds4_model.cu:7167-7174`; 上限 `src/dsv41/ds4_marks.hpp:19-20`)。

| 状態・値 | エンジンの上限 |
|---|---:|
| `STRATA_DS4_RESTORE_POINTS` と `DS4_RESTORE_POINTS` が unset | 4 |
| 優先名が unset、`DS4_RESTORE_POINTS` が空文字 | 0 |
| 文字列が整数として始まる | `atoi` の変換結果を 0..16 に clamp（例: `5x` は 5、`-2` は 0、`99` は 16） |
| 数字で始まらない文字列 | `atoi` の結果 0 |
| 優先名が設定済み | その値を採用。空文字や不正値も fallback 名へは切り替えず、変換結果 0 になる |

`atoi` は文字列全体の厳密な検証をせず、先頭の空白や符号を許し、数値の後ろの文字を無視します。整数型の範囲に収まらない文字列の結果はこの実装から保証できません。無効値に対する警告やエラー出力はありません。

## 有効になる条件

- 上限は `maya-ds4 serve` の DeepSeek-V4.1 実行経路で使われます。サーバーも restore key を作るのは family が `deepseek41` の場合だけで、画像を含む要求では作りません (`serve/server.py:5714-5725`)。
- 上限が 0 でも常設の checkpoint 3 個は別に残ります。0 になるのは要求された追加 restore point の保持数です (`src/dsv41/ds4_model.hpp:237-249`)。
- 上限が正でも、GEN 要求に restore point の位置がなければ追加 point は作られません。エンジンは要求位置を `mark_plan` に渡し、その read が通る地点で状態を保存します (`src/dsv41/ds4_main.cpp:1146-1183,1260-1268,1296-1303`)。
- サーバー経由では `strata_prefix` が設定されている場合、または `STRATA_DS4_RESTORE_SHARED=0` の場合、サーバーは自動生成した `shared` point を取り除きます (`serve/server.py:5724-5730`)。
- 上限 0 の場合、DeepSeek サーバーの共有 prefix 保存も無効になります。正数の場合も `STRATA_DS4_PREFIX_KEEP`, `STRATA_DS4_PREFIX_GB`, `STRATA_DS4_PREFIX_MIN` の設定に従います (`src/dsv41/ds4_main.cpp:804-806,824-827`)。
- `STRATA_DS4_REUSE=0` は要求間の再利用全体を無効にする別設定です。その場合、この上限が正でも restore point による再利用は行われません (`src/dsv41/ds4_main.cpp:563,1042-1045`)。

## 実行時の詳細

上限値は `marks_cap()` 内の function-local `static const int` に保存され、プロセス内の初回評価後は再読込されません。サーバーエンジンの起動処理で `m.marks_cap()` が prefix 上限の算出に使われるため、通常は要求処理より前に評価されます (`src/dsv41/ds4_model.cu:7167-7174`; `src/dsv41/ds4_main.cpp:804-806`)。

上限に達した後、新しい restore point を保持するときは、共有 start ではない point のうち最も長く使われていないものを先に置き換えます。共有 start しかない場合はその中の LRU を置き換えます。各 point は `Check` 状態を持ち、保存サイズは `check_bytes()` に含まれます (`src/dsv41/ds4_model.cu:7181-7200`; `src/dsv41/ds4_marks.hpp:120-136`; `src/dsv41/ds4_model.hpp:245-249`)。

サーバーの自動 key 生成は別に `STRATA_DS4_RESTORE_POINTS` を読み、既定値 4、`int` 変換後の下限 0 で有効/無効を決めます。`DS4_RESTORE_POINTS` alias は Python 側では読まれません (`serve/server.py:761-770,5718-5725`)。従って alias だけを設定した場合もエンジンの上限は変わりますが、サーバーの key 生成条件は既定の `STRATA_DS4_RESTORE_POINTS` 側で決まり、通常の既定値 4 では位置付き key を生成し得ます。優先名に不正文字列がある場合、Python はその変数を既定値 4 として扱う一方、C++ の `atoi` は 0 にするため、key を送ってもエンジンが保持しない場合があります。

この変数固有のログ、無効値警告、終了・失敗経路はありません。保持数の変更による再利用可否が実行上の結果です。調査対象の `docs/DETAILS.md` にはこの設定値の説明や測定結果は見つかりませんでした。

## 根拠

- 環境値の優先順、既定値、変換、clamp とキャッシュ: `src/dsv41/ds4_model.cu:7167-7174`。
- 上限と restore point の選択、共有 start の保持優先: `src/dsv41/ds4_marks.hpp:19-20,43-70,120-136`。
- point の作成・置換・既存 checkpoint との関係: `src/dsv41/ds4_model.cu:7181-7200`; `src/dsv41/ds4_model.hpp:237-250`。
- 要求位置の採用、prompt read 中の保存: `src/dsv41/ds4_main.cpp:1146-1190,1260-1303`。
- サーバー側の独立した設定判定と DeepSeek/画像条件: `serve/server.py:761-770,5691-5699,5714-5730`。
- 通常の checkpoint 再利用と `STRATA_DS4_REUSE=0`: `src/dsv41/ds4_main.cpp:1042-1091`。
