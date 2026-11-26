# `STRATA_PREFILL_GROUP_GATHER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt prefill の MoE expert 重みを MMQ / int8 の expert グループへ gather する際、expert ごとに gather・コピー完了待ち・ring slot 解放を行うか、複数 expert をまとめるかを制御する。CUDA/HIP 実装では短い staged walk、長い streamed walk、条件を満たす layer-major walk に関係し、SYCL 実装では長い streamed walk の native MMQ 経路に関係する。CUDA/HIP では OWN-I8 の grouped route を選ぶ条件にもなる。グループの上限は `MMQ_GROUP = 16`（CUDA/HIP: `engine/src/prefill/prefill.cpp:1916`、SYCL: `engine/sycl/src/prefill/prefill.cpp:1243`）。読み取りは各 backend の `prefill.cpp` にある。

CUDA/HIP の staged walk では、グループ対応の native expert 層に対し、staged slot を保持したまま複数 expert をまとめて gather する経路を選ぶ。streamed walk でもグループ対応層は gather をまとめ、最後のコピーを待ってから一括 gather する。無効にすると expert ごとの gather に戻るほか、OWN-I8 経路の条件も満たさなくなる（`engine/src/prefill/prefill.cpp:7001-7013`, `7117-7123`, `7256-7305`, `7526-7531`, `7561-7583`, `6359-6378`）。routing の生成を選ぶ CLI 引数やサーバー設定を読むコードはない。

## 値と判定

各箇所で `std::getenv` の結果を `std::atoi(v) != 0` と判定する。未設定は有効。設定値は整数全体として検証せず、`atoi` が変換した値がゼロかどうかだけを見る。したがって空文字・数値で始まらない文字列・`0anything` は無効、`1`・`-1`・`1anything` は有効。先頭空白と符号の後に数値があればその数値を変換し、後続文字は判定に使わない。`true` / `false` はどちらも数値変換できず無効。整数範囲外の文字列については `atoi` の結果を保証できず、コードに別の範囲検査はない（CUDA/HIP: `engine/src/prefill/prefill.cpp:343-345`, `6360-6362`, `7003-7005`, `8792-8795`; SYCL: `engine/sycl/src/prefill/prefill.cpp:4706-4709`）。

| 条件（build / 経路） | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP の staged / streamed walk、layer-major の native MMQ グループ | 有効 | `1`, `-1`, `1x` | `0`, 空文字, `0x`, `true` |
| SYCL の streamed native MMQ グループ | 有効 | `1`, `-1`, `1x` | `0`, 空文字, `0x`, `true` |

この名前を読む場所に CLI、設定ファイル、別の環境変数による値の上書きはない。各読み取り箇所は関数内 `static` に判定結果を保存するため、その箇所では初回評価後にプロセス環境を変更しても再評価されない。複数の箇所は別々の `static` なので、それぞれが初めて評価される前に環境が変更されれば、読み取り結果が異なる余地はある（上記の全読み取り箇所）。

## 有効になる条件

- 対象は prompt prefill の expert 処理であり、decode など prefill のこれらの walk を通らない処理には適用されない。CUDA/HIP 側と SYCL 側にそれぞれ読み取り箇所がある。Metal 用実装を含む Strata 全体の `rg` 検索では、この名前を値として読む別の実装は見つからなかった。
- CUDA/HIP の通常の chunk-major 経路では、expert 層が `lay.native` であることが必要。長い streamed walk はさらに `m.ring > STAGE`、`T >= stream_all_min()`、`m.src != nullptr` が必要（`engine/src/prefill/prefill.cpp:4625-4629`）。短い staged walk は `!stream_all` の分岐で、MMQ または対象 fused / int8 経路が存在し、16 expert のグループ上限以内である場合に限る（`engine/src/prefill/prefill.cpp:6343-6350`, `7006-7013`）。
- CUDA/HIP の staged fused entry（P4-SMALL）はこの変数が有効なだけでは使われない。`staged_entry_layer(...)`、native 形式、peer 構成なし、`m.group_cap == 0`、MMQ direct / WS などの除外、fused kernel の形式対応、グループ上限などを満たす必要がある。また `staged_group_entry_on()`（`STRATA_PF_FUSED` と build による既定値）も必要で、この変数は `STRATA_PF_STAGED_FO` の unset 時の既定判定にも渡される（`engine/src/prefill/prefill.cpp:326-337`, `427-446`, `6341-6350`）。
- CUDA/HIP の OWN-I8 経路にも独立した読み取りがあり、この値が無効ならその int8 grouped route は選択されない。値が有効でも native expert 形式、peer / group scratch 等の条件、対象チャンク条件や必要バッファが要る（`engine/src/prefill/prefill.cpp:6351-6378`）。
- CUDA/HIP の layer-major walk では、walk 自体が別の条件を満たして実行される場合に限り、native MMQ 層の `group_lm` を有効化する。`fz_l`（fused）層と `fp16_l` 層はこの grouped-MMQ 分岐の対象外であり、それぞれの処理はこの判定を通らない（`engine/src/prefill/prefill.cpp:8790-8799`, `8921-8948`, `8950-9001`）。layer-major 自体は CUDA/HIP build の条件、モデルや prompt 状態、peer・画像 prompt・KVA 等の条件で利用できない場合がある（`engine/src/prefill/prefill.cpp:8166-8209`）。
- SYCL では読み取り箇所が `stream_all` の group gather 判定に限られ、`stream_all && use_mmq && lay.native && MMQ_GROUP <= mmq::kGatherGroupMax` のときだけ grouped gather を選ぶ。短い staged walk や CUDA/HIP の P4-SMALL / OWN-I8 / layer-major には、この SYCL 読み取りによる制御はない（`engine/sycl/src/prefill/prefill.cpp:4705-4711`）。

