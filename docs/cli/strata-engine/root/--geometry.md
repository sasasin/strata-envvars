# `--geometry`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`strata generate` からも利用可能） |
| オプション | `--geometry` |
| 別名 | なし |
| 値 | 値を取らない |

## 役割

実行ファイルにコンパイルされたモデル形状（geometry）の名前を表示する問い合わせフラグです。エンジンのビルドがどの形状向けかを確認できます。モデルファイルから形状を読み取る機能や、実行時にモデル形状を変更する指定ではありません。

## 使い方

```sh
# エンジンがコンパイルされた geometry 名を表示
strata --geometry

# generate 経路から同じ問い合わせを行う
strata generate --geometry
```

## 値と既定値

値は不要です。引数 `--geometry` と完全一致した場合に、コンパイル時に選ばれたヘッダーの `strata::core::kGeometryName` を表示します。geometry 名を引数で渡す構文や、重複指定を検証する処理はありません。初期引数走査が調べるのは `argv[1]` と `argv[2]` までなので、それより後ろに置いた `--geometry` はこの問い合わせ分岐では認識されません（`engine/src/program/generate.cpp:3699-3715`）。

## 実行時の動作

起動時の初期引数走査で `--geometry` を見つけると、`kGeometryName` を標準出力に改行付きで書き、終了コード `0` で直ちに終了します。そのため、この問い合わせ経路では通常のモデル読込や GPU 初期化へ進みません（`engine/src/program/generate.cpp:3699-3715`）。SYCL 側の実装も同じく名前を出力して `0` を返します（`engine/sycl/src/program/generate.cpp:1841-1845`）。

表示名はビルド構成に依存します。`geometry.hpp` はビルドツリーに選択済みヘッダーがあればそれを読み、なければ `flash_next.hpp` を使います。既定ヘッダーの名前は `flash_next` です。別の geometry ヘッダーを指定する仕組みはビルド時の `STRATA_GEOMETRY` / `STRATA_GEOMETRY_FILE` であり、この CLI フラグではありません（`engine/include/strata/core/geometry.hpp:72-82`、`engine/include/strata/core/geometries/flash_next.hpp:6-10`）。

通常のモデル読込では別に、ネイティブモデルの GGUF メタデータからモデル側 geometry を読み、コンパイル済み形状との不一致を検査します。これは `--geometry` の問い合わせがモデルを検査するという意味ではありません（`engine/src/program/generate.cpp:5624-5640`）。

## 適用条件と副作用

CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` に同じ問い合わせ分岐があります。結果は実行ファイルにコンパイルされた名前であり、搭載 GPU の有無・実行可否を調べるものではありません。確認できた処理は標準出力のみで、ファイルやネットワークへの副作用はありません。

## 出力とエラー

成功時は geometry 名を1行だけ標準出力へ出し、終了コード `0` を返します。この分岐には値の validation やエラー出力はありません。ビルド済み実行ファイルを実行して出力値を実測することは、この調査では行っていません。

## 根拠

- `engine/src/program/generate.cpp:3699-3715` — 初期引数走査、`--geometry` の一致判定、名前の標準出力、即時終了。
- `engine/sycl/src/program/generate.cpp:1841-1845` — SYCL 側の同じ問い合わせ処理。
- `engine/include/strata/core/geometry.hpp:72-82` — 選択済み geometry ヘッダーと既定ヘッダーの読込規則。
- `engine/include/strata/core/geometries/flash_next.hpp:6-10` — 既定ビルド名 `flash_next`。
- `engine/src/program/generate.cpp:5624-5640` — 通常のネイティブモデル読込で行うモデル側 geometry の読込と、コンパイル済み形状との不一致検査。
