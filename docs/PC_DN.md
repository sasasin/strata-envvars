# `PC_DN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Strata の通常実行ファイルの設定ではありません。リポジトリ全体を検索したところ、環境変数 `PC_DN` を読むコードは `metal/tests/prompt_chain.cpp` のみでした。このファイルは Metal の `prompt_chain` テスト／計測用プログラムです。Metal engine に組み込まれる `strata` 実行ファイルから `PC_DN` は読み取られません。

テストプログラム内では、MoE の routed expert down projection に使う行列カーネルの選択と、`v3` カーネルの tile 設定に使われます。

## 値と判定

テストプログラムは `main()` の初期化時に一度 `std::getenv("PC_DN")` を呼び、返されたポインターが null かどうかで未設定を判定します。値の全体を検証する処理や、空文字・無効値へのエラー処理はありません。

| 状態 | テストプログラムの処理 |
|---|---|
| 未設定 | `COOP_K4` による `k4` 判定が真なら `v3:16,64,32,2`、偽なら `v2` を選ぶ |
| 設定あり（空文字を含む） | 指定文字列をそのままモード名として使う |
| 文字列が `v3:` で始まる | `sscanf` で後続から整数4個を `%d,%d,%d,%d` 形式で読む。戻り値は検査しない |
| 上記以外 | `v3:` 判定が偽となり、down projection に `mm_down2` 系カーネルを選ぶ |

`v3:` の文字列は先頭3文字だけを `rfind("v3:", 0)` で照合します。tile の読み取りは文字列全体の厳密な検証ではなく `sscanf` であり、4個すべてを読み取れたか、値が有効な範囲かはこの箇所では確認されません。設定値がある場合の `v3` 選択は `k4` の有無にかかわらず行われます。

## 有効になる条件

この環境変数の読み取りと効果は `metal/tests/prompt_chain.cpp` のテスト／計測実行に限られます。`metal/CMakeLists.txt` は `tests/*.cpp` を列挙して各ファイル名の実行ファイルを作るため、このソースは `prompt_chain` 実行ファイルの対象になります。一方、同 CMake ファイルでは Strata engine の実行ファイル `strata` を別ターゲットとして定義しています。

Metal engine の本番 prompt 経路は別実装です。`metal/src/engine/prompt_chain.inc` は `PC_DN` を読み取らず、`Window::pc_setup()` で `dn3` tile を固定値 `{16,64,32,2}` に設定しています。したがって `PC_DN` を設定しても、本番 engine の expert down カーネル選択や tile は変わりません。

## 実行時の詳細

`prompt_chain` テストでは、未設定時に `COOP_K4` などをもとに既定モードを決めます。`PC_DN` が設定されると、その文字列を `dn_mode` に採用します。`dn_mode` が `v3:` で始まる場合は `dn3` を読み取り、`dn_v3` を真にして、expert down dispatch で `mm_down3_<型>_<tile>` を選びます。それ以外は `mm_down2_<型>...` を選びます。`meta` にも `dn_v3` に応じた分割数を設定します。

値は `main()` のこの初期化時にローカル変数へ取り込まれます。後からプロセス環境を書き換える挙動はこのコードにはありません。環境変数に応じた専用ログや警告はこの読み取り箇所にはありません。

## 根拠

- `metal/tests/prompt_chain.cpp:57-76` — テスト／計測プログラムの `main()` と CLI
- `metal/tests/prompt_chain.cpp:133-149` — `PC_DN` の読み取り、既定値、`v3:` 判定、tile 変換
- `metal/tests/prompt_chain.cpp:205-206,445-448` — down dispatch の分割数とカーネル選択
- `metal/CMakeLists.txt:41-47,122-123` — `tests/*.cpp` から個別実行ファイルを作成し、engine の `strata` ターゲットを別に定義
- `metal/src/engine/prompt_chain.inc:92-97` — 本番 prompt 経路の down tile 固定値
- `metal/src/engine/window.cpp:2625` — 本番 engine への `prompt_chain.inc` の取り込み
