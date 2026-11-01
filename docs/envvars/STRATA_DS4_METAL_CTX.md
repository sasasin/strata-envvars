# `STRATA_DS4_METAL_CTX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 上の DeepSeek V4.1 用に、`strata::gpu` の allocator ではなく `mtl::Context` からメモリを確保する経路を有効にするためのスイッチとして実装されています。説明コメントでは、Context の GPU address と residency set を使う目的が記されています。ただし、この commit の `strata_ds4` ビルドにはこの allocator の実装ファイルが含まれず、`active()` / `alloc()` などを呼び出す箇所もありません。したがって現在の `strata_ds4` 実行ファイルでは、この変数による割当て変更は起きません。

## 値と判定

実装箇所の `enabled()` は `std::getenv("STRATA_DS4_METAL_CTX") != nullptr` の結果を `static const bool` に保存します。値の文字列は parse しません。

| 環境の状態 | `enabled()` の結果 |
|---|---|
| 未設定 | `false` |
| 空文字を設定 | `true` |
| `0`、`false`、その他の文字列を設定 | `true` |

初回の `enabled()` 呼び出し時に判定してプロセス内で cache します。その後の環境変更は再評価されません。CLI 引数、設定ファイル、別の環境変数による上書きは、この実装にはありません。根拠: `metal/src/engine/ds4_ctx.cpp:29-32`。

## 有効になる条件

ソース上では Metal の DS4 allocator 用コードですが、現行ターゲットへの組み込みが確認できません。

- `metal/CMakeLists.txt:138-147` の `STRATA_DS4_SOURCES` に `src/engine/ds4_ctx.cpp` はありません。
- `metal/CMakeLists.txt:165` はそのソース一覧と runtime object から `strata_ds4` を作ります。
- リポジトリ全体の参照検索では `strata::dsv41::metal_ctx::active()`、`alloc()`、`release()`、`host_view_of()`、`buffer_of()` の呼び出しは見つかりませんでした。

そのため、変数を設定してもこの commit の `strata_ds4` で機能が有効になる条件はありません。OS や CLI オプション、モデル状態によってこの未接続を有効化する別経路も確認できません。索引 `docs/envvars/000_envvers.md:723` には候補として載っていますが、実行ファイルで使われる環境変数であることを裏付けるビルド・呼び出し経路はありません。

## 実行時の詳細

未接続の実装を直接呼び出した場合、`alloc(bytes)` は無効時に `nullptr` を返します。有効時は要求サイズを 16,384 byte 単位に切り上げて `cx().alloc(rounded)` を呼びます。サイズ 0 を除外する判定や、丸め計算の overflow 検査はありません。成功したバッファは GPU address ではなく CPU 側ポインターをキーにした map に記録し、そのポインターを返します。Context は `alloc()` が必要になったとき初期化されます。割当て結果の `handle` または `ptr` が無効なら stderr に `dsv41 metal: Context::alloc(%zu) failed` を出して `nullptr` を返します。呼び出し元や fallback はこの未接続コードにはありません。根拠: `metal/src/engine/ds4_ctx.cpp:34-55`。

同ファイルには map を使う `host_view_of()` / `buffer_of()` と、登録済みバッファを Context に返して map から除く `release()` もありますが、これらにも呼び出し元はありません（`metal/src/engine/ds4_ctx.cpp:57-78`）。これらのコードから実行時ログや終了経路は確認できません。上記の割当て失敗メッセージは、関数が呼ばれ割当てに失敗した場合に限るソース上の挙動です。

## 根拠

- 環境変数の読み取り・cache: `metal/src/engine/ds4_ctx.cpp:29-32`
- 無効時の戻り値、サイズ丸め、Context 割当て、失敗ログ、map 登録: `metal/src/engine/ds4_ctx.cpp:42-55`
- 補助関数: `metal/src/engine/ds4_ctx.cpp:57-78`
- DS4 実行ファイルのソース一覧とリンク対象: `metal/CMakeLists.txt:138-147`, `metal/CMakeLists.txt:155-171`
- Metal が独立した DeepSeek エンジンを持つという製品経路の説明: `docs/MAC.md:3-7`

この文書はコードを静的に調査した結果です。ビルド、実行、GPU での動作確認はしていません。
