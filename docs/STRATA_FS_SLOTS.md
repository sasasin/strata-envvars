# `STRATA_FS_SLOTS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert cache に入っていない expert のコピーを一時的に置く、layer ごとの VRAM swap slot 数を指定します。通常なら CPU へ割り当てられる expert のうち、コピーが完了済みのものを GPU group として計画できます。slot は expert cache とは別に確保されるため、その分だけ cache に使える VRAM が減ります。

実装は `src/core/expert_source.cpp` の `ForesightSwap` と `src/program/generate.cpp` の expert 計画処理にあります。環境変数を読む主経路は CUDA runtime を使う C++ generate/serve 経路です。SYCL 側の `sycl/src` にはこの変数の参照がなく、この機能の実装は確認できませんでした。

## 値と判定

値は `std::atoi` で変換され、変換結果が 1 以上の場合だけ swap space を作ります。未設定は 0、空文字や数値で始まらない文字列も 0 となり、無効です。`atoi` は文字列全体の厳密な数値検証をしないため、先頭の空白と符号の後に数字があればその数値を読み、数字の後ろに文字があっても読み取った数値を使います（例: `" 3x"` は 3、`"-2"` は無効）。

slot 数として実際に使う値は `min(変換値, 64)` です。したがって 65 以上を指定しても各 layer につき最大64 slotです。設定値に 1 以上の数字が含まれていても、変換結果が 0 以下なら無効です。

## 有効になる条件

- `STRATA_VERIFY_DEVICE_PLAN` が設定され、`atoi` の結果が 0 以外の場合は初期化を拒否します。stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` と出ます。
- 初期化には CUDA device memory、layer ごとの expert blob サイズに応じた slot 領域、copy stream と event の確保が必要です。VRAM 確保または stream 作成に失敗した場合は `cannot allocate ... MiB on CUDA... (raise --vram-reserve-mib by about that much)`、event 作成失敗時は `cannot create the copy events` を出して機能を無効にします。
- 実際に slot へ expert をコピーするには、その expert が cache に存在せず、peer GPU にもなく、remote helper にも割り当てられておらず、`d.src` がその expert の pinned host blob を持つ必要があります。slot が未到着、空きなし、または当該 window の copy 上限に達した場合も、その場では swap slot を使わず通常の処理に戻ります。
- Router look-ahead からの先行コピーは別条件です。`STRATA_FS_SLOTS` の正の値に加え、source が存在し、`STRATA_FS_AHEAD` が未設定または `atoi` 結果が 0 以外で、`STRATA_LOOKAHEAD` も未設定または `atoi` 結果が 0 以外である必要があります。予測機能が利用可能な場合は look-ahead が次 layer 向けの候補を `predict()` に渡します。これは slot 数の有効化そのものとは別の動作です。

## 実行時の詳細

generate/serve の expert 計画を構築するときに `foresight_swap_from_env()` が値を読み、slot pool を初期化します。この箇所には `static` cache がないため、各構築時に環境を読みます。初期化後の slot 数はその pool の寿命中固定です。初期化成功時は stderr に slot 数、カード数、カード/window ごとの copy 上限（既定32）、miss admission（既定1）、slot 再利用までの window 数（既定4）を出します。これらの別設定はそれぞれ `STRATA_FS_BUDGET`、`STRATA_FS_ADMIT`、`STRATA_FS_DEPTH` で、最低値は順に1、1、2です。

miss または look-ahead prediction がコピーを要求すると、filler thread が pinned host blob から専用 copy stream へ非同期コピーし、event を記録します。dispatch 側は event が完了した slot だけを GPU group として採用し、まだ完了していなければ pending miss として通常経路に戻します。slot は参照された window の完了数を記録し、`STRATA_FS_DEPTH` 分の window が経過してから再利用できます。copy failure が起きた場合は `strata serve: foresight swap: a copy failed - swap space off` を出し、その slot は使用しません。要求があっても使用できた回数、copy 数、未到着、空きなし、予算超過などは処理末尾の `foresight swap:` report に記録されます。

## 根拠

- `src/core/expert_source.cpp:4951-4976` — `getenv` と `atoi`、0以下での無効化、`STRATA_VERIFY_DEVICE_PLAN` による拒否、64 slot 上限、初期化ログ。
- `src/core/expert_source.cpp:4740-4792,4824-4836` — layer/card ごとの VRAM 割り当て、stream/event 作成、filler thread の非同期 copy。
- `src/core/expert_source.cpp:4839-4865,4890-4936` — 到着済み slot のみ利用、miss 条件、pinned source、slot 再利用・copy 上限。
- `src/program/generate.cpp:5487-5516,8181-8199` — look-ahead の条件と swap pool の生成、予測器への接続。
- `src/core/expert_source.cpp:3730-3751` — cache、peer、remote helper を優先し、その後 swap slot を GPU group として使う経路。
- `src/program/generate.cpp:11665-11666,11967-11968,12055` — 完了 window の計数と report 出力。
- `include/strata/core/foresight_swap.hpp:2-21` — 機能の設計概要と関連設定。
- `docs/DETAILS.md:1680-1688` — slot の目的と RTX 3060、Tesla P100、RTX 5070 等での測定記録。これらは同資料に記載された条件での結果で、コードから一般的な性能向上は確認できません。資料は当該測定で cache 縮小の損失が slot の効果を上回ったとして、既定を off と説明しています。
