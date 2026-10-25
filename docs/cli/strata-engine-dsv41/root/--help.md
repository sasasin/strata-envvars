# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 エンジン） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

DeepSeek-V4.1 エンジンの usage を表示して終了します。CMake の `STRATA_BUILD_DSV41=ON` で生成される独立実行ファイルのオプションです。このオプションだけを使う場合、モデルを指定する必要はありません。

## 使い方

```sh
strata-dsv41 --help
```

短縮形も同じ動作です。

```sh
strata-dsv41 -h
```

usage には `--pack` と、推論・serve・画像 encode・pack 情報表示の各モードに関する引数形式が記載されます。表示文字列の実行名は `maya-ds4` です。

## 値と既定値

値を取りません。既定値や値の validation はありません。

## 実行時の動作

引数を左から解析し、このオプションに到達すると `usage()` を呼び、直ちに `0` を返します。usage の内容はモデルパス、GPU、コンテキスト、serve、画像、score などの利用形式を示す固定文字列です。通常処理で行うモデル生成と `m.load()` はこの分岐より後にあるため、ヘルプ表示では実行されません。

引数解析は逐次処理です。そのため、`--help` より前に未知オプションがあれば未知オプションのエラーで終了し、`--version` が先にあれば version 表示で終了します。`--verbose` が先にある場合は build 情報を `stderr` に出してから usage を表示します。また、値を要求するオプションの直後に `--help` を置くと、その文字列は値として消費される場合があります。単独の `strata-dsv41 --help` が確実な呼び出し方です。

## 適用条件と副作用

この実行ファイルは `STRATA_BUILD_DSV41=ON` の場合に CMake target `strata-dsv41` として定義されます。help 分岐は `main()` の引数解析中にあり、モデルのロード、推論、serve 開始には進みません。`main()` の冒頭ではタイマー初期化関数が呼ばれますが、それ以外の help 分岐固有のファイル・ネットワーク・GPU 処理は確認できません。

## 出力とエラー

usage は `stderr` に書き出され、通常の help 呼び出しは終了コード `0` です。未知の引数は `unknown option ...` を `stderr` に出し、続けて usage を表示して終了コード `2` になります。これは help 自体の拒否ではなく、help 分岐に到達する前に起きる引数解析エラーです。

## 根拠

- `src/dsv41/ds4_main.cpp:85-94` — usage の文面と `stderr` 出力。
- `src/dsv41/ds4_main.cpp:1187-1208` — `main()` と逐次引数解析、値不足時のエラー処理。
- `src/dsv41/ds4_main.cpp:1248-1254` — `--verbose` の表示副作用と、`--version` の先行終了。
- `src/dsv41/ds4_main.cpp:1266-1273` — `--help` / `-h` の認識、usage 表示、終了コード、未知オプションの経路。
- `src/dsv41/ds4_main.cpp:1289-1295` — help 分岐の後に行うモデル生成・ロード。
- `CMakeLists.txt:797-812` — DeepSeek-V4.1 の独立 executable と、build option が既定 OFF であること。
- `docs/cli/README.md:1353-1370` — `strata-engine-dsv41/root/--help.md` の索引項目。索引には `-h` alias の記載がありませんが、parser は `-h` も受け付けます。索引は依頼範囲外のため変更していません。

調査時点の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。ビルド済みバイナリの help は実行していません。Release での配布有無も、この調査では確認していません。
