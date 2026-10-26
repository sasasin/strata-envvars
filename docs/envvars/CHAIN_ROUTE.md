# `CHAIN_ROUTE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`CHAIN_ROUTE` は、Metal 用の単体計測プログラム `token_chain` において、MoE router の GEMV と expert route の処理を1つの `router_route` dispatch にまとめるか、別々の dispatch にするかを選ぶ。Strata の通常の推論エンジンが読む環境変数ではない。直接参照は `metal/tests/token_chain.cpp` のみ。

## 値と判定

| 環境変数の状態 | `routef` | `token_chain` の処理 |
| --- | --- | --- |
| 未設定 | `true` | `router_route_30` の単一 dispatch を構成する（既定） |
| 値が文字列 `0` と完全一致 | `false` | router GEMV と route を別々の dispatch にする |
| 空文字、`00`、`1`、その他の文字列 | `true` | `router_route_30` の単一 dispatch を構成する |

値は `std::string(...) == "0"` で比較され、大文字小文字の問題はない。数値変換は行わず、空白を含む値なども文字列全体が `0` と一致しない限り有効化側（`routef == true`）になる。CLI 引数による上書きはない。

## 有効になる条件

`CHAIN_ROUTE` を読むのは `metal/tests/token_chain.cpp` の `token_chain` だけで、Metal 用の単体計測・カーネルチェーン構築経路に限られる。`metal/CMakeLists.txt` は macOS 以外では Metal プロジェクトを構成せず、`tests/*.cpp` から `runtime_hello.cpp` を除いた各ファイルを実行ファイルとして追加する。

この変数を Strata の通常の CUDA/HIP/SYCL エンジンやサーバーの設定として扱う根拠は見つからなかった。`docs/DETAILS.md` にもこの名前の記載は見つからなかった。

## 実行時の詳細

`token_chain` は引数を処理した後、dispatch を組み立てる段階で `CHAIN_ROUTE` を一度読み、`routef` に保持する。未設定または値が `0` 以外なら、MoE 部分で router GEMV を別 dispatch として先に積まず、共有 expert GEMV と並行する `router_route_30` dispatch を積む。値がちょうど `0` の場合は、router GEMV dispatch を先に積み、expert route 用の `proute` dispatch を別途積む。各層の MoE 構築で同じ `routef` を使うため、プロセス起動後の環境変更は反映されない。

この分岐が選ぶのは `token_chain` 内の GPU dispatch 構成である。ソースコメントは融合 dispatch の動作を「bitwise」と記しているが、この調査ではビルドや GPU 実行、数値比較を行っておらず、同一性を独立に検証したものではない。該当する分岐自体は標準出力・標準エラーへのログを出さない。

## 根拠

- `metal/tests/token_chain.cpp:1-8` — `token_chain` が実 GGUF 重みを使う Metal の単体 decode 計測プログラムであり、数値検証ではない旨と起動形式。
- `metal/tests/token_chain.cpp:71-83` — CLI 引数の処理。`CHAIN_ROUTE` に相当する CLI オプションはない。
- `metal/tests/token_chain.cpp:180-188` — `CHAIN_ROUTE` の読み取りと、未設定または文字列 `0` 以外で `routef` が true になる判定。
- `metal/tests/token_chain.cpp:495-500, 547-565` — false 時の router GEMV と route dispatch の分離、および true 時の `router_route_30` dispatch。
- `metal/CMakeLists.txt:1-2, 16-18, 41-47` — Metal プロジェクトの対象プラットフォームと、`tests/*.cpp` から単体実行ファイルを追加する設定。
