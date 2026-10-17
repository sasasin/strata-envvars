# `GR_INJ_F32`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

これは通常の Strata 実行時設定ではなく、Metal の `gr_parity` テスト専用の切り替えです。`GR_Q8` と併せて設定すると、hyper-connection の down projection に使う inject 行列を Q8_0 ではなく F32 のデータとして用意し、F32 入力向けのテストカーネルを選びます。Strata の通常のエンジン、サーバー、セットアップ処理がこの環境変数を読む実装は、調査対象 HEAD の追跡対象ソースに見つかりませんでした。

## 値と判定

| `GR_Q8` | `GR_INJ_F32` | テスト内の扱い |
|---|---|---|
| 未設定 | 任意 | `GR_INJ_F32` は効果なし。BF16 経路を選ぶ |
| 設定済み | 未設定 | Q8_0 経路を選び、3行列を Q8_0 に量子化する |
| 設定済み | 設定済み（空文字を含む） | down projection 用 inject 行列を F32 のまま格納し、F32 入力用 Q8 down カーネルを選ぶ |

両変数とも文字列値の変換・比較は行いません。`std::getenv(...) != nullptr` による設定有無の判定なので、`GR_INJ_F32=0` や空文字も「設定済み」です。判定結果は `gr_parity` の `main()` 内で起動時に一度決まり、テストプロセス実行中に環境を変更して再評価するコードはありません。

## 有効になる条件

`GR_Q8` が設定されていることが必要です。`GR_INJ_F32` だけを設定しても `injf` は false です。これは `metal/tests/gr_parity.cpp` のテストプログラムに限った動作であり、Metal エンジンの通常実行経路を有効化するものではありません。

## 実行時の詳細

テストは `GR_Q8` が設定されると行列形式を Q8_0 とし、生成した BF16 値をいったん F32 に展開します。`GR_INJ_F32` も設定されている場合、3行列のうち inject 行列（2番目）だけはその F32 データをそのまま格納し、down projection の pipeline 名に `gr_down_q8f_` を使います。`GR_DOWN` が設定されていればその文字列を suffix にし、未設定なら `8_8` を使います。他の2行列は引き続き Q8_0 です。

parity モードでは CPU 参照計算も inject 行列を `ref::F32` として読みます。したがって、この変数はテストの入力形式と比較対象を揃えるためのものです。`--bench` モードでも同じ行列形式と pipeline 選択に使われますが、CPU parity 計算は実行されません。テストは通常の `parity ... PASS/FAIL` または `bench ...` の行を出力し、parity モードの終了コードは不一致があれば 1、なければ 0 です。この変数専用のログはありません。

## 根拠

- `metal/tests/gr_parity.cpp:28-43`: テストの引数処理と、`GR_Q8` / `GR_INJ_F32` の設定有無判定。
- `metal/tests/gr_parity.cpp:55-64`: Q8 行列生成時、inject 行列だけ F32 のまま格納する条件。
- `metal/tests/gr_parity.cpp:82-85`: `gr_down_q8f_` / `gr_down_q8_` / `gr_down_` の pipeline 選択。
- `metal/tests/gr_parity.cpp:120-129`: parity 比較と CPU 参照側での F32 decode。
- `metal/tests/gr_parity.cpp:184-207`: parity/bench の出力とテスト終了コード。
- HEAD 全体の完全一致検索では、環境変数名の直接参照は `metal/tests/gr_parity.cpp` の上記2箇所のみでした。
