# `strata-inkling-metal --version`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

Metal 版 Inkling エンジンのバージョン文字列を標準出力に表示して終了します。モデルの読み込みや推論を始めずに、実行ファイルが報告するバージョンを確認できます。

## 使い方

```sh
strata-inkling-metal --version
```

## 値と既定値

`--version` は値を取りません。別名、数値範囲、入力値の validation はありません。バージョン文字列は `INK_VERSION` マクロから取得し、Metal の `build_mac.sh` はこのマクロを別途定義していないため、ソース内の既定値は `0.1.66` です。別のビルド設定がマクロを定義する場合の値は、このソースだけでは確定できません。

## 実行時の動作

引数を左から走査し、`--version` に到達すると `strata-inkling <バージョン>` を標準出力へ出し、終了コード `0` で直ちに終了します。そのため、このオプションより後ろの引数は処理されません。前にある引数は先に parser で処理され、未知の引数や値不足があればバージョン表示より先に失敗します。

この分岐はモデルパスの必須確認、Metal デバイス情報の表示、モデル読込、runner 初期化より前にあります。単独で使う場合、これらの処理は行われません。

## 適用条件と副作用

対象は索引上の `strata-inkling-metal`（Metal）です。`--version` の分岐自体は標準出力への表示と正常終了だけを行います。引数にモデルなどを指定していても、オプションを先に処理できればモデル読込へ進まず終了します。

## 出力とエラー

標準出力の形式は `strata-inkling %s\n` で、`%s` に `INK_VERSION` が入ります。オプション単独での失敗経路はありません。先行引数に未知の引数があれば `unknown arg: <引数>` を標準エラーに出して `2` を返し、値を要求する先行オプションの値が不足していれば `missing value for <オプション>` を標準エラーに出して `exit(2)` します。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:26-28` — `INK_VERSION` が未定義の場合に使う既定値 `0.1.66`。
- `engine/src/inkling2/metal/ink_metal_main.cpp:417-438` — `main` の引数走査と `--version` の標準出力・即時 `return 0`。
- `engine/src/inkling2/metal/ink_metal_main.cpp:435-436` — 先行オプションの値不足時に標準エラーへ出力して終了コード `2`。
- `engine/src/inkling2/metal/ink_metal_main.cpp:464-467` — 先行する未知引数の標準エラー出力と `return 2`。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-492` — 引数走査完了後のモデル必須確認、Metal デバイス情報出力、ロードと runner 初期化。`--version` はこれらより前に終了する。
- `engine/src/inkling2/metal/build_mac.sh:10-12,40-43` — Metal 版のビルド引数に `INK_VERSION` の定義が含まれないこと。
- `docs/cli/README.md:1549-1569` — `strata-inkling-metal` の階層と `metal/--version.md` の索引リンク。
- `docs/cli/000_cli_tools.md:12` — `strata-inkling` の Metal parser と `metal/` scope。
