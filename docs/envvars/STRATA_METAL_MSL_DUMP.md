# `STRATA_METAL_MSL_DUMP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Metal runtime が Metal Shading Language (MSL) のライブラリをコンパイルする直前に、コンパイラへ渡す組み立て済みソース文字列をファイルへ出力する調査用フックである。通常のコンパイル経路に加えてファイル出力を試みるが、出力の成否をコンパイル可否の条件にはせず、MSL 文字列やコンパイル設定もこの変数自体では変更しない。実装は `mtl::Context::compile_try` にあり、engine の通常ライブラリ、prompt、MTP、DFlash2 など `Context::compile` を通る Metal kernel compilation に適用される（`metal/src/mtl_rt.mm:76-114`、`metal/src/engine/window.cpp:756-764,2375-2377,2925-2930`、`metal/src/engine/prompt_chain.inc:53-60`、`metal/src/engine/dflash2.inc:30-33`）。

同じ runtime を使う standalone の Metal parity / bench プログラムでも、`Context::compile` を呼ぶ箇所では読み取り経路に入る。これは engine 専用の CLI 引数ではなく、CLI や他の環境変数との優先順位は実装されていない（例: `metal/tests/gr_parity.cpp:38`、`metal/tests/mm_bench.cpp:23`）。

## 値と判定

`std::getenv("STRATA_METAL_MSL_DUMP")` の null 判定だけを行い、数値変換・文字列比較・空白除去・値域検査はしない。未設定なら出力分岐に入らない。設定されていれば空文字を含む任意の文字列で分岐に入る。値をディレクトリ文字列 `dump` として使い、`dump + "/NNN.msl"` と `dump + "/index.txt"` を開く。ディレクトリの作成・正規化・存在確認はしない（`metal/src/mtl_rt.mm:100-114`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal runtime の `Context::compile_try` が実行される場合 | ダンプを試みない | `STRATA_METAL_MSL_DUMP=/tmp/msl`、`1`、空文字（空文字の場合は `/000.msl` などの絶対パスを試す） | 設定値の内容による無効値はない。どの設定済み文字列でも分岐するが、出力先を開けなければファイルは作られない |

境界値や大文字小文字の規則は該当しない。これは値の内容でなく、環境変数が未設定かどうかで判定する。空文字は「無効」ではなく「設定あり」である。`0`、`false`、前後空白付き文字列も特別扱いされず、そのまま出力先の先頭として使われる。

## 有効になる条件

- macOS 向け Metal runtime がビルドに含まれ、`mtl::Context::compile_try` が呼ばれること。`metal/CMakeLists.txt` は非 Apple 環境の構成を拒否し、`mtl_rt` に `metal/src/mtl_rt.mm` を含める（`metal/CMakeLists.txt:17-18,33-40`）。
- engine では MSL library のコンパイル経路に到達すること。通常の window 初期化は core/GDN/QSA/sample/PLE をコンパイルし、prompt や draft など一部の library はそれぞれの経路で追加コンパイルする（`metal/src/engine/window.cpp:756-764,2375-2377,2925-2930`、`metal/src/engine/prompt_chain.inc:49-60`、`metal/src/engine/dflash2.inc:24-33`）。値が設定されていても、プロセスがそのコンパイル経路を通らなければ読み取りも出力も起きない。
- 出力ファイルを得るには、値の文字列に `/NNN.msl` または `/index.txt` を連結したパスを `fopen` で開けること。出力先ディレクトリがない、または開けない場合でも、Strata はここで警告せず、通常の Metal コンパイルを続ける（`metal/src/mtl_rt.mm:100-114`）。

GPU 世代、モデル量子化、サーバーモード、CLI オプション、別の環境変数によるこのフックの有効・無効判定はない。コンパイル対象のライブラリや prelude は呼び出し元が選ぶが、この変数はその選択を上書きしない。

## 実行時の詳細

変数は `compile_try` の各呼び出し時に読み直され、環境値の static cache はない。出力番号 `ndump` は当該関数内の `static int` で、最初の設定済み呼び出しが `000`、以降の設定済み呼び出しごとに増える。環境値が設定されていると、`src`（prelude、`<metal_stdlib>`、条件に応じた ggml-common、各 kernel file の内容を連結した文字列）の構築後、Metal compiler API を呼ぶ前に出力を試す（`metal/src/mtl_rt.mm:89-114`）。

各呼び出しは `<値>/NNN.msl` を `wb` で開き、開けた場合に `src` の全バイトを書いて閉じる。続いて `<値>/index.txt` を `ab` で開き、開けた場合に `NNN.msl:` と、そのライブラリの `files` を空白区切りにした行を追記する。両方の `fopen` が失敗してもエラー処理はなく、`fwrite` の戻り値も確認しない。空文字では `/NNN.msl` と `/index.txt` を試すため、通常想定される指定ディレクトリへの出力にはならない（`metal/src/mtl_rt.mm:100-114`）。

その後のコンパイルは通常どおり行われる。`compile_try` は Metal compile failure 時に理由を `why` へ返して `-1` を返す。`Context::compile` 経由では `mtl: compile failed (%s, macOS %s; %s):\n%s\n` を stderr に出して exit code 3 で終了する。従って、ダンプファイルが作られていてもコンパイル成功を意味しない。ダンプ出力エラー自体による Strata の終了や警告はない（`metal/src/mtl_rt.mm:76-85,125-130`）。

## ログと測定値

この変数の読取・ダンプについて Strata はログを出さない。出力先を開けない場合や書込が完了しない場合にも専用の警告はない（`metal/src/mtl_rt.mm:100-114`）。ダンプ処理の測定値は `docs/DETAILS.md` に見当たらず、本書では記載しない。

## 根拠

- `metal/src/mtl_rt.mm:76-85,89-114,125-132` — compile 経路、環境値判定、ファイル名・index の生成、コンパイル前後のエラー処理。
- `metal/src/mtl_rt.h:94-100` — `compile` と `compile_try` の API と失敗時の契約。
- `metal/src/engine/window.cpp:756-764,2375-2377,2925-2930`、`metal/src/engine/prompt_chain.inc:49-60`、`metal/src/engine/dflash2.inc:24-33` — engine の各 MSL compile 呼び出し。
- `metal/CMakeLists.txt:17-18,33-40,127-139` — macOS 限定および runtime / engine 実行ファイルとのリンク。
- `metal/tools/msl_text_check.py:2-16` — 出力済みダンプを比較する同梱ツールの説明。Python ツール自身は対象名を環境から読まず、環境変数の挙動根拠にはしていない。
