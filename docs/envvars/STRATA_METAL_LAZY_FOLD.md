# STRATA_METAL_LAZY_FOLD

調査対象: Strata main の HEAD 296b59d2f73c8f04a805df29c2fa97655adace78（2026-10-14 時点）。対象は Strata 所有ソース。外部ライブラリや Metal driver の動作は含めない。

## 役割

Metal decode window の commit で行う GDN state の fold を、commit 時点で実行するか、次の処理機会まで保留するかを選びます。既定では fold を pend_fold_ に記録し、次の decode window の GPU command buffer の先頭に追加します。STRATA_METAL_LAZY_FOLD=0 は commit 中に fold を実行する設定です。Strata の docs/MAC.md は =0 を decode fusion 2種類の無効化として列挙し、同じ token・低速と説明しています。

## 値と判定

判定は文字列全体と "0" を比較します。数値変換、trim、大文字小文字変換はありません。

| 環境値 | 判定 | 挙動 |
|---|---|---|
| 未設定 | getenv() が null | lazy fold を有効化 |
| 空文字 | getenv() は非 null、文字列は "0" と不一致 | lazy fold を有効化 |
| 0 | 文字列全体が "0" | lazy fold を無効化し、commit 中に fold |
| その他の文字列（例: 1, 00, false, `0␠`） | "0" と不一致 | lazy fold を有効化 |

値の判定結果は関数内 static const bool に保存されます。初めて last_T_ > 1 の commit に入る時点で評価され、その後プロセス内で環境変数を変更しても再評価されません。コンストラクターやプロセス起動時の一律な読み取りではありません。

根拠: metal/src/engine/window.cpp:1442-1449。

## 有効になる条件

- Metal backend の Window::commit() を通る必要があります。通常の verifier commit は STRATA_GPU_METAL ビルドで Metal 側の window_commit() に委譲されます。
- last_T_ > 1 のときだけ環境値を評価します。1 token window はこの commit fold 分岐に入りません。
- さらに fold 対象行数 nf が正である必要があります。通常モードでは nf = n_keep。STRATA_METAL_PARTIAL=1 の場合、head 付き window は nf = n_keep - 1、head なし window は全行 commit が必須で nf = 0 となるため、後者では lazy 設定は fold 時期に影響しません。partial mode で n_keep == 1 の場合も nf == 0 です。

根拠: metal/src/engine/window.cpp:230-235,1442-1468,2491-2495,2508-2512; src/core/verify.cpp:2645-2648。

## 実行時の詳細

fold は各 GDN layer について、window 内に保持した入力から keep された prefix を gdn_step で state に反映する処理です。lazy が有効で nf > 0 なら、commit は pend_fold_ = nf として fold を記録し、history parity を切り替えて戻ります。次の decode window は保留数を window cache key に含め、dispatch 構築時に fold を先頭へ追加して pending 状態を消費します。したがって通常の decode 継続では、次 window の計算に先立って fold が実行されます。

commit 後に次の decode window ではなく prompt chunk に進む場合も、prompt_chunk() が保留 fold を実行してから prompt の dispatch を組みます。conversation checkpoint の保存時も保留 fold を実行してから state をコピーします。reset は state とともに pending 値をゼロにし、checkpoint restore は既存の pending 値を破棄して復元 state に置き換えます。

lazy 無効時は commit 内で fold dispatch を作り、cx_->run_graph(ds) で直ちに実行します。環境変数に関する個別のログや警告はありません。

根拠: metal/src/engine/window.cpp:984-1023,1351-1373,1375-1383,1401-1403,1421-1439,1449-1469,2108-2122。

## 文書との照合

docs/MAC.md:183-193 は STRATA_METAL_LAZY_FOLD=0 を STRATA_METAL_FUSE=0 と並べて decode fusion の無効化として記載し、同じ token で遅くなるとしています。ソースでは lazy 設定は fold の実行時期を切り替えています。ソースコメントは fold を次の window の command buffer 冒頭へ送ることで submit/wait を1回省く意図を示します（metal/src/engine/window.cpp:226-229）。この調査では性能値を新たに測定していません。

## 根拠

- 値判定、対象行数、即時/保留の分岐: metal/src/engine/window.cpp:1442-1469
- window graph 冒頭での pending fold 消費と cache key: metal/src/engine/window.cpp:984-1023
- fold dispatch の内容: metal/src/engine/window.cpp:1351-1373
- checkpoint、reset、restore、prompt 経路: metal/src/engine/window.cpp:1375-1439,2108-2122
- Metal backend の verifier との接続: src/core/verify.cpp:2235-2241,2645-2648; metal/src/engine/window.cpp:2491-2512
- 利用者向け記述: docs/MAC.md:183-193
