# `STRATA_PARK_ASYNC`

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

conversation cache が会話を park するとき、CUDA では GPU 上の K/V を device-to-device で一時領域へコピーし、その領域からホスト側の snapshot buffer へバックグラウンド転送する opt-in です。snapshot を作って次の prompt を始めるまでの K/V の host 転送を非同期化します。また serve 側では、park 後に捨てる turn checkpoint をコピーせず snapshot に移します。通常の同期コピー経路も残り、条件不成立や staging の確保失敗時はその経路になります。対象は会話 cache の park であり、各リクエストで常に動く設定ではありません。conversation_snapshot_save と conversation_park_async_begin が転送を組み立て、serve loop の park_async_env が checkpoint 選別に使います（engine/src/core/conversation_state.cpp:563-586,623-699、engine/src/program/generate.cpp:504-507,14202-14206）。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 通常の CUDA build | park_async_on() は false | 先頭文字が 1（1, 10, 1anything） | 空文字、0, true,  1, 01 |
| HIP、gfx906 HIP compatibility、Metal | compile-time 分岐で常に false | なし | すべて（値を読み取らない） |

CUDA build では std::getenv の結果が null でないことと v[0] == '1' だけを確認します。文字列全体の parse や数値変換、大文字小文字・後続文字の検査はありません。空文字は設定済みでも無効です。park_async_env() も同じ先頭文字判定をします。両関数は関数内 static const に保存するため、各関数の初回評価後にプロセス内で環境を変更しても反映されません（engine/src/core/conversation_snapshot.cpp:237-243、engine/src/program/generate.cpp:504-507）。

なお、conversation swap の別の最適化は値ではなく std::getenv("STRATA_PARK_ASYNC") の null 判定を使います。そのため変数が空文字や 0 でも設定されていれば swap prepare を見送ります（engine/src/core/conversation_state.cpp:783-790）。

## 有効になる条件

- 非同期 K/V staging は CUDA build であることが必要です。HIP (STRATA_USE_HIP)、gfx906 compatibility (STRATA_HIP_GFX906)、Metal (STRATA_GPU_METAL) では park_async_on() が常に false です。docs/SETTINGS.md の候補表は NVIDIA と AMD を記載していますが、実装では HIP 系を無効化しています（engine/src/core/conversation_snapshot.cpp:237-243）。
- serve の conversation cache が有効で、live conversation を park する経路に入る必要があります。--conversation-cache-mib 0 は cache を無効にします。serve loop は会話の切替などで park_current を呼び、cache 無効・live state 不成立・空会話なら park を省略します。この CLI option は cache を制御しますが、STRATA_PARK_ASYNC の値判定を上書きしません。各リクエストでの継続処理そのものを有効化する設定ではありません（engine/src/program/generate.cpp:1295,4084-4099,14519-14532,19836-19860）。
- K/V の必要量が 0 なら staging は始まりません。CUDA device 取得、stream と pinned host buffer の作成、stage/slot の確保ができないと begin が false になり、K/V 保存は同期転送へ進みます（engine/src/core/conversation_state.cpp:623-638,641-682、engine/src/core/conversation_snapshot.cpp:1077-1142）。
- 通常の VRAM stage は必要量を 64 MiB 単位に切り上げて確保し、確保後にも 1.5 GiB の空きを要求します。満たせない場合は staging を諦めます。STRATA_PARK_VRAM_MIB が正数なら予算・空き VRAM 条件を満たす slot を先に試し、slot の対象外部分は同期コピーに fallback します（engine/src/core/conversation_snapshot.cpp:143-198,1086-1141）。
- checkpoint の移動最適化は serve loop の park_async_env() が true の場合だけ設定されます。layer split (n_st != 0) または main session の retained-K/V reuse がない場合には、この park 選別による checkpoint 移動は行いません。条件を満たす場合、incoming conversation・borrow・batch slot source がある、または cvec が変わると checkpoint を全て移し、それ以外は resume 位置より後ろ、または画像 prefix と一致しない checkpoint を移します（engine/src/program/generate.cpp:14202-14206,14457-14466,19742-19754）。
- STRATA_PARK_VRAM_MIB は任意の併用設定です。正数でも budget 超過や VRAM 不足なら slot は使われず、通常 stage を試します。checkpoint pool (STRATA_CKPT_POOL) が有効なら、移動してきた checkpoint は pool 補充にも使われます（engine/src/core/conversation_snapshot.cpp:162-198、engine/src/program/generate.cpp:14447-14466）。

