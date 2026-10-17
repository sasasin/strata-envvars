# `PC_QSA`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`PC_QSA` は通常の Strata 実行ファイルの設定ではありません。確認できた読み取り箇所は Metal の診断・ベンチマーク用プログラム `metal/tests/prompt_chain.cpp` だけです。このプログラムで QSA attention の実装経路を選びます。Metal エンジン本体の `strata` では参照されません。

## 値と判定

値は `std::getenv()` で文字列として一度読み、未設定の場合だけ `coop_k4()` の結果に応じた既定値を使います。設定された値は文字列全体で比較され、数値変換や大文字小文字の正規化はありません。

| `PC_QSA` | `qsa_mode` | attention の経路 |
|---|---|---|
| 未設定、かつ `k4=true` | `flash` | `qsa_flash` |
| 未設定、かつ `k4=false` | `v1` | `qsa_attn` と `qsa_merge` |
| `flash` | `flash` | `qsa_flash` |
| `mm` | `mm` | `qsa_attn_mm` と `qsa_merge` |
| 空文字または上記以外の文字列 | 設定値のまま | `qsa_attn` と `qsa_merge`（`v1` と同じ分岐） |

`k4` は `COOP_K4` の設定、または Metal の協調メモリ配置 probe の結果です。したがって、`PC_QSA` を明示設定すると既定値選択における `k4` の結果を上書きします。設定値が `flash` でも `mm` でもない場合、エラーにはならず `else` 側の `qsa_attn` 経路になります。

## 有効になる条件

- Metal テスト群の `prompt_chain` 実行時に限ります。`metal/CMakeLists.txt` は `metal/tests/*.cpp` をテスト用実行ファイルとして列挙し、エンジン本体 `strata` は別ターゲットとして定義しています。
- `PC_QSA` に対応する CLI オプションはありません。テストプログラムの起動時に環境変数から読みます。
- attention のスコア計算には別変数 `PC_QSA_SCORE` が使われます。こちらは設定有無で `qsa_score_mm` と `qsa_score` を切り替えます。`PC_QSA` の値判定とは独立しています。

## 実行時の詳細

`prompt_chain` は `main()` の初期化中に `PC_QSA` を読み、`qsa_mode` を保持します。prompt の QSA layer を処理するとき、値が完全一致で `flash` なら `qsa_q_f16` と `qsa_flash` を実行して出力 GEMM に進みます。`mm` なら `qsa_q_f16`、`qsa_attn_mm`、共通の `qsa_merge` を実行します。それ以外は `qsa_attn` と `qsa_merge` を実行します。プロセス起動後に環境を変更しても、この選択は再評価されません。

## 根拠

- `metal/tests/prompt_chain.cpp:1-18,57-58` はプログラムを実重みの prompt 処理・GPU 時間計測用として説明し、単独の `prompt_chain` コマンドとして Usage を示します。
- `metal/tests/prompt_chain.cpp:105-106,127-132` は `k4` の probe と `PC_QSA` の読み取り、未設定時の既定値選択を示します。
- `metal/tests/prompt_chain.cpp:371-395` は `flash` / `mm` / その他の attention dispatch を示します。
- `metal/tests/prompt_chain.cpp:357-365` は別環境変数 `PC_QSA_SCORE` によるスコア計算経路の選択を示します。
- `metal/tests/coop_probe.h:10-35` は `COOP_K4` が設定されていれば `atoi(e) != 0` で上書きし、未設定なら GPU の layout probe を行うことを示します。
- `metal/CMakeLists.txt:41-47,122-123` は `tests/*.cpp` から各テスト実行ファイルを作り、engine の `strata` ターゲットを別に定義します。

調査対象の候補名全体検索では、上記テストファイル以外に `PC_QSA` の参照は見つかりませんでした。したがって、この変数を製品版 Strata の環境設定として説明する根拠はありません。性能差や出力の同一性についても、このソース調査からは判断していません。
