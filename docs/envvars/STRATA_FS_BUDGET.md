# `STRATA_FS_BUDGET`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Foresight swap space が、各カードにつき完了済み window ごとに新たに発行できる expert blob の非同期コピー数を制限する。既定値は32コピーで、値が小さいとその上限に達した後のコピー要求が記録されて見送られる。環境変数は swap space の作成時に読み取られ、そのインスタンスの `budget` に格納される。`STRATA_FS_SLOTS` が有効な CUDA/HIP の serve 経路で使われる設定であり、通常の経路やスロットを作らない経路では効果がない（`engine/src/core/expert_source.cpp:7294-7321`、`engine/src/program/generate.cpp:14795-14807`）。

## 値と判定

値は swap space 作成関数内の helper が `std::getenv` で取得し、設定があれば `std::atoi`、未設定なら既定値32を採用したうえで1未満を1に丸める。文字列全体の妥当性検査やエラー報告はなく、`atoi` が変換する先頭の整数部分が使われる。従って空文字や整数に変換できない文字列は0相当となり1に丸められる。数値の後ろの文字は無視される。符号と先行空白も `atoi` の変換に従う。`atoi` の `int` 範囲を超える値の結果はこのコードで定義されない（`engine/src/core/expert_source.cpp:7306-7311`）。

| 条件 | 未設定 | 有効になる値（例） | 無効な値・変換後の扱い（例） |
|---|---|---|---|
| Foresight swap space を作成する経路 | 32 | `1` → 1、`32` → 32、`32junk` → 32、`+4` → 4 | 空文字、`abc`、`false`、`0`、`0anything`、`-7` → 1。`1.9` → 1。 |

ここで「有効」はコピー予算に格納される値を指す。`0` や負値でも機能全体を無効にはせず、最小予算1になる。設定値に上限の clamp はない（ただし `atoi` の結果型は `int`）。

## 有効になる条件

- `STRATA_FS_SLOTS` を `std::atoi` した値が正であること。未設定・0以下なら `foresight_swap_from_env` は直ちに `nullptr` を返し、`STRATA_FS_BUDGET` を読み取らない。スロット数そのものは64に上限 clamp される（`engine/src/core/expert_source.cpp:7294-7298,7313`）。
- `STRATA_VERIFY_DEVICE_PLAN` と `STRATA_VERIFY_DEVICE_HITS` のどちらも、設定値を `atoi` した結果が非0でないこと。いずれかが非0なら stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN/HITS (the device would plan resident layers without the host)` と出して `nullptr` を返し、予算値の読取りより前に機能を止める（`engine/src/core/expert_source.cpp:7299-7308`）。
- serve の対象実行経路で Foresight swap space の生成処理が呼ばれること。作成時に CUDA device memory / stream / event の初期化に失敗した場合は「`cannot allocate ...`」または「`cannot create the copy events`」を理由に `strata serve: foresight swap: <理由> - swap space off` を出し、機能を無効にする（`engine/src/core/expert_source.cpp:7082-7113,7312-7316`）。

## 実行時の詳細

`generate.cpp` は serve の処理で `foresight_swap_from_env` を呼び、生成されたインスタンスを dispatch に設定する。利用可能な場合は router look-ahead と expert source にも接続される（`engine/src/program/generate.cpp:14795-14807`）。呼び出し側は予算値を引数や設定ファイルから渡しておらず、優先順位を上書きする CLI 設定はこの経路にない。対象変数の読取りはこのインスタンスの作成時だけで、関数内 static cache はなく、既存インスタンスの実行中にプロセス環境を変更しても格納済みの `budget` には反映されない。

通常の expert 選択でキャッシュにない expert を Foresight slot から取得できなければ、swap に miss を通知した後、既存の fetch / staging 処理へ進む。予測コピーも同じ swap の要求処理を使う（`engine/src/core/expert_source.cpp:5593-5606,3791-3792,7218-7221`）。要求処理はカードごとに完了済み window の番号を見て使用数をリセットし、`card_used >= budget` なら `over_budget` を増やしてコピー要求をそこで終了する。予算内で pinned arena にコピー元があり、再利用可能な slot があればコピーをキューへ積み、別 filler thread がホストからデバイスへコピーする（`engine/src/core/expert_source.cpp:7230-7278,7134-7158`）。

予算上限に達した要求はコピーを追加しないだけで、miss の処理は既存の経路へ進む。予算が route / expert 選択を書き換える処理はここにはなく、値はコピー機会の上限として使われる（`engine/src/core/expert_source.cpp:5593-5606,7240-7245`）。生成処理の報告時には、コピー数と `over budget` 件数を含む統計を stderr に出す（`engine/src/core/expert_source.cpp:7281-7291`、`engine/src/program/generate.cpp:23286`）。

## ログと測定値

swap space 作成に成功すると stderr に `strata serve: foresight swap: <slots> slots per layer on <cards> card(s), up to <budget> copies per card and window, admit after <n> miss(es), reuse after <n> windows` が出る。この `<budget>` は clamp 後の値。生成処理の報告では `foresight swap: ... <n> over budget` が含まれる（`engine/src/core/expert_source.cpp:7318-7321,7281-7291`）。コピー失敗時は `strata serve: foresight swap: a copy failed - swap space off` が出る（`engine/src/core/expert_source.cpp:7151-7155`）。対象変数の値ごとの性能測定値は、確認した Strata の資料にない。

## 根拠

- `engine/src/core/expert_source.cpp:7294-7321` — スロット有効条件、検証フラグ、予算の変換・既定値・下限、作成ログ。
- `engine/src/core/expert_source.cpp:7230-7278` — window ごとのカード別予算適用とコピー要求。
- `engine/src/core/expert_source.cpp:5593-5606,3791-3792` — miss と look-ahead からの利用。
- `engine/src/program/generate.cpp:14795-14807,23286` — serve 経路の接続と報告。
