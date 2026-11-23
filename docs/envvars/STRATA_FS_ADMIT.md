# `STRATA_FS_ADMIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_FS_SLOTS` で有効にした Foresight swap において、GPU swap slot にコピーする対象を、通常の expert cache ミスから何回観測した後に採用するかを指定する。既定値 1 ではミスのたびにコピー候補として進み、2 以上では同じ `(layer, expert)` の最近のミス回数がしきい値に達するまで通常ミスからのコピー要求を抑える。これはコピー候補を選ぶ条件であり、GPU slot が空いていることやコピーが完了して実際に利用できることを保証しない。読み取りと設定は `engine/src/core/expert_source.cpp:7294-7311`、miss 回数によるゲートは同 `:7218-7238`。

## 値と判定

読み取りは `foresight_swap_from_env` の生成時に行う。`STRATA_FS_SLOTS` を `std::getenv` と `std::atoi` で先に読み、値が 1 以上の場合にだけ設定用 lambda が `STRATA_FS_ADMIT` を読む。lambda は未設定なら既定値 1、設定時は `std::atoi` の結果を使い、1 未満を 1 に clamp する。文字列全体の妥当性検査はなく、`atoi` の数値接頭辞変換に従う（例: `2tail` は 2、空文字・`true`・`0`・`-3` は 0 以下となり 1）。先頭空白や符号は `atoi` の変換規則に従い、大文字小文字は数値判定に関係しない。根拠: `engine/src/core/expert_source.cpp:7294-7311`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・特別扱いとなる値 |
|---|---|---|---|
| `STRATA_FS_SLOTS` が `atoi` で 1 以上 | 1 | `1` は各通常ミスをしきい値通過、`2`〜`255` は同じ expert の miss 回数がその数に達したとき通過 | 空文字、`0`、`-1`、`true` は 1 に clamp。`2tail` は 2 として扱う。`256` 以上は整数しきい値として保持されるが、回数カウンターは 255 で飽和するため通常ミスからは到達しない |
| `STRATA_FS_SLOTS` が未設定または `atoi` で 1 未満 | この変数を読まず Foresight swap 自体を作らない | 該当なし | `STRATA_FS_ADMIT` の値は適用されない |

通常ミスの回数カウンターは layer と expert ごとに保持され、最後の miss から完了 window 数が 4 を超えた場合にリセットされる。カウンターの上限は 255。look-ahead 由来の予測コピーはこの回数条件を適用しない。根拠: `engine/src/core/foresight_swap.hpp:49-54`、`engine/src/core/expert_source.cpp:7231-7238`。

## 有効になる条件

- `STRATA_FS_SLOTS` が設定され、`std::atoi` の結果が 1 以上であること。0 以下や未設定では swap pool を作らず、この変数も読まない。生成経路での有効化と pool への接続は `engine/src/program/generate.cpp:14794-14807`。
- `STRATA_VERIFY_DEVICE_PLAN` または `STRATA_VERIFY_DEVICE_HITS` が設定され、`std::atoi` の結果が非 0 の場合、Foresight swap は無効化される。`STRATA_FS_ADMIT` は pool 作成前に読まれない。警告は `engine/src/core/expert_source.cpp:7299-7305`。
- pool の初期化に成功すること。初期化時の CUDA device memory または copy event の作成失敗では pool を破棄し、swap を無効にする（`engine/src/core/expert_source.cpp:7059-7113`、作成元の失敗ログは同 `:7313-7316`）。この値の読み取り・判定箇所に OS や build macro による分岐はない。pool 初期化は CUDA runtime API を呼ぶ。
- しきい値は `note_miss` から来る通常ミスにだけ適用される。expert が pinned source にあり、blob が取得でき、カードごとの window budget に空きがあり、再利用可能な slot があることもコピー成立に必要。これらの条件を満たさない候補はコピーされない（`engine/src/core/expert_source.cpp:7234-7269`）。
- Router look-ahead の予測要求は `STRATA_FS_AHEAD` が未設定または非 0 で look-ahead が起動している場合に swap pool に届く。予測要求は `STRATA_FS_ADMIT` の miss しきい値を迂回する。look-ahead の起動条件は `engine/src/program/generate.cpp:10210-10225`、予測要求は `engine/src/core/expert_source.cpp:7223-7227` と `:7234-7238`。

## 実行時の詳細

`foresight_swap_from_env` が pool を作る際に一度読み、`ForesightSwap::admit` に保存する。pool 作成後に環境を変更しても、その pool のしきい値は読み直されない。別の pool 作成時にはその時点の環境を読み取る。CLI 引数による `STRATA_FS_ADMIT` の上書きはこの読み取り経路にはない（`engine/src/core/expert_source.cpp:7294-7311`）。

通常ミスでは `(layer, expert)` ごとのカウンターを更新し、最後の miss から完了 window 数が 4 を超えていれば回数をゼロに戻す。`admit > 1` の場合、カウンターが `admit` 未満ならその場で戻り、しきい値到達後に限って slot 探索と copy queue 登録へ進む。生成 loop は処理 window の完了ごとに pool の `completed` を増やす（`engine/src/core/expert_source.cpp:7231-7238, 7240-7278`、`engine/src/program/generate.cpp:22304, 23019`）。

threshold を通過した候補でも、GPU slot への非同期コピーがまだ完了していれば、その時点では pool から利用できない。expert dispatch は pool の `take` が成功した場合にだけ GPU group として扱い、成功しない場合は通常の miss 経路を続ける（`engine/src/core/expert_source.cpp:5583-5606`）。

## ログと測定値

初期化成功時は stderr に、実際に採用されたしきい値を含む `strata serve: foresight swap: %d slots per layer on %zu card(s), up to %d copies per card and window, admit after %d miss(es), reuse after %d windows` を出す（`engine/src/core/expert_source.cpp:7318-7320`）。値が低すぎる／高すぎる場合や、miss がしきい値未満で抑制された場合に個別の警告を出す処理は確認できない。測定値はこの変数の実装箇所に記載されていない。

## 根拠

- 読み取り条件、`atoi`、既定値、下限 clamp、成功ログ: `engine/src/core/expert_source.cpp:7294-7320`
- pool の miss counter と admission gate: `engine/include/strata/core/foresight_swap.hpp:49-54`、`engine/src/core/expert_source.cpp:7218-7238`
- pool の有効化と dispatch への接続: `engine/src/program/generate.cpp:14794-14807`
- 通常ミス時の pool 利用: `engine/src/core/expert_source.cpp:5583-5606`
- Router look-ahead の起動と予測要求: `engine/src/program/generate.cpp:10210-10225`、`engine/src/core/expert_source.cpp:7223-7238, 3791-3793`
- pool 初期化と失敗経路: `engine/src/core/expert_source.cpp:7059-7113, 7313-7316`
