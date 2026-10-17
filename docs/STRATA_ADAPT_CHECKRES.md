# `STRATA_ADAPT_CHECKRES`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

適応 expert cache の verify window ごとに、GPU 上の residency table をホストへ読み戻してホスト側の計画と比較する診断用スイッチです。また、CPU 側で expert を計算する layer について、ルーティングされた expert がすべて GPU residency table 上で resident に見えるため activation が publish されなかったケースを数えます。テーブルの不一致や stale activation を修正するスイッチではありません。

## 値と判定

| 環境変数 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む任意の設定値 | 有効（値の内容を parse せず、`getenv(...) != nullptr` だけで判定） |

`=0` も設定されていれば有効です。serve 経路ではシリアル window の場合、speculative generate 経路では `d_res` が存在する場合に限り、読み戻し用のバッファを割り当てて Verifier の pre-launch hook を設定します。判定は各経路の初期化時に行われ、環境変数を実行途中で変更しても再評価されません。

## 有効になる条件

- **serve**: `serial_windows` が真のとき有効です。これは `--pipeline-windows` 相当の `pipe` がなく、`--batch-groups` を使う layer split の piped groups でもない状態です。layer split の各 stage の verifier にはテーブル更新 hook が設定されますが、読み戻し・比較は pool 側の verifier で行います。
- **speculative generate**: device residency table `d_res` が存在するとき有効です。存在しない場合、変数による確認 hook は設定されません。
- この機能は CUDA の residency table を対象にした実装です。候補一覧にあることだけから他 backend でも有効とは判断できません。

環境変数が有効でも、Verifier が window を起動しなければ確認は行われません。serve では非シリアル window の経路で `res_checking` が false になります。

## 実行時の詳細

pre-launch hook は、まず必要なら dirty な residency entry を device 側へ反映します。確認が有効なら verifier stream（serve では各 stage の verifier stream も）を同期してから device table をホストへ読み戻し、`host_res` と entry ごとに比較します。不一致の最初の最大20件は stderr に `strata: res check: window ... layer ... expert ...: host ..., device ...` と出ます。読み戻しに失敗した場合は stderr に失敗理由を出しますが、その比較関数自体は不一致数 0 を返します。

serve では不一致 window 数・entry 数と、CPU expert がある layer で activation が publish されなかった回数を stderr に定期表示します（不一致がある場合は初回4 window まで、その後は256 windowごと）。generate では終了時の `residency check` 統計として stdout に表示します。dispatch 側の `stale_x` カウンタは、CPU で処理する routed expert があるのに、当該 layer の routed IDs がすべて読み戻し表で resident と判定されたときに増えます。このカウンタは dispatch が評価された回数であり、比較処理による修復や停止はしません。

有効時は window 起動前の stream 同期と device-to-host copy が追加されます。測定値や速度への影響は、この commit の該当実装および確認した資料には示されていません。

## 根拠

- `src/program/generate.cpp:1513-1534`: residency table の読み戻し、entry 比較、不一致ログ、読み戻し失敗時の扱い。
- `src/program/generate.cpp:9605-9619,9652-9672,9686-9689`: serve 経路の適用条件、各 window 前の同期・比較、集計ログ。
- `src/program/generate.cpp:15321-15371,15763-15766`: speculative generate 経路の適用条件、pre-launch hook、終了時の統計。
- `src/core/expert_source.cpp:3989-3999` および `include/strata/core/expert_source.hpp:578-581`: CPU expert dispatch による `stale_x` の計上条件と診断表ポインタ。
- `docs/DETAILS.md:1887`: 関連する eviction 同期修正の説明。同資料は `STRATA_ADAPT_CHECKRES=1` が stale activation に該当する layer を数える診断であると記載しています。
