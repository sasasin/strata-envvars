# `GDN_IB8`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`GDN_IB8` は Metal の `gdn_parity` 診断プログラムで、GDN step のどちらのカーネル特殊化を検査するか選びます。通常の Strata Metal エンジンが読む環境変数ではありません。候補一覧にはありますが、ソース全体での完全一致参照は `metal/tests/gdn_parity.cpp` 内だけで、実行ファイルの推論経路への設定ではなくテスト専用フックです。

## 値と判定

| 環境変数の状態 | 選択されるカーネル | threadgroup のサイズ |
|---|---|---:|
| 未設定 | `gdn_step` | 512 threads |
| 設定済み（空文字、`0` を含む任意の文字列） | `gdn_step8` | 1024 threads |

判定は `std::getenv("GDN_IB8")` の null 判定だけで、値の内容を parse しません。したがって `GDN_IB8=0` も有効化扱いです。値は `static` にキャッシュされず、該当箇所ごとに読み取られます。

## 有効になる条件

`metal/tests/gdn_parity.cpp` をビルドして実行する場合だけ関係します。診断プログラムは実行時に Metal の `gdn.metal` をコンパイルし、特殊化ごとにパイプラインを作ります。選択した特殊化について `GDN_NTOK=1..8` の最大 thread 数を調べ、必要数（512 または 1024）を下回るものがあれば `FAIL` を出して終了コード 1 で終了します。`gdn_step8` は 1024 threads を必要とする実装として定義されています。

通常の Metal エンジンは `window.cpp` から `gdn_step` を選択しており、`GDN_IB8` を読みません。したがってこの変数を設定しても通常推論のカーネル選択や結果は変わりません。

## 実行時の詳細

`gdn_parity` は値の有無に応じてパイプライン名と `disp` の threadgroup サイズを選びます。同じ選択が `--bench` の計測対象にも使われます。引数なしの parity 実行では 1〜4 token の窓を調べ、verify 時の state 不変、commit 時の出力、CPU 参照との誤差などを表示します。これらはテストプログラムの診断出力であり、Strata の通常実行時ログではありません。

## 根拠

- `metal/tests/gdn_parity.cpp:29-33` はテストプログラムの起動処理と Metal kernel のコンパイルを示す。
- `metal/tests/gdn_parity.cpp:54-78` は `GDN_IB8` の有無による 512/1024 thread 設定、カーネル名、特殊化ごとの実行可能性チェックを示す。
- `metal/tests/gdn_parity.cpp:81-100,179-190` は benchmark と parity 経路が同じ環境変数で `gdn_step` / `gdn_step8` を選ぶことを示す。
- `metal/kernels/gdn.metal:30-36,169-170` は step kernel の必要 thread 数に関する説明と、`gdn_step` / `gdn_step8` の特殊化定義を示す。
- `metal/src/engine/window.cpp:797,1488` は通常エンジン側が `gdn_step` を選んでいる箇所。Strata ソース内の `GDN_IB8` 完全一致検索ではテストファイル以外に読み取りが見つからない。
