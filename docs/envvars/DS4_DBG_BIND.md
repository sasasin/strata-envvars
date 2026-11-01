# `DS4_DBG_BIND`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal 版 DSV41 エンジンの初期化時に、GPU メモリの書き込み経路を 2 通り試す診断です。1つ目は `host_view` をページ境界に合わせて `mtl::Context::wrap` で包み、`mtl::Arg::B` としてカーネルに渡す方法です。2つ目は GPU ポインターを値引数 `mtl::Arg::V` で渡す方法です。両カーネルは先頭 4 要素へ定数を書き、ホスト側で読み戻した値を stderr に出します。通常のモデル計算の設定や CLI オプションではありません。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | バインド診断を実行しない |
| 空文字を設定 | 診断を実行する（`getenv()` が null でないため） |
| 空でない任意の値 | 診断を実行する。文字列比較や数値変換はしない |

この環境変数自体に数値の境界・無効値・CLI による上書きはありません。診断用割り当てサイズには別変数 `DS4_MEM_GB` が関係し、未設定なら 4096 bytes、設定されていれば 64 MiB です。こちらも値の内容ではなく設定有無で分岐します。

## 有効になる条件

- `metal/src/engine/ds4_finish.cpp` がビルドされる Metal エンジン経路に限られます。Metal CMake ターゲットは同ファイルと `src/dsv41` のエンジンソースを含めます。
- `ensure()` が初めて呼ばれ、`ds4_init.metal` のコンパイルに成功して `g_lib >= 0` であることが必要です。コンパイル失敗時は既存の `dsv41 metal: compiling ds4_init.metal failed` ログが出ますが、この診断は走りません。
- `cudaMalloc` が成功したときだけ診断本体に入ります。失敗時の専用警告・エラー出力はこの箇所にはありません。
- `DS4_DBG_BIND` は CLI 引数や他の設定値で上書きされません。`DS4_MEM_GB` は診断領域の大きさだけを変えます。

## 実行時の詳細

各 Metal エンジン操作は `ensure()` を呼びます。初回呼び出しではコンテキストと Metal ライブラリを作成・コンパイルし、その直後に `DS4_DBG_BIND` を確認します。以降は `g_cx` が設定済みなので `ensure()` は早期 return し、この環境変数を再確認しません。従って初回確認後にプロセス環境を書き換えても診断状態は変わりません。

診断領域の先頭を `host_view` 経由で包むカーネル `ds4_test_write` は 4 要素へ `3.0f` を書き、GPU ポインターを値として受け取る `ds4_test_write_v` は 4 要素へ `7.0f` を書きます。それぞれの実行後に `flush_runs()` と `cudaMemcpy` を呼び、読み戻した 4 個の値を次の形式で stderr に出します:

- `DBG bind A (wrap host_view + Arg::B): %g %g %g %g`
- `DBG bind B (device pointer by value): %g %g %g %g`

この診断ブロックには読み戻し値の比較、失敗時の専用終了処理、明示的な検証結果判定はありません。診断実行後は一時領域を `cudaFree` します。`ensure()` はその後も通常の Metal 操作から呼ばれ、同関数の戻り値は `g_lib >= 0` に基づきます。

## 根拠

- 候補一覧には名前があります: `docs/envvars/000_envvers.md:140`。Strata 全体を完全一致検索し、候補名の直接参照は以下の 1 箇所と確認しました。動的な名前を受ける `ds4_dbg(const char*)` helper はありますが、呼び出し一覧に `DS4_DBG_BIND` はなく、この名前は helper 経由ではありません。
- Metal ソースと設定有無判定、ライブラリのコンパイル、診断の割り当て・実行・ログ: `metal/src/engine/ds4_finish.cpp:62-120`。`ensure()` を通る操作例は `metal/src/engine/ds4_finish.cpp:136-143`、同ファイル内に他の `ensure()` 呼び出しもあります。
- 2 つの診断カーネルが書く値: `metal/src/engine/msl/ds4_init.metal:2591-2598`。
- Metal ターゲットへの実装組み込み: `metal/CMakeLists.txt:132-142`。
- 共通の `ds4_dbg` helper は Metal でのみ環境を検索し、その他では常に false を返します: `src/dsv41/ds4_launch.h:30-36`。ただし `DS4_DBG_BIND` の直接参照はこの helper を通らず、Metal 側 `ensure()` にあります。
