# `strata --expert-profile-save`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--expert-profile-save` |
| 別名 | なし |
| 値 | 保存先ファイルのパス `P` |

## 役割

`--serve` で動く適応型 expert tier が実行中に数えた routing と現在の VRAM 常駐状態から、全 `(layer, expert)` の順位を profile ファイルに保存します。次回起動時に `--expert-profile` へこのファイルを渡すと、その順位を初期 profile として利用できます。オプションを省略した場合は routing の集計も保存も行われません（`engine/src/program/generate.cpp:933-937, 1407-1410`）。

## 使い方

```sh
./strata --serve --pack /path/to/pack --native /path/to/model.gguf \
  --expert-profile /path/to/initial-profile.bin \
  --expert-profile-save /path/to/learned-profile.bin
```

`--serve`、モデル・pack の指定に加え、適応型 tier が使う `--expert-profile` を指定する例です。`/path/to/learned-profile.bin` はエンジンが書き込む保存先です。

## 値と既定値

- `P` は `next()` で次の argv 要素から文字列として受け取り、`expert_profile_save` に格納します。省略時は空文字列で、保存は無効です。オプション自体のパス存在確認や親ディレクトリ検証は parser にありません（`engine/src/program/generate.cpp:935-937, 3842-3847, 4211-4216`）。
- 値を省略して argv の末尾に置くと、`--expert-profile-save needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- 同じオプションを複数回指定した場合は parser が同じ文字列メンバーへ順に代入するため、最後の値が残ります（`engine/src/program/generate.cpp:3842-3847, 4212`）。
- 保存間隔は別オプション `--expert-profile-save-every MIN` で、既定値は 10 分です。0 以下では定期保存の条件を満たさなくなりますが、終了時保存は引き続き行われます（`engine/src/program/generate.cpp:937, 1407-1410, 4215-4216, 18503-18507, 23958`）。

## 実行時の動作

- 実際の保存処理は serve ループにあり、終了時（`QUIT` または stdin の終了）に `save_profile("exit")` を呼びます。定期保存は、次の要求を処理する前に、前回保存から設定時間が経過していて、その行が `QUIT` ではない場合に行われます（`engine/src/program/generate.cpp:18503-18507, 23958`）。
- 保存用の集計 `heat` は、`--expert-profile-save` が指定され、全 expert が常駐しておらず、適応型 tier の usage と host residency が利用可能なときに初期化されます。適応型 tier が無効、または residency 情報がないときは `--adapt-every` と `--adapt-swaps` が 0 より大きいこと、および `--expert-profile` が必要だと stderr に出します。その場合、エンジンは処理を継続しますが保存用集計は作られず、ファイルも保存されません。全 expert が常駐している場合もこの保存用集計の初期化条件から外れます（`engine/src/program/generate.cpp:14932-14933, 15091-15101`）。
- 適応型 tier の各 routing 集計時に `drive.d.usage` を `heat` へ加算します（`engine/src/program/generate.cpp:15800-15808`）。保存順位は、まず現在 resident の expert、次に累積 routing 数の降順、同数なら起動時 profile の順位、最後に pair の index 順です。保存ファイルには全 `(layer, expert)` pair が順位付けされます（`engine/src/program/generate.cpp:15955-15967`; `engine/src/core/expert_cache.cpp:246-272`; `engine/include/strata/core/expert_cache.hpp:57-66`）。
- profile の読み込み用データは、起動時の `--expert-profile` から読み込んだ順位を保存処理の prior として保持します。GPU layer split 時も split 後の `profile` ではなく、読み込み時の全順位を保持するために保存用コピーを取ります（`engine/src/program/generate.cpp:6790-6793`）。

## 適用条件と副作用

- help の説明と保存処理は `--serve` 用です。通常の非 serve 実行経路でこの値が使われる保存箇所は確認できません（`engine/src/program/generate.cpp:933-935, 1407-1410, 15091-15101, 23958`）。
- 保存先には `<P>.tmp` を作成し、内容を書き終えた後に `<P>` へ rename します。rename は既存の `<P>` を置き換えます。途中のファイルを読み手に見せないための書き込み方式です（`engine/src/core/expert_cache.cpp:294-314`; `engine/include/strata/core/expert_cache.hpp:68-71`）。
- 親ディレクトリが存在しない、書き込み権限がない、または書き込み・rename に失敗する場合は保存できません。失敗時は `.tmp` を削除し、stderr に理由を出します（`engine/src/core/expert_cache.cpp:296-312`; `engine/src/program/generate.cpp:15967-15972`）。
- CLI 値の相対パスをどの作業ディレクトリ基準で解決するかは、エンジン側のこの parser・書き込み処理からは確認できません。保存間隔と config の相対パス処理を行う Terminal のラッパー経路はこの CLI 文書の対象外です。

## 出力とエラー

- 保存に成功すると stderr に `strata serve: expert profile saved to <P> (periodic|exit)` と出ます。書き込みに失敗すると `strata serve: the expert profile was not saved: <理由>` と出ます（`engine/src/program/generate.cpp:15967-15972`）。
- 適応型 tier の利用条件を満たさない場合は stderr に `--expert-profile-save needs the adaptive tier (--adapt-every and --adapt-swaps above 0) and --expert-profile: nothing will be saved` と出ます（`engine/src/program/generate.cpp:15094-15099`）。
- 書き込み失敗はこの処理ではログ出力に留まり、保存関数の失敗を終了コードへ変換する処理はありません（`engine/src/program/generate.cpp:15967-15972`）。parser の値不足は前述の通り終了コード 2 です。

## 根拠

- `engine/src/program/generate.cpp:933-937, 1407-1410, 4211-4216` — 値の格納、保存間隔の既定値、help 上の serve 限定説明。
- `engine/src/program/generate.cpp:3842-3847` — 値不足時の stderr と終了コード。
- `engine/src/program/generate.cpp:6790-6793, 14932-14933, 15091-15101, 15800-15808, 15955-15972, 18503-18507, 23958` — prior の保持、適用条件、routing 集計、保存・定期実行・終了時実行。
- `engine/include/strata/core/expert_cache.hpp:57-72`、`engine/src/core/expert_cache.cpp:246-314` — 順位規則、ファイル形式、`.tmp` 経由の書き込みと失敗処理。
