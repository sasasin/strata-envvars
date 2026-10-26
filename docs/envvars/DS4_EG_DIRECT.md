# `DS4_EG_DIRECT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows の DS4 GGUF 読み込み時に、Engram embedding tensor だけを含むファイルを通常の file mapping から外し、Engram row を非バッファ読み込みする経路を選びます。環境変数を設定するだけでは有効にならず、値が整数変換で非ゼロになり、Windows かつ GGUF の場合にだけ選択処理へ進みます。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、整数として先頭に数値がない文字列（例 `true`） | `atoi` が 0 を返すため無効 |
| 整数変換結果が 0 以外（例 `1`, `-1`, `1junk`, ` 1`） | 有効 |
| `0`, `0junk`, `0x1` | `atoi` の結果が 0 のため無効 |

文字列全体の検証はせず、`atoi` が認識する先頭の整数部分で判定します。範囲外値の扱いはコードで定義されていません。変数は初期化処理中に通常の `getenv` で参照され、結果を static cache していませんが、選択済みのファイル一覧と reader の起動は初期化時だけです。その後プロセス内で環境値を変更しても、既に起動した reader の設定は変わりません。

## 有効になる条件

- `_WIN32` のビルドであること。判定とファイル unmap の処理全体が Windows 向け `#if defined(_WIN32)` 内にあります。
- pack が GGUF であること（`pk.gguf`）。
- 少なくとも一つのファイルに `.engram.embed.` を名前に含む tensor があり、そのファイルにそれ以外の tensor がないこと。

条件に合うファイルがなければ効果はありません。対象ファイルに mapping があれば `os::unmap` して `pk.maps[i]` を空にし、reader 用の `eg_direct[i]` を立てます。Engram 以外の tensor も含むファイルは unmap されません。Windows 以外では環境変数を読むこの分岐自体がなく、`EgReader` からの非バッファ open も無効です。

## 実行時の詳細

DS4 初期化でファイル単位に tensor 名を調べ、条件に合うファイルを `EgReader::start` へ渡します。reader thread は対象ファイルを初回使用時に `os::open_unbuffered`（Windows の `FILE_FLAG_NO_BUFFERING`）で開き、行のファイル offset と長さを 4096 byte 境界に丸めた span で読みます。直接読み込みを試すのは、行が一つのファイル内にあり（MXFP8 または scale を別 tensor に持たない形式）、丸めた span が 8192 byte 以下の場合です。現行コードでの GGUF の MXFP8、Q6_K、IQ4_NL row はこの形式です。古い別 tensor scale 形式など、条件外の読み込みは通常の buffered `pread_full` に進みます。

非バッファ open または read に失敗した場合も buffered 読み込みへ fallback します。読み取りデータ自体は同じ row bytes で、MXFP8 は読み出した `[scale, 32 codes]` ブロックを codes と scales に分けます。対象ファイルが選ばれると `--verbose` 時に `ds4: <file> unmapped, its Engram rows read unbuffered` を stderr に出します。verbose の一般的な Engram reader 情報は `ds4: Engram rows read on ...` です。

`DS4_EG_CHECK` は別の診断フックです。設定有無を初回の非バッファ row 読み込み時に cache し、有効なら各 row を buffered でも読み比べます。reader 終了時に比較行数と不一致数を stderr に出します。これは `DS4_EG_DIRECT` の判定や有効化条件を変更しません。

## 文書・測定値との照合

`docs/DETAILS.md` と他の `docs/` 文書に `DS4_EG_DIRECT` の説明や測定結果は見つかりませんでした。実装コメントには「4K prompt で -8%」とありますが、比較条件・環境・反復数が記されていないため、再現可能な測定値としては扱えません。コメントはこの最適化が既定 off であることと、ある条件で遅くなった履歴を示すにとどまります。

## 根拠

- `src/dsv41/ds4_model.cu:2515-2538` — Windows/GGUF/`atoi` 判定、Engram 専用ファイルの選定・unmap、verbose ログ、reader へのフラグ渡し。
- `src/dsv41/ds4_model.cu:2542-2575` — 現行 Engram row format の判定。
- `src/dsv41/ds4_engram_io.hpp:129-137,180-205` — reader thread と対象ファイルごとの handle。
- `src/dsv41/ds4_engram_io.hpp:207-255` — 非バッファ読み込み条件、形式別処理、buffered fallback。
- `src/dsv41/ds4_engram_io.hpp:147-149,207-223` — `DS4_EG_CHECK` の比較と終了ログ。
- `src/dsv41/ds4_os.hpp:98-101,153-178` — 4096 byte alignment、Windows の非バッファ open/read。