## 実行時の詳細

snapshot 保存のたびに、まず前回 park のバックグラウンド転送を join し、snapshot 対象の K/V byte 数を計算して conversation_park_async_begin を呼びます。begin が成功すると、各 K/V buffer のうち保存対象部分を device-to-device で stage または VRAM slot に写します。stage の利用条件を満たさない K/V 部分は transfer による従来経路で保存されます。全レイヤーの保存後、launch は private stream の device-to-device コピー完了を待ち、その後 std::async の worker が 4 MiB 片を二つの pinned buffer で交互に host buffer へ転送します（engine/src/core/conversation_state.cpp:623-682、engine/src/core/conversation_snapshot.cpp:496-517,1155-1208）。

次の park や snapshot の読取・解放時は pending copy を join します。parked image には pending token が付けられ、画像の K/V を restore する前に完了を待ちます。通常の stage 経路では restore は host snapshot から行われます。VRAM slot が利用される場合は slot の寿命を image/K/V に結び付け、restore は slot の device データを使えます（engine/src/core/conversation_state.cpp:573-576,682-698,899-911、engine/src/core/conversation_snapshot.cpp:1061-1068）。

stage/slot の開始前に stream・pinned buffer や GPU memory の確保が失敗すれば同期保存へ戻ります。stage launch の stream 同期失敗は conversation_snapshot_save の失敗として返り、serve loop は ERR <error> を出力します。非同期 worker の K/V copy が失敗した場合、join は結果をエラーとして返さず stderr へ strata: STRATA_PARK_ASYNC: a parked K/V copy failed (<CUDA error>) を出します。snapshot swap prepare は値が有効かどうかにかかわらず環境変数が設定されていれば拒否し、通常経路に戻ります（engine/src/core/conversation_snapshot.cpp:1061-1068,1155-1166、engine/src/core/conversation_state.cpp:682-699,783-790、engine/src/program/generate.cpp:19836-19860）。

## ログと測定値

この変数自体の on/off を通知するログはありません。非同期 copy の失敗時は strata: STRATA_PARK_ASYNC: a parked K/V copy failed (%s) を stderr に出します。launch の失敗は serve loop が ERR %s として stdout に出します（engine/src/core/conversation_snapshot.cpp:1061-1068,1155-1166、engine/src/program/generate.cpp:19858-19861）。

docs/DETAILS.md は、変更報告者が CMP 170HX (GA100, sm_80)、PCIe Gen2 x4 で測定した park 時間として、3.3K token で 212–217 ms から 64–75 ms、13K token で 329–334 ms から 68 ms と記載しています。同資料は手元に sm_80 card がなく、報告者の測定であることを明記しています。別の opt-in 設定を併用した測定もあるため、一般的な性能値とは扱えません（docs/DETAILS.md:1784-1795）。同資料は回答 bytes が同じと説明しますが、この調査では測定を再実行していません。

## 根拠

- 値判定・compile-time backend 条件: engine/src/core/conversation_snapshot.cpp:237-243
- serve 側の値 cache と checkpoint 選別: engine/src/program/generate.cpp:504-507,14202-14206,14457-14466,19742-19754
- park の呼出し条件: engine/src/program/generate.cpp:14519-14532,19836-19860
- stage 開始から async launch、pending の設定: engine/src/core/conversation_state.cpp:563-586,623-699
- K/V の device stage と background copy、join・失敗ログ: engine/src/core/conversation_snapshot.cpp:496-517,1061-1068,1077-1142,1155-1208
- 設定有無による conversation swap prepare の抑止: engine/src/core/conversation_state.cpp:783-790
- 併用する VRAM slot の予算・空き判定: engine/src/core/conversation_snapshot.cpp:143-198
- 性能値の出典と条件: docs/DETAILS.md:1784-1795
