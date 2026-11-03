# `SFNX_TEST_PROMPT_CONFIRM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`sfnx --serve` の計測用プロンプト差し替え `SFNX_TEST_PROMPT` に対する明示確認です。`SFNX_TEST_PROMPT` が設定されているとき、この変数が文字列として厳密に `1` でなければ sfnx は起動前にエラーにします。確認値だけではプロンプトを変更しません。

対象コードは `src/split/tools/sfnx.cpp` の sFNX サーバーです。split engine は既定ではビルドされず、CMake 上 Linux CUDA または HIP ビルドに限られます（`src/split/CMakeLists.txt:1-5,20-30,64-77`）。

## 値と判定

| `SFNX_TEST_PROMPT` | `SFNX_TEST_PROMPT_CONFIRM` | 判定 |
|---|---|---|
| 未設定 | 任意（未設定を含む） | 確認関数は戻り、確認値は読みません。 |
| 設定あり | 文字列全体が `1` | 起動を続け、stderr に差し替えの案内を出します。 |
| 設定あり | 未設定、空文字、または `1` 以外 | 起動前エラー。 |

値は `std::getenv` で取得し、`std::string(ok) != "1"` で文字列全体を比較します。数値変換、前後空白の除去、先頭文字だけの比較、大文字小文字変換はありません。したがって `01`、`1 `、`true`、`0` は通らず、空文字も未設定とは異なりエラーです。`SFNX_TEST_PROMPT` は `getenv` が null かどうかで判定されるため、空文字でも「設定あり」として確認を要求します。

根拠: `src/split/tools/sfnx.cpp:1017-1024`。

## 有効になる条件

この変数が確認に使われるのは、split engine の `sfnx` 実行ファイルがあり、`--serve` で起動される場合です。sfnx は `--serve` を必須とし、通常の Strata CLI に同名の引数はありません（`src/split/tools/sfnx.cpp:1-5,72-104`）。ビルド定義は Linux CUDA/HIP に限る opt-in の split engine です（`src/split/CMakeLists.txt:1-5,20-30`）。

起動時に `SFNX_TEST_PROMPT` 自体が未設定なら、`SFNX_TEST_PROMPT_CONFIRM` の有無や値は効果を持ちません。別の CLI 引数や設定ファイルとの優先順位はありません。確認が成功した後、差し替え対象になるのは画像入力でない要求です（`src/split/tools/sfnx.cpp:299-301`）。

## 実行時の詳細

`main` は引数解析と route 用環境変数の確認後、モデルをロードする前に `check_test_prompt()` を一度呼びます（`src/split/tools/sfnx.cpp:1040-1057`）。この関数はまず `SFNX_TEST_PROMPT` を読み、未設定なら戻ります。設定されていれば `SFNX_TEST_PROMPT_CONFIRM` を読み、値が厳密に `1` でない場合は例外を投げます。環境変数を static に cache する処理はなく、この確認値の読み取りはこの起動時チェックだけです。

確認に失敗すると stderr に `sfnx: SFNX_TEST_PROMPT=... replaces every text request's tokens (measurements only): set SFNX_TEST_PROMPT_CONFIRM=1 beside it, or unset it` の形で表示し、終了コード 2 で終了します。確認に成功すると stderr に `sfnx: SFNX_TEST_PROMPT: every text request reads ... instead of its own tokens` を一度出します（`src/split/tools/sfnx.cpp:1020-1024,1045-1049`）。

このフラグ自体は要求トークンを差し替えません。確認後は `SFNX_TEST_PROMPT` のパスを各テキスト要求の解析時に読み、ファイルの token id で要求の id を置き換えます。画像付き要求は差し替えません。実際の置換は各要求で別途 stderr に記録され、ファイルを開けない・形式が不正・token id が範囲外などの場合は要求処理の `ERR ...` 経路になります（`src/split/tools/sfnx.cpp:299-323,990-995`）。

## 根拠

- `src/split/tools/sfnx.cpp:1017-1025` — companion 変数の有無、確認値の完全一致判定、起動時の案内。
- `src/split/tools/sfnx.cpp:1040-1057` — 引数解析後・モデルロード前の確認呼び出しと、失敗時の終了コード。
- `src/split/tools/sfnx.cpp:299-323,990-995` — 確認後のテキスト要求でのファイル読込・置換・エラー応答。
- `src/split/CMakeLists.txt:1-5,20-30,64-77` — split engine の対象 backend / OS と sfnx ソースのビルド対象。
