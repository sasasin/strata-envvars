# `FNX_KV_PAGES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next の split engine は、この変数を K/V page 数の設定には使いません。`Engine` の生成時に、27B 向け設定が誤って渡されたかを確かめる名前の一覧に含めています。変数が設定されていると、値の内容にかかわらず `Engine` の生成をエラーにします。したがって、`FNX_KV_PAGES` に数値を設定しても Flash-Next の K/V pool サイズは変わりません。

## 値と判定

| 状態 | 判定と結果 |
| --- | --- |
| 未設定 | この名前については何もしない。後続の engine 初期化へ進む |
| 空文字を設定 | `std::getenv` は非 null を返すため設定ありと判定し、例外を投げる |
| 任意の非空文字列 | 値を parse せず設定ありと判定し、例外を投げる。数値、符号、範囲の検証や fallback はない |

環境変数名はループ内の `std::getenv(k)` に渡されます。`FNX_KV_PAGES` は他の 27B 向け名と同じ存在確認だけを受け、数値読み取り用の `env_int` には渡されません（`src/split/src/engine.cu:31-36`）。

## 有効になる条件

- `src/split/src/engine.cu` の Flash-Next `Engine` が生成されるときに検査されます。sFNX サーバーはモデル読み込み後に `e.emplace(...)` で engine を作ります（`src/split/tools/sfnx.cpp:1051-1060`）。`fnx_run` の通常コマンド経路も `Engine` を構築します（`src/split/tools/fnx_run.cpp:978-988`）。
- 対象の split build は `FNX_27B=0` を定義して `engine.cu` を含めます（`src/split/CMakeLists.txt:66,102-114,153-160`）。この検査自体に OS、GPU backend、CLI 値、モデル page 数による条件分岐はありません。
- `fnx_run` の `exact`、`read`、`batch`、`compare`、`decode`、`bdecode`、`cache2` などの lab mode は、まず別の `lab_check` 経路へ進みます（`src/split/tools/fnx_run.cpp:960-962,978-982`）。その経路で `Engine` を生成した場合に検査が行われます。
- `FNX_KV_PAGES` が未設定でも、この検査がないというだけで、ページ数の明示設定が可能になるわけではありません。少なくともこの Flash-Next 実装には、この変数を K/V page 数へ反映する読み取りはありません。

## 実行時の詳細

コンストラクタは、`FNX_PF_SKIP`、`FNX_PF_SKIP_CONFIRM`、`FNX_PF_SCORE_MIB`、`FNX_PF_WINDOWS`、`FNX_PF_SCORES`、`FNX_KV_PAGES`、`FNX_KV_RESERVE_MIB` を順に調べます。対象名が設定されていれば、たとえば `FNX_KV_PAGES=4096` の場合は `FNX_KV_PAGES is the 27B's: Flash-Next has nothing it sets` という `std::runtime_error` になります。空文字も `getenv` が null でないため同じ経路です。値は保存・cache されず、`Engine` を作るたびにその時点のプロセス環境を検査します（`src/split/src/engine.cu:31-36`）。

エラーは `sfnx` の初期化 catch から `ERR <理由>` を出力し、stderr に `sfnx: failed: <理由>` を書いて終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1055-1062`）。`fnx_run` では最上位 catch が stderr に `fnx_run: <理由>` を書き、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 根拠

- `src/split/src/engine.cu:31-36` — Engine constructor 内の動的な環境変数名チェックと例外文。
- `src/split/CMakeLists.txt:66,102-114,153-160` — Flash-Next engine source と `FNX_27B=0` の build 定義。
- `src/split/tools/sfnx.cpp:1030-1035,1051-1062` — sFNX の engine 初期化と失敗時の出力・終了。
- `src/split/tools/fnx_run.cpp:960-962,978-988,1364-1373` — fnx_run の Engine 生成経路と例外処理。
- `docs/envvars/000_envvers.md:545-546` — 候補一覧には `FNX_KV_PAGES` と `FNX_KV_RESERVE_MIB` がある。コード上の現状は、Flash-Next の K/V pool 設定ではなく、設定されている場合に拒否するチェックである。
