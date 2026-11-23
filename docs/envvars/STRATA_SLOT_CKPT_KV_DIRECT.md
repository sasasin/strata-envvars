# STRATA_SLOT_CKPT_KV_DIRECT

調査対象: Strata main の HEAD 73d4f4196c25a65e02f6b9ef25d354826ce55105（2026-11-23 時点）。

## 役割

バッチ処理でスロットから会話のターン checkpoint を復元するとき、checkpoint の実行状態を復元した後の K/V をスロットの GPU 上の session state からメイン session state へ直接コピーする経路を選びます。これによりこの分岐では K/V を ConversationKv のホスト image に保存してから復元する手順を通りません。通常の会話内容や checkpoint 選択を変える設定ではありません（engine/src/program/generate.cpp:16861-16886,16888-16911）。

## 値と判定

copy_from_slot 内の関数内 static const bool 初期化で std::getenv の値を一度読み、値が存在し、空でなく、先頭文字が '0' 以外なら有効です。文字列全体の parse や数値変換はしません。空白の trim、大文字小文字の判定、後続文字の検査もありません（engine/src/program/generate.cpp:16867-16870）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の非 Metal バッチ復元経路 | 無効。checkpoint K/V は従来の image save/restore 経路 | 1, true, false, x,  0（空白始まり） | 空文字、0, 00, 0anything |

値に境界値や数値の範囲はありません。CLI 引数による値の上書きはなく、適用には別途 STRATA_SLOT_COPY_DIRECT が有効である必要があります（下記）。STRATA_SLOT_COPY_DIRECT が無効ならこの変数だけでは経路を切り替えません（engine/src/program/generate.cpp:16763-16766,16871-16873）。

## 有効になる条件

- この読み取りと分岐は Metal の STRATA_GPU_METAL 分岐の後にあり、同じ設定登録情報も backend を cuda-hip としています。したがって対象は CUDA/HIP のバッチ復元コードです。Metal は専用の window_slot_copy_main 経路を通ります（engine/src/program/generate.cpp:16757-16766,16852-16860; terminal/data/settings-register.json:42540-42550）。
- 対象は --batch のスロットから会話状態を戻す経路です。リクエスト選択では o.prompt_cache > 0、画像入力なし、互換する cvec の idle/cached slot が条件です。active slot の checkpoint を候補にするには STRATA_SLOT_CKPT_MOVE が有効で、slot が tainted でなく、drafting 条件も満たす必要があります（engine/src/program/generate.cpp:19216-19235）。
- この変数の効果が出るのは、選ばれた slot restore が checkpoint を指定する場合（at != nullptr）かつ STRATA_SLOT_COPY_DIRECT が有効な場合だけです。slot 全体の末尾から戻す場合（at == nullptr）は STRATA_SLOT_COPY_DIRECT の直接コピー分岐を使い、この変数は分岐選択に関与しません（engine/src/program/generate.cpp:16871-16873）。
- STRATA_SLOT_COPY_DIRECT も未設定・空文字・先頭が 0 なら無効、それ以外なら有効です。両方の値は初期化時に一度だけ読み取られます（engine/src/program/generate.cpp:16763-16766,16867-16870）。
- checkpoint restore に失敗した場合、設定値にかかわらず checkpoint 経路は完了しません。呼び出し側は slot の状態を破棄して prompt を先頭から読み直します（engine/src/program/generate.cpp:19757-19770）。

## 実行時の詳細

STRATA_SLOT_COPY_DIRECT と本変数はそれぞれ関数内 static に保存されます。前者はバッチ slot copy 用コードの実行時、後者は copy_from_slot が最初に呼ばれて宣言に到達したときに初期化され、そのプロセス内では再読込されません。起動後の環境変更は反映されません（engine/src/program/generate.cpp:16763-16766,16852-16870）。

checkpoint 指定かつ両設定が有効なら、各 stage で対象 device を同期し、対応する checkpoint（stage 0 は *at、後続 stage は at->stage_parts）の実行状態を復元します。その後、slot session の各 QSA state からメイン session の対応する QSA state へ、checkpoint の token 数 upto まで conversation_kv_copy(..., true, ..., false) で K/V をコピーし、再度 device を同期します。対して本変数が無効の場合は各 stage で checkpoint を復元したうえ、K/V を conversation_kv_save で image 化し、conversation_kv_restore で戻す従来経路です（engine/src/program/generate.cpp:16855-16856,16873-16911）。

この分岐は checkpoint の実行状態を復元する処理を省略せず、K/V コピー方法だけを変えます。成功時は slot の token 数まで戻し、request path が slot の会話を再利用します（engine/src/program/generate.cpp:16879-16885,19770-19783,19826-19843）。

## ログと測定値

この環境変数の有効・無効を知らせる専用ログはありません。復元処理が失敗すると stderr に「strata batch: restoring slot %d failed (%s); reading the prompt」を出し、live state と checkpoint をクリアして prompt を読み直します。同期失敗時の error は「batch slot restore: device sync failed」です。別の checkpoint restore / K/V copy が失敗した場合は、その処理が設定した error 文字列が同じ stderr 行に含まれます（engine/src/program/generate.cpp:16878-16885,16892-16911,19760-19770）。本変数について、条件付きの測定値を示す Strata 資料は確認できません。

## 根拠

- engine/src/program/generate.cpp:16763-16766 — 連携する STRATA_SLOT_COPY_DIRECT の値判定。
- engine/src/program/generate.cpp:16852-16870 — 対象変数の読み取りと checkpoint restore の分岐。
- engine/src/program/generate.cpp:16871-16911 — 直接コピー経路と従来の image 経路。
- engine/src/program/generate.cpp:19216-19235 — slot/checkpoint の候補条件。
- engine/src/program/generate.cpp:19757-19783,19826-19843 — restore 失敗時の再読込と成功後の状態処理。
- terminal/data/settings-register.json:42540-42550 — 設定登録上の backend と読み取り位置。
