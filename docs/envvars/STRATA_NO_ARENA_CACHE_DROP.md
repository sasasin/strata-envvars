# `STRATA_NO_ARENA_CACHE_DROP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

統合型 AMD gfx11 GPU の Linux 実行で、expert arena へ読み込んだモデルファイルのページキャッシュを読み込み中・読み込み後に返す処理を抑止する環境変数です。値が有効なときは、expert 読み込み中のチャンクごとの `drop_behind` と、読み込み後のモデルファイル単位の処理の両方が無効になります。既定では両処理が対象デバイスで有効です。対象はファイルキャッシュへの助言処理であり、arena の読み込み自体や GPU 計算を無効にする変数ではありません（`include/strata/core/page_cache_drop.hpp:1-16,47-59`; `src/program/generate.cpp:4154-4157,8361-8376`）。

## 値と判定

`page_cache_drop::off_by_env()` は `std::getenv` で値を取得し、未設定でなく、先頭文字が空文字でも `'0'` でもないときに抑止を返します。文字列全体や数値としての妥当性は検査しません。したがって、未設定・空文字・`0`・`0anything` は抑止しません。一方、`1`、`true`、`false`、` 1`、`00`、`0.5` はいずれも先頭文字が `'0'` 以外（または空白）なので抑止します。大文字小文字の変換もありません。先頭文字だけの判定です（`include/strata/core/page_cache_drop.hpp:47-51`）。

| 条件 | unset | 抑止が有効になる値 | 抑止されない値 |
|---|---|---|---|
| 全ビルド共通の値判定 | 抑止しない | 空文字でも `'0'` でもない文字列（例: `1`, `true`, ` 1`, `00`） | 空文字、先頭が `0` の文字列（例: `0`, `0anything`） |

この値判定は「cache drop を止めるか」の判定です。実際に cache drop が既定で有効になるかは Linux・HIP・デバイス条件にも依存します（`include/strata/core/page_cache_drop.hpp:53-59`; `src/program/generate.cpp:4074-4078,4154-4157`）。

## 有効になる条件

- 実際の抑止効果があるのは、Strata が `STRATA_USE_HIP` 付きでビルドされ、`cudaGetDeviceProperties` によるデバイス情報取得が成功し、Linux 上で、可視 GPU がすべて統合型かつ同じ GCN アーキテクチャである場合です。device 0 を含む可視 GPU に異なるアーキテクチャまたは discrete GPU があると `all_igpu` が false になります（`src/program/generate.cpp:4074-4089`）。
- 対象アーキテクチャは `gfx1103`、`gfx1150`、`gfx1151` です。既定フラグは統合型でない場合と Windows では false、それ以外はこの 3 アーキテクチャとの一致で決まります（`src/core/arch_defaults.cpp:151-163`）。
- デバイス条件を満たすとエンジンが `arena_cache_drop_flag` を true にします。`enabled()` は Linux でこのフラグが true かつ環境変数による抑止がない場合だけ true です（`src/program/generate.cpp:4154-4157`; `include/strata/core/page_cache_drop.hpp:39-59`）。
- CLI 引数や別の環境変数がこの環境変数の値を上書きする分岐は確認できません。設定有無のみを見る設定優先順位もありません（候補名の読み取りは `include/strata/core/page_cache_drop.hpp:47-51`）。
- 同じ値判定でも、非 Linux ビルドでは `enabled()` が常に false です。HIP 以外のビルドではデバイス初期化ブロックがコンパイルされず、このフラグを有効にする処理は確認できません（`include/strata/core/page_cache_drop.hpp:53-59`; `src/program/generate.cpp:4074-4078,4154-4157`）。

## 実行時の詳細

