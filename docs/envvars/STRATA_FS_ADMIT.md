# `STRATA_FS_ADMIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Foresight swap が、通常の expert miss を受けて VRAM の swap slot へコピーを予約するまでに要求する miss 回数を指定します。Foresight swap が有効なとき、既定値 `1` は従来どおり最初の miss でコピーを要求し、`2` 以上は同じ `(layer, expert)` の miss が所定の window 範囲で指定回数に達するまでコピーを保留します。既に発生した miss の処理を変える設定ではなく、将来の swap slot 用コピーの受付を絞る設定です。

## 値と判定

値は `foresight_swap_from_env()` 内の `env_int` helper で `std::getenv()` から取得し、`std::atoi()` で整数化した後、下限 `1` に clamp します。上限 clamp はありません。

| 環境値 | 実装上の結果 |
| --- | --- |
| 未設定 | 既定値 `1`。通常 miss の最初の発生でコピー要求の判定を通る |
| 空文字 | `atoi("")` は `0` となり、下限 clamp により `1` |
| `0`、負値 | `1` に clamp |
| 正の整数 `N` | 閾値 `N`。通常 miss は閾値に達するまでコピー要求を保留。`N > 255` は miss counter の上限に届かないため、通常 miss からは閾値を満たせない |
| 整数として読めない文字列 | `atoi` の結果 `0` となるため `1` |
| 数字で始まり後続に数字以外がある文字列 | `atoi` が読む数値部分を使い、その後に下限 clamp |

変換エラーを個別に報告する処理はありません。環境変数の値を `1` と文字列比較する処理でもありません。根拠: `src/core/expert_source.cpp:6537-6552`。

## 有効になる条件

- この設定を読むのは CUDA の serve 経路で `ForesightSwap` を構成するときです。生成処理は `foresight_swap_from_env()` を呼び、戻った swap pool を dispatch と expert source に接続します（`src/program/generate.cpp:11108-11121`）。
- 先に `STRATA_FS_SLOTS` を `atoi` で読み、値が `1` 未満なら pool を作らず return します。この場合 `STRATA_FS_ADMIT` は読み取られず、効果もありません（`src/core/expert_source.cpp:6537-6541`）。
- `STRATA_VERIFY_DEVICE_PLAN` が設定され、その `atoi` 結果が非ゼロの場合も、pool 作成前に return します。この場合は stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` を出し、`STRATA_FS_ADMIT` は読み取りません（`src/core/expert_source.cpp:6542-6545`）。
- pool が有効でも、通常の miss 受付閾値を適用するのは `note_miss()` 経由のコピー要求です。router look-ahead からの `predict()` 要求は閾値判定を迂回します（`src/core/expert_source.cpp:6461-6469,6472-6482`）。look-ahead が pool に接続されるのは look-ahead が存在するときです（`src/program/generate.cpp:11118-11120`）。

## 実行時の詳細

`STRATA_FS_ADMIT` は pool 構成時に読み取り、`ForesightSwap::admit` に保存します。pool 稼働中に環境を変更しても再読み取りはありません。各 `(layer, expert)` の miss counter は pool 初期化時に 0 で作られます。通常 miss では、完了済み verify window 数 `now` が前回記録時から 4 を超えて進んでいれば counter を 0 に戻し、その後 miss counter を最大 255 まで増やします。counter が `admit` 未満ならその miss でのコピー要求を終え、閾値に達した場合は通常の予算・pinned source・空き slot などの条件確認へ進みます（`src/core/expert_source.cpp:6302-6311,6472-6513`）。したがって値が 1 より大きくても、予算超過、pinned arena に source がない、blob がない、再利用可能な slot がない場合にはコピーされません（同 `6483-6504`）。

dispatch は resident cache、peer GPU、helper にない expert について foresight slot を調べます。slot が利用できなければ `note_miss()` を呼んだ後、既存の miss 経路で PCIe staging 条件を確認し、それ以外は元の miss 処理を続けます。`STRATA_FS_ADMIT` はその miss を即座に処理するかどうかを変更せず、Foresight swap 用のコピー予約だけを制限します（`src/core/expert_source.cpp:4977-5005`）。閾値を通過したコピー要求は fill thread の queue に入り、host blob から CUDA device slot への非同期コピーが行われます。コピーに失敗すると stderr に `strata serve: foresight swap: a copy failed - swap space off` を出し、pool は以後の要求を受け付けません（同 `6377-6401,6472-6521`）。

pool 作成に成功すると stderr に slot 数、card 数、budget、`admit after %d miss(es)`、再利用までの window 数が出ます。この `%d` が clamp 後の実値です。`docs/DETAILS.md` は `STRATA_FS_SLOTS` を CUDA 向けの opt-in として記載し、測定した組み合わせで効果が確認できず off としていますが、`STRATA_FS_ADMIT` の個別測定や推奨値は記載していません（`docs/DETAILS.md:1030,1432-1437`）。

## 根拠

- 候補名の全参照: `src/core/expert_source.cpp:6550` の実読み取りと、`include/strata/core/foresight_swap.hpp:20,53` の説明コメント。実装側の読み取りは一箇所です。
- helper、既定値、下限 clamp、pool 起動ログ: `src/core/expert_source.cpp:6537-6562`。
- miss counter の初期化と時間窓判定: `src/core/expert_source.cpp:6302-6311,6472-6482`。
- copy request が満たす追加条件と queue 登録: `src/core/expert_source.cpp:6483-6521`。
- dispatch miss と look-ahead の呼び出し: `src/core/expert_source.cpp:4977-5005,3311-3315`。
- CUDA serve 経路での pool 作成・接続: `src/program/generate.cpp:11108-11129`。
