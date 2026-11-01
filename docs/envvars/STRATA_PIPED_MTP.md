# `STRATA_PIPED_MTP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`--batch-mtp` の draft proposal を、layer split 上で並行実行する `--batch-groups` の各グループにも載せる opt-in 設定です。通常の pipelined groups は slot ごとに1行を処理し MTP draft を実行しません。この変数と `--batch-mtp` が有効なら、slot の token と proposal 行を同じ group window に載せ、最終 stage が proposal を判定した後、各 stage が採用行を commit します。設定がなければ既定の動作は変わりません。(`src/program/generate.cpp:6044-6045,6073-6083`; `docs/BATCHING.md:476-490`)

## 値と判定

読み取りは `batch_groups_for()` 内の `std::getenv()` と、piped MTP 時の `std::atoi()` です。文字列全体を真偽値として parse せず、最初に空でなく `0` でもない文字かを有効判定に使います。その後、proposal 数は `atoi` の結果を下限1、上限 `min(--spec - 1, kVerifyNarrowT - 1)` に clamp します（上限側も最低1）。(`src/program/generate.cpp:6028-6045,6077-6083`)

| 値 | piped MTP の要求判定 | 要求が有効になった場合の proposal 数 |
|---|---|---|
| 未設定、空文字、先頭文字が `0` | 無効 | 計算しない |
| 先頭文字が `0` 以外の非空文字列 | 有効 | `atoi` の値を `[1, min(--spec - 1, kVerifyNarrowT - 1)]` に clamp |

`atoi` は10進整数の先頭部分を読み、後続の非数字は無視します。数字部分がなければ0となり、下限 clamp により1 proposalになります。したがって `2junk` は2、`junk` は1、`-3` は1です。先頭が `0` の `0junk` は有効判定の段階で無効ですが、` 0` は先頭が空白なので要求は有効となり、数値0を1へ clamp します。上限は `--spec` と narrow verifier window に依存し、上限超過は clamp されます。`atoi` に整数型で表せない値を渡した場合の結果は実装で保証されません。

## 有効になる条件

環境変数が要求されても、次の条件が揃わなければ piped MTP は動きません。

- `--batch-mtp` または `STRATA_BATCH_MTP` が有効である。CLI と環境変数は OR 条件です。後者も未設定・空文字・先頭 `0` 以外を有効と判定します。(`src/program/generate.cpp:6047-6049`)
- `--batch` が2以上、`--mtp` が指定され、`--spec T` が `T >= 2`、`--serve` が指定されている。
- layer split があり、各 stage が別 GPU 上にある（`split_same` ではない）。
- 環境変数の読み取り自体には OS や `STRATA_USE_HIP` による条件コンパイル分岐がありません（同じ箇所で `STRATA_USE_HIP` により条件分岐するのは別設定 `STRATA_BATCH_GROUPS_NV_SERIAL` の扱いです）。実際に動く範囲は `strata` の GPU layer split / batch serving 経路です。(`src/program/generate.cpp:6038-6045,6073-6076`; `CMakeLists.txt:868`; `cmake/hip_backend.cmake:98`)
- group 数が2以上である。`--batch-groups 1` や、解決後に1 groupとなる場合は対象外。layer split で `--batch-groups` を省略した場合は通常 auto で複数 group になりますが、他の group 設定で1 groupに解決されることがあります。明示した group 数または `auto` は group resolver に渡されます。(`src/program/generate.cpp:6028-6045,6050-6063`; `include/strata/program/batch_groups.hpp:92-115`)
- helper expert cache を layer split で使っていない。`STRATA_BATCH_SELF_COMMIT` が未設定・空・先頭 `0` である。
- slot 数と proposal 数からなる group window（`slots/group × (1 + proposals)`）が `kVerifyNarrowT` 以下である。過大な場合は `STRATA_PIPED_MTP is off` の警告を出し、piped MTP を無効にします。(`src/program/generate.cpp:6064-6067,6218-6245`)

前段の `--batch-mtp` 条件が不足する場合は `--batch-mtp is off: ...` の警告が出て batch MTP 自体が無効になります。piped MTP が要求されても group が足りない、`STRATA_BATCH_SELF_COMMIT` が有効、または window が大きすぎる場合は `STRATA_PIPED_MTP is off: ...` を stderr に出して piped MTP だけを無効にします。どちらもこの gate ではエンジンを終了させず、可能なら通常の batch/pipeline 経路を続けます。(`src/program/generate.cpp:6068-6071,6236-6244`)

## 実行時の詳細

設定値は起動後、batch group の解決時に `batch_groups_for()` から読み取られます。slot の VRAM fit を確定した後にも group と piped MTP の可否を再評価し、最終結果を決めます。static cache はありませんが、実行中の生成ループでこの環境変数を再読する箇所はありません。proposal 数も初期化時に決まり、その後は各 slot の draft chain に使われます。(`src/program/generate.cpp:6028-6045,6077-6083,6218-6245`)

有効時は group window に各 slot の現 token と最大 N proposal を含めて検証します。proposal は少なくとも1つを作り、前の proposal の draft 層確率が `--spec-min-p` 以上なら次も追加します。最終 stage が proposal の一致を判定し、各 stage は採用行を commit します。slot ごとの次の draft は非同期 chain で開始し、slot の状態を別経路が読む前や pipeline を drain するときに commit/draft の完了を待ちます。(`src/program/generate.cpp:13017-13028,13082-13104,13106-13221`; `docs/BATCHING.md:482-490`)

起動時の成功時は stderr に `STRATA_PIPED_MTP: <groups> pipelined groups ... draft up to <N> MTP proposal(s) per slot each window` と出ます。slot draft chain の準備失敗や deferred commit 初期化失敗は `strata serve: ...` を stderr に出し、`return 1` で起動を失敗させます。実行中の chain や commit 失敗は `ERR ...` を stdout に出し、処理 loop が失敗を返します。event 作成失敗は stderr に `strata serve: STRATA_PIPED_MTP: event creation failed` を出して終了コード1の経路です。(`src/program/generate.cpp:6236-6244,10211-10217,10231-10236,13074-13080,13182-13201`)

`docs/BATCHING.md` は opt-in、必要条件、行の commit/draft の流れを実装と同様に説明しています。同文書の性能値は2x RTX A6000 48 GB、Qwen3.8-Flash-Next IQ3_S、全 expert VRAM resident、`--batch 4 --batch-groups auto` 等の条件下での測定として掲載されており、ここでは別環境の性能を示すものとして一般化しません。(`docs/BATCHING.md:476-510`)

## 根拠

- 値の読み取り・batch group resolver 入力: `src/program/generate.cpp:6028-6045`
- batch MTP の値と前提 gate、piped MTP 初期判定: `src/program/generate.cpp:6047-6083`
- group の auto/明示設定の解決と `mtp_piped` 判定: `include/strata/program/batch_groups.hpp:51-71,92-115`
- helper cache と slot/group 確定後の最終 gate、警告・成功ログ: `src/program/generate.cpp:6218-6245`
- slot draft chain の準備と deferred commit: `src/program/generate.cpp:10211-10217,10220-10236`
- group window、判定・commit・次 proposal の非同期 chain: `src/program/generate.cpp:13017-13104,13106-13221`
- Strata の説明と測定条件: `docs/BATCHING.md:476-510`
