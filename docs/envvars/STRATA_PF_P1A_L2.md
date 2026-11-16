# `STRATA_PF_P1A_L2`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP ビルドの gfx1151 向け native fused prompt expert 経路で、P1A の F16 行列コアカーネルに渡せる gate/up と down の量子化形式ペアを広げるフラグです。既定では追加分を有効にせず、既定の Q4_K gate/up + Q5_1 down ペアはこの変数を設定しなくても対象です。値が有効でも、P1A 本体、FP16 down 行、モデル形式などの条件がそろわなければ通常の native expert カーネルが続きます（`src/prefill/moe_fused_iq.cu:3076-3082,3093-3096,3131-3143`、`src/prefill/moe_p1a.cu:508-510`）。

## 値と判定

HIP では `p1a_l2()` の初回評価時に `std::getenv` し、値が存在し、先頭が `'1'` かつ次の文字が終端（`'\0'`）である場合だけ有効です。数値変換や空白除去、大文字小文字変換はありません。空文字、`0`、`true`、`10`、`1anything`、` 1` は無効です。非 HIP ビルドはこの環境変数を読み取らず常に無効を返します（`src/prefill/moe_fused_iq.cu:3076-3082`）。

| ビルド・条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP | 追加ペアは無効。Q4_K + Q5_1 は引き続き候補 | 文字列が厳密に `1` | 空文字、`0`、`true`、`10`、`1anything`、空白を含む値 |
| HIP 以外 | 関数が `false` を返す | なし | すべて |

コード上のペア判定は `STRATA_PF_P1A_L2=1` のとき、Q4_K または Q5_K の gate/up と、Q5_1 または Q8_0 の down の組み合わせを許可します。したがって判定式上は Q4_K/Q5_1、Q4_K/Q8_0、Q5_K/Q5_1、Q5_K/Q8_0 が対象です。コメントは L2 が追加するペアを Q5_K/Q8_0 とだけ説明しており、判定式とは範囲が異なります。実際にどのペアが選ばれるかは読み込んだ native pack の形式にも依存します（`src/prefill/moe_p1a.cu:57,508-510`、説明コメント `src/prefill/moe_p1a.hpp:16`、`src/prefill/moe_fused_iq.cu:3056-3059`）。

## 有効になる条件

- `__HIPCC__` でコンパイルされた経路であること。CUDA など非 HIP ビルドでは無効です（`src/prefill/moe_fused_iq.cu:3076-3082`）。
- P1A 本体の `STRATA_PF_P1A` が厳密に `1` で、検出デバイスが gfx1151 であること。P1A 本体が無効なら、ペア判定より前に対象外です（`src/prefill/moe_fused_iq.cu:3065-3074,3093-3096`）。Windows の統合 gfx1151 では起動時の arch defaults が `STRATA_PF_P1A=1` を既定設定します。設定済みの値は上書きしません。`STRATA_PF_P1A_L2` 自体はこの既定値一覧にありません（`src/core/arch_defaults.cpp:187-213,218-223,358-363`）。
- 対象層が native expert layout で、`fused_nat` が選ばれること。これは MMQ 計画または fused-only 対象、全体ストリーム経路、peer 不使用、native layout、対応形式を要します。通常の fused native 判定は折り畳み入力・出力の層を除外します（`src/prefill/prefill.cpp:5426-5437`）。
- 同じ呼び出しで `STRATA_PF_DM16` による FP16 down 出力が許可されること。`STRATA_PF_DM16` は先頭文字が `1` なら有効ですが、CPU 分担がなく、peer 行がなく、共有バッファと出力ポインタが 16-byte 整列している必要もあります（`src/prefill/prefill.cpp:931-935,5540-5543`）。
- P1A に渡す FP16 入力があること。gate/up の入力を折り畳む層では `p1a_input` に null が渡されます。また down の回転が有効な呼び出しも P1A の条件から外れます（`src/prefill/prefill.cpp:5490-5493`、`src/prefill/moe_fused_iq.cu:3084-3090,3134-3136`）。
- `tiles <= 65535` かつ FP16 H 行を格納する容量があること。モデル内に対象ペアがない場合はバッファを追加せず、対象層があっても容量条件を満たさない呼び出しでは P1A を起動しません（`src/prefill/prefill.cpp:2237-2267`、`src/prefill/moe_fused_iq.cu:3133-3136`）。

## 実行時の詳細

`p1a_l2()` は関数内 `static const bool` に結果を保存します。通常は P1A が有効な状態で native pack のバッファを計画するとき、`p1a_pack()` → `p1a_takes_pair()` から初回評価されます。そこで読み取られた後にプロセス環境を変更しても反映されません。P1A 本体の `p1a_wanted()` も別の関数内 static として初回値を保持します（`src/prefill/moe_fused_iq.cu:3065-3082,3093-3096`、`src/prefill/prefill.cpp:2237-2243,2260-2267`）。

専用の engine CLI 引数はありません。Strata Terminal の汎用 `strata launch --set STRATA_PF_P1A_L2=1` は設定を受け付け、CLI の指定は保存済みの同名 extra を上書きします。その後、runner は env 形式の extra を起動設定の `env` に適用し、同名キーを置き換えます。`--set ...=off` / `unset` / `none` はキーを削除します。engine 内では最後に渡された環境値を上記の厳密な判定で読みます（`strata_cli/launch/cmd.py:121-122,285-286`、`strata_cli/launch/settings.py:247-252`、`strata_control/tune_knobs.py:259-284,522-529`、`strata_cli/launch/runner.py:507-510`）。

条件を満たす呼び出しでは `moe_p1a.cu` の F16 gate/up と down を起動し、H と down 行を FP16 として書きます。続いて `dm16_used` が立ち、CPU 行がない場合は `moe_combine16` がその down 行を読みます。launch 条件を満たさない場合は `experts_native` の残りの既存経路に進みます（`src/prefill/moe_fused_iq.cu:3133-3143`、`src/prefill/moe_p1a.cu:513-525`、`src/prefill/prefill.cpp:5540-5554,7091-7099`）。

## ログと測定値

この変数専用の警告・有効ログはありません。P1A が少なくとも 1 層で実際に使われると、最初の対象チャンクの最終層で stderr に `strata: prompt experts P1A (STRATA_PF_P1A=1): ...` が出て、使われた形式ペアと層数、既存カーネルに残った層数などを表示します。P1A を使った層が 0 の場合、この行は出ません。L2 の値自体はログに表示されません（`src/prefill/prefill.cpp:2195-2230,5567-5571`）。この L2 追加分について、調査対象ソースに条件付き測定値は見つかりませんでした。

## 根拠

- 読み取り、厳密な値判定、HIP 以外の扱い、ペア判定呼び出し: `src/prefill/moe_fused_iq.cu:3076-3096`
- 実際の対応型ペアとカーネル起動条件: `src/prefill/moe_p1a.cu:57,508-525`; `src/prefill/moe_fused_iq.cu:3131-3143`
- native fused prompt 条件、FP16 入出力、フォールバック後の combine: `src/prefill/prefill.cpp:5426-5443,5490-5493,5540-5554,7091-7099`
- 対象 pack の事前判定と H 容量: `src/prefill/prefill.cpp:2232-2267`
- 関連資料: `docs/SETTINGS.md:187` は AMD 向け on/off 設定として掲載。個別の効果説明はありません。`data/settings-register.json:26099-26127` は HIP、既定 off、P1A と gfx1151 で追加ペアを使う設定として登録しています。
