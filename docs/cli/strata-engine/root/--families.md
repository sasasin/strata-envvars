# `--families`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン、root） |
| オプション | `--families` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

このビルドのエンジンが実行対象として扱う GGUF architecture 名を列挙します。setup は導入するモデルをエンジンが実行できるか調べるためにこの出力を利用します（`src/program/generate.cpp:2337-2345`、`setup.py:7418-7426`）。

## 使い方

```sh
strata --families
```

`--families` 自体は位置引数を必要としません。ソースは実行ファイル直後から最大2個の argv 要素を走査するため、`strata generate --families` のように2番目の argv 要素に置いても早期判定されます（`src/program/generate.cpp:2331-2345`）。

## 値と既定値

値を取らず、既定値はありません。引数の値検証や重複指定の処理はありません。実装は `argv[1]` と `argv[2]` の範囲だけを調べるため、3番目以降に置かれた `--families` はこの早期判定の対象外です（`src/program/generate.cpp:2332-2345`）。

## 実行時の動作

`main()` の冒頭でこのフラグを見つけると、ビルド時の `STRATA_HAVE_QWEN35` 定義に応じて次を stdout に出し、終了コード `0` で直ちに戻ります。

- 定義あり: `qwen4exp qwen35moe`
- 定義なし: `qwen4exp`

通常の引数 parser、モデル読み込み、推論処理には進みません。CMake は該当する GPU エンジン構成で Qwen3.6 専用エンジンをリンクする際に `STRATA_HAVE_QWEN35` を定義し、gfx906 ではこの経路を有効にしません（`CMakeLists.txt:771-795`）。したがって出力は実行時の GPU 検出ではなく、実行ファイルを作ったときの build 構成に基づきます。

setup 側はこのコマンドを `capture_output=True` で実行して空白区切りで集合化します。実行失敗・timeout の場合や、出力に `qwen4exp` がない場合は `{"qwen4exp"}` にフォールバックします（`setup.py:7418-7426`）。

## 適用条件と副作用

`--families` の判定は GPU 初期化より前にあります。通常の GPU 処理やモデルファイルへのアクセスを行わず、ファイル・ネットワークへの副作用もありません（`src/program/generate.cpp:2331-2345`）。Windows の HIP build ではこの判定より前に実行ファイル隣接の `rocm/bin` を DLL 検索先に追加する処理があります（`src/program/generate.cpp:2314-2329`）。

このフラグと同時に別の引数があっても、先頭2引数内で認識された時点で出力して終了するため、後続引数は処理されません。また、出力はモデル対応可否の照会結果であり、実際のモデル実行成功を保証するものではありません。

## 出力とエラー

成功時は stdout に architecture 名を1行出力し、終了コード `0` で終了します（`src/program/generate.cpp:2338-2345`）。この分岐内に値不正などのエラー経路はありません。コマンド単独の OS loader 起動失敗など、プロセス起動前のエラーはこのソース分岐の対象外です。setup からの実行については、失敗時に前述の `qwen4exp` フォールバックを使います（`setup.py:7420-7426`）。

## 根拠

- parser より前の早期判定、走査範囲、build 条件別出力、終了: `src/program/generate.cpp:2309-2345`
- `STRATA_HAVE_QWEN35` の定義条件: `CMakeLists.txt:771-795`
- setup における呼び出しと失敗時フォールバック: `setup.py:7418-7426`
- `qwen4exp` / `qwen35moe` architecture 名の対応: `include/strata/artifact/model_family.hpp:15-24`
