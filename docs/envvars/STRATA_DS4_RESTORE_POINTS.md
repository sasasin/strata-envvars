# `STRATA_DS4_RESTORE_POINTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の会話状態に、通常の 3 checkpoint に加えて保持する restore point の最大数を指定します。サーバーはこの変数が正数なら、プロンプト中の再利用候補位置を `marks=`、`tail=`、`shared=` として engine に要求します。engine は要求位置で状態を保存し、後続プロンプトが過去の内容と分岐した場合に、その位置まで戻れるようにします。上限は会話ごとの数で、最大 16 です。

サーバーと engine は同じ環境変数を別々に解釈します。サーバー側は「要求を作るか」の真偽値として読み、engine 側は「保持数の上限」として読みます。そのため不正値などでは両者の判断が一致しないことがあります。

この名前に対応する CLI 引数は確認できません。server の `child_env()` は親プロセス環境をコピーして engine に渡し、その後 config の `env` 項目が同名を含めて上書きします。したがって server は親環境の値を見て要求を作る一方、engine は config `env` で上書きされた値を使う場合があります。

## 値と判定

| 入力 | サーバー (`serve/server.py`) | DeepSeek engine (`src/dsv41/ds4_model.cu`) |
|---|---|---|
| 未設定 | 既定値 `4`。要求を作る | 別名 `DS4_RESTORE_POINTS` も未設定なら既定値 `4` |
| 空文字 | `int()` 変換失敗として既定値 `4`。要求を作る | `atoi("")` は `0` となり上限 `0` |
| 整数文字列 | 前後空白を除いて Python `int()` に変換し、`> 0` なら要求を作る | `atoi()` で数値化し、`0..16` に clamp |
| 負数または `0` | 要求を作らない | clamp 後 `0`。restore point を保持しない |
| 変換できない文字列 | 既定値 `4` に fallback | `atoi()` の結果 `0`（または数値接頭部があればその値）を clamp |

Python の `int()` は文字列全体を変換するため、たとえば `2x` や `1.5` は失敗して既定値 `4` になります。一方、C/C++ の `atoi()` は先頭の空白と符号の後にある数字接頭部を読み、後続の非数字で止まります。たとえば `2x` は `2`、`x2` は `0` として扱われます。engine では主変数が設定済みなら、その値が不正でも別名へは fallback しません。別名 `DS4_RESTORE_POINTS` は主変数が unset の場合に限り参照されます。サーバー側は別名を参照しません。

engine の `0..16` clamp は `atoi()` が返した `int` 値に対するものです。整数型の範囲を超える入力を検査する処理はありません。

例として、主変数が空文字の場合、サーバーは要求を有効扱いして engine へ候補位置を送りますが、engine の上限は `0` となり保持されません。主変数が unset で別名だけ `0` の場合も、サーバーは要求を作りますが engine は保持しません。不正文字列ではサーバーが既定値 `4` で要求を作り、engine は `atoi()` の結果に応じて保持しないか、数字接頭部の数だけ保持します。

## 有効になる条件

- `serve/server.py` では、対象リクエストの service family が `deepseek41` で、画像入力がない場合に限り `_restore` 候補を作ります。client が送った `_restore` は先に取り除かれ、値として採用されません。
- 設定値のサーバー側変換結果が `> 0` である必要があります。候補位置も、tokenizer が DeepSeek の user/system turn token を認識し、位置が `RESTORE_LEAST`（1024 tokens）以上などの条件を満たす必要があります。tail の位置は別変数 `STRATA_DS4_RESTORE_TAIL`（既定 512）で決まります。
- `strata_prefix` が解決されている場合、または `STRATA_DS4_RESTORE_SHARED` が文字列 `"0"` の場合、サーバーは shared point を除きます。
- engine は要求位置を処理する前に `marks_cap() > 0` を確認します。`mark_plan()` は read 範囲内かつ prompt の最終 token より前にある位置を選び、画像 span 内の位置を除ける形に調整し、近接位置をまとめ、上限を超えた場合は shared point を優先します。

この環境変数を読む Python 経路は Strata server、C++ 経路は DeepSeek V4.1 engine (`src/dsv41`) です。別の model family では server は候補を作りません。

## 実行時の詳細

Python の `restore_point_settings()` は `Service.prepare` からリクエストごとに呼ばれ、現在の `os.environ` を読みます。正数なら、プロンプト token ID から最初の user turn、最後の user/system turn、prompt tail の候補を求め、存在するものを request 内の `_restore` に設定します。`StrataEngine.sampling_keys()` は `_restore` がある場合だけ正の整数位置を `marks=... tail=... shared=...` として engine の GEN 行に付加します。client 由来の `_restore` は `Service.set_restore_points()` の先頭で削除されます。

engine の `marks_cap()` は `static const int` に一度だけ保存されます。`ds4_main.cpp` の serve 初期化中に呼ばれるため、engine 起動時の環境が上限を決め、起動後の環境変更は反映されません。上限が正なら、GEN request の restore point を読み取り時に選別し、位置に到達したところで model 状態を保存します。上限が `0` なら request に位置があっても mark 計画を作らず、通常の 3 checkpoint のみです。上限は保存済み slot の restore point 数にも適用され、上限を超えた分は victim 選択で削られます。

server プロセス自身の環境は各リクエストの Python 判定に使われます。engine の子プロセスには `child_env()` が親環境をコピーして渡しますが、model config の `env` が同名を指定した場合はその値に上書きされます。その場合、server が候補を送るかどうかと engine が保持する上限が異なることがあります。

この変数の無効値に対する専用警告、エラー、終了経路は確認できません。Python の変換失敗は既定値に置き換わり、engine の `atoi()` 結果は clamp されます。上記の値の不一致はログではなく、要求位置が engine に保持されるかどうかの違いとして現れます。

## 根拠

- `serve/server.py:761-770` — Python の既定値、変換、正数判定。
- `serve/server.py:773-804` — user/system/tail 位置の算出、1024-token 下限。
- `serve/server.py:1617-1618,1631-1644` — `_restore` を engine の sampling keys に変換。
- `serve/server.py:5691-5699,5714-5730` — prepare 経路、DeepSeek family・画像条件、prefix/shared 条件、client 値の除去。
- `serve/server.py:1152-1154` — server が engine を `--serve` で起動する箇所。
- `serve/server.py:9114-9115` — 子環境を `StrataEngine` に渡す箇所。
- `serve/server.py:4054-4069` — engine 環境の親からの複製と config `env` による上書き。
- `src/dsv41/ds4_model.cu:7165-7173` — 主変数・別名の読み取り、`atoi()`, clamp、既定値、static cache。
- `src/dsv41/ds4_model.cu:7177-7200` — 上限判定と mark の保持・置換。
- `src/dsv41/ds4_main.cpp:804,1146-1183` — serve 初期化時の上限参照、GEN 要求位置の選別と mark 計画。
- `src/dsv41/ds4_marks.hpp:37-70` — read 範囲・gap・cap に基づく mark 選定。
- `src/dsv41/ds4_model.hpp:245-250` — 追加 restore point の上限と会話状態への用途。

`docs/envvars/000_envvers.md:1080` には候補名があります。Strata 所有ソース内で Python と C++ の実読み取りを確認したため、環境変数として文書化しました。`docs/DETAILS.md` には本変数名の記載が見当たらず、この調査ではソース以外の性能値を根拠としていません。