## 実行時の詳細

CUDA/HIP の chunk-major walk では `stream_all` の長い prompt で、値が有効かつ native MMQ または OWN-I8 の group 経路に入る場合、`group_gather` が true になる。false の場合は各 streamed expert のコピー完了を待って `compute` し、個々の slot を解放する。有効な場合はグループ内の staged blob を保持し、最後のコピーを待ってグループ gather を行い、グループの slot をまとめて解放する。非 streamed の staged walk でも `group_resident` が true なら `STAGE_GRP` ring を使い、グループ境界で staged slots を保持・処理する。無効時や条件外では `STAGE` ring と expert 単位の wait / compute に戻る（`engine/src/prefill/prefill.cpp:7006-7013`, `7117-7123`, `7256-7279`, `7495-7532`, `7561-7583`）。

この grouped gather はグループ分の expert を一括で gather する（`mmq::gather_native_group`）。その後の MMQ products は引き続き expert group ごとに実行される。無効値はエラー扱い・警告・自動 fallback のログを出すのではなく、grouped gather 判定を false にする（`engine/src/prefill/prefill.cpp:7120-7125`, `7268-7305`）。

layer-major の native MMQ 経路では有効な場合に `group_lm` が true となり、各 group の staged copy を一度待ってまとめて gather し、slot を group 単位で解放する。無効時は expert ごとに待ち・gather・slot 解放を行う。fused の `fz_l` 経路は環境変数の `group_lm` 判定から独立して group entry を実行する（`engine/src/prefill/prefill.cpp:8792-8799`, `8873-8880`, `8921-9001`）。

SYCL の streamed group gather では、有効時に group のコピー完了を待って `mmq::gather_native_group` を呼び、ring slot をまとめて同期する。無効時は expert ごとにコピー完了 barrier を待ち、各 expert を gather して slot を同期する（`engine/sycl/src/prefill/prefill.cpp:4706-4709`, `4715-4739`, `5083-5104`, `5295-5317`）。

## ログと測定値

変数の値、無効な値、grouped gather の選択を直接表示する Strata のログ・警告は見当たらない。SYCL の gather / barrier 中に `sycl::exception` が発生した場合は例外文字列とファイル・行を stderr に出して `exit(1)` するが、この処理は設定値の検証ではない（`engine/sycl/src/prefill/prefill.cpp:4692-4697`, `4741-4745`）。

`docs/DETAILS.md:1305` は `STRATA_QUANT_GATHER=1` と本変数 `=0` の組合せを「Per-row gather ... short-prompt grouped gather off」と記す。現行ソースで確認できるのは上記の backend ごとの grouped expert gather 判定であり、この資料の性能測定条件や「No gain measured」の測定値は同ファイルに示された記載以上には特定できないため、本書では性能効果を結論しない。

## 根拠

- `engine/src/prefill/prefill.cpp:339-347` — staged walk 用の読み取りと cache。
- `engine/src/prefill/prefill.cpp:6359-6378` — OWN-I8 経路用の読み取りと適用条件。
- `engine/src/prefill/prefill.cpp:7001-7013`, `7117-7123`, `7256-7305`, `7526-7531`, `7561-7583` — chunk-major streamed / staged gather の分岐・待ち・slot 解放。
- `engine/src/prefill/prefill.cpp:8790-9001` — layer-major の grouped MMQ / fused 経路。
- `engine/sycl/src/prefill/prefill.cpp:4699-4739`, `4705-4711`, `5083-5104`, `5295-5317` — SYCL streamed gather。
- `engine/cmake/strata_gpu_engine.cmake:482-488`, `engine/sycl/CMakeLists.txt:303-309` — CUDA/HIP と SYCL の prefill 実装の build 登録。
- `docs/DETAILS.md:1305` — 関連する資料上の記述。