デバイス初期化時に `igpu_cache_drop_default()` の結果を共有 atomic フラグへ保存します。この default 関数は `igpu_arena_no_thp_default()` と同じ判定を使います。環境変数値そのものは保存せず、`enabled()` が呼ばれるたびに `std::getenv` で読み直します（`src/core/arch_defaults.cpp:151-163`; `src/program/generate.cpp:4154-4157`; `include/strata/core/page_cache_drop.hpp:39-59`）。

Linux では expert arena の読み込み経路が `enabled()` を呼び、その時点の結果を `drop_behind` として range reader に渡します。range reader はチャンクを arena にコピーした後、読み込み元ファイルの該当範囲に `drop_range()` を呼びます。`drop_range()` は空範囲・無効 descriptor・`posix_fadvise` の失敗では false を返し、失敗は呼び出し元で無視されます（`src/core/expert_source.cpp:6323-6328`; `src/core/pinned.cu:1293-1325`; `include/strata/core/page_cache_drop.hpp:68-79`）。直接読み込みが成功する unbuffered 経路では、この range reader によるチャンク単位の処理を通りません（`src/core/expert_source.cpp:6323-6328`）。

さらに arena 読み込み後、`enabled()` が true なら、読み込み対象となった expert ファイル、pack の `dense.bin` と `embd.bin`、および `--native` の GGUF shard（PLE table を除く）を集めて `give_back()` に渡します。重複・空パスを除き、各ファイルに対して読み取り専用で開いてファイル全体を助言対象にします。失敗は件数に記録されるだけで処理を中断しません（`src/program/generate.cpp:8361-8376`; `include/strata/core/page_cache_drop.hpp:82-94,128-147`）。

この変数の値は関数呼び出しごとに再評価されるため、プロセス内で環境が変更された場合は後続の `enabled()` 呼び出しに反映されます。ただし、arena の読み込み中は一度取得した `drop_behind` 値をその読み込み処理に渡すため、読み込み途中の変更でその処理の値が変わることはありません。子プロセスへの環境引き継ぎ・上書きは、この変数について Strata ソース内で確認できません（`include/strata/core/page_cache_drop.hpp:47-59`; `src/core/expert_source.cpp:6323-6328`）。

## ログと測定値

`give_back()` 後、range 読み込み中に助言できた合計 byte 数と `Cached` の前後差がともに 0 でなければ、stderr に次の形式の行を出します。値は実行時に埋められます。

```text
strata generate: the model files' cached pages were given back after the expert load: %.1f GiB asked back during the read, %.1f GiB by the call after it (%.0f ms); the file cache is %.1f GiB now (STRATA_NO_ARENA_CACHE_DROP=1 keeps it)
```

空文字・`0` 始まりの値、または対象外のビルド・デバイスでは cache drop とこの処理後ログは発生しません。範囲・ファイル単位の助言失敗だけを理由とするログやエラー終了はありません。ログが出ないことは、すべてのキャッシュページが実際に返された／返されなかったことの証明にはなりません（`include/strata/core/page_cache_drop.hpp:128-159`; `src/program/generate.cpp:8366-8376`）。

`docs/DETAILS.md` にこの変数の説明や、この処理に対応する測定値は見つかりませんでした。ソースコメントの測定状況は Radeon 780M の特定構成について記されていますが、対象変数の on/off 比較ではないため、この文書では性能値を記載しません（`include/strata/core/page_cache_drop.hpp:1-16`）。

## 根拠

- `include/strata/core/page_cache_drop.hpp:39-59` — 有効フラグ、環境変数判定、Linux 条件。
- `src/core/arch_defaults.cpp:151-163` — 対象デバイスの既定判定。
- `src/program/generate.cpp:4074-4089,4154-4157` — HIP デバイス検出と既定フラグ設定。
- `src/core/expert_source.cpp:6323-6328`、`src/core/pinned.cu:1293-1325` — arena 読み込み中の range 処理。
- `src/program/generate.cpp:8361-8376`、`include/strata/core/page_cache_drop.hpp:82-94,128-159` — 読み込み後のファイル処理とログ。
