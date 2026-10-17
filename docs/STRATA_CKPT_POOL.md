# `STRATA_CKPT_POOL`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の会話 checkpoint を破棄するとき、その実行状態を格納していたベクトル領域をすぐに解放せず、後の checkpoint 保存や batch slot への checkpoint コピーで再利用します。新しい領域を割り当てる頻度を抑える仕組みです。checkpoint の保持数や再利用対象の選び方は変更しません。

プールは serve loop の中に作られ、最大2個を保持します。これは `STRATA_CKPT_POOL` 自身で有効にするほか、`STRATA_SLOT_CKPT_MOVE` が有効な場合にも有効になります。

## 値と判定

`ckpt_pool_env()` は `std::getenv()` の結果を static bool に一度だけ保存し、値全体の parse はせず先頭文字だけを確認します。

| 値 | `STRATA_CKPT_POOL` の判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 有効（設定あり、先頭文字は `\0`） |
| 先頭文字が `0` | 無効。`0`, `0foo` など |
| それ以外 | 有効。`1`, `true`, `false`, ` 0` など |

大文字小文字、空白、数値としての妥当性は検査されません。プロセスで最初に `ckpt_pool_env()` を呼んだ時点の結果がキャッシュされるため、その後の環境変更は反映されません。根拠: `src/program/generate.cpp:195-201`。

## 有効になる条件

プールは serve loop 内で `CheckpointPool(ckpt_pool_env() || slot_ckpt_move_env())` として作られます。したがって `STRATA_SLOT_CKPT_MOVE` の判定が有効なら、`STRATA_CKPT_POOL` が未設定または無効でもプールが動作します。根拠: `src/program/generate.cpp:212-224,8775-8779`。

再利用の対象は会話 checkpoint です。checkpoint 保存処理は `--prompt-cache` が無効、または保存位置 `L` が1未満なら何も保存しません。プールにまだ再利用可能な checkpoint がない初回の保存も、新しい `ConvCheckpoint` から始まります。根拠: `src/program/generate.cpp:9096-9106`。

## 実行時の詳細

checkpoint が LRU eviction、古い tail checkpoint の置換、または次の request と合わなくなった checkpoint の削除で破棄される際、プール有効時は `give()` に移されます。`give()` は `gdn` が空の checkpoint を無視し、checkpoint の token/image 情報、使用時刻、pin mark をクリアしますが、実行状態ベクトルと layer-split の stage parts は保持します。保持上限2を超える領域は解放されます。根拠: `src/program/generate.cpp:1695-1734,9210-9217,9221-9251,12257-12265`。

後続の通常 checkpoint 保存は `take()` でプールから一つ取得し、その `gdn`, `ple`, `tails`, `dead`, `block_pos` ベクトルへ現在の状態を保存します。core 側の保存関数は各ベクトルを必要サイズに `resize()` して状態をコピーします。layer split の場合は pooled checkpoint の stage parts も保存先として再利用できます。プールが空なら空の checkpoint が返り、通常どおり必要な領域が作られます。根拠: `src/program/generate.cpp:9105-9122,9147-9154,9177-9197`; `src/core/conversation_state.cpp:165-184`。

batch admission では、既存 checkpoint を slot にコピーする際にもプールから領域を取得してコピー先として使います。また、slot の古い checkpoint はプールへ渡されます。`STRATA_SLOT_CKPT_MOVE` によって checkpoint 自体が移動された場合も、後の prune 時にその領域が失われないようプールが有効になります。根拠: `src/program/generate.cpp:14640-14647,14665-14700`。

この変数専用の有効・無効ログはありません。`STRATA_TRACE` が有効な checkpoint 保存では、stderr の trace に保存先が `into a dropped checkpoint's vectors` か `new vectors` かが出ます。実際の速度差はこの調査では測定していません。ソースコメントには新規ページ確保の fault 時間への言及がありますが、対象条件がこのファイル内で十分に示されていないため、一般的な性能値としては扱いません。根拠: `src/program/generate.cpp:9161-9175,8776-8778`。

## 文書との照合

`docs/BATCHING.md:110-120` は本変数を既定 OFF の opt-in switch とし、破棄された checkpoint のベクトルへの保存と説明しています。同じ表で `STRATA_CKPT_THREADS` も並記されていますが、stage ごとの保存を同時実行する分岐は `ckpt_threads_env()` が有効な場合です。本変数だけでその同時実行が有効になるわけではありません（`src/program/generate.cpp:9116-9119,9147-9154`）。

## 根拠

- 値の読み取りと判定: `src/program/generate.cpp:195-201`
- プールの保持上限、破棄時の整理、取得: `src/program/generate.cpp:1695-1734`
- serve loop での生成と checkpoint 保存: `src/program/generate.cpp:8775-8779,9096-9122`
- 保存先ベクトルの resize と状態コピー: `src/core/conversation_state.cpp:165-184`
- eviction と request path prune: `src/program/generate.cpp:9210-9251,12257-12265`
- batch slot へのコピーと古い checkpoint の再利用: `src/program/generate.cpp:14640-14700`
- 関連資料: `docs/BATCHING.md:110-120`
