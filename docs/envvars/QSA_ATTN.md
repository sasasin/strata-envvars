# `QSA_ATTN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

この名前を読む箇所は `metal/tests/qsa_parity.cpp` と `metal/tests/token_chain.cpp` の2か所で、どちらも Metal QSA attention のテスト・計測プログラムです。読み取り値に応じてテスト側が選ぶ attention pipeline を変えます。Strata の通常の実行経路でこの変数を読む箇所は、調査対象 HEAD では見つかりませんでした。したがって通常の Strata 実行に対する設定としては確認できず、製品ランタイムの挙動を制御する変数とは扱えません。

## 値と判定

両プログラムとも、変数が未設定なら整数値 `1` を使います。設定されている場合は `std::atoi` で変換します。文字列全体の妥当性検査はありません。空文字や数値に変換できない先頭部分は `atoi` により `0` になり、数値の後ろに続く文字は変換結果に影響しません。

| `atoi` の結果 | `qsa_parity` が選ぶ attention | `token_chain` が選ぶ attention |
|---|---|---|
| unset（既定 `1`）、または `1` | `qsa_attn` | `qsa_attn` |
| `2` | `qsa_attn2` | `qsa_attn2` |
| `0`、`3`、負数、その他 `1`/`2` 以外 | `qsa_attn3` | `qsa_attn3` |

たとえば `QSA_ATTN=2tail` は `atoi` の結果が `2` なので variant 2 を選びます。`QSA_ATTN=`、`QSA_ATTN=x`、`QSA_ATTN=0` は結果が `0` となり variant 3 を選びます。両プログラムは起動時に `main` 内で値を読み、その実行の pipeline を組み立てます。値を後から変更して再評価するループはありません。

## 有効になる条件

対象は Metal の開発用プログラムだけです。`qsa_parity` はソース冒頭で QSA の各段を CPU reference と照合し、`--bench` では kernel 時間を測るプログラムと説明されています。`token_chain` は Metal kernel 群を実モデルの重みに対して1 decode step 実行する検査用プログラムです。これらのテスト実行ファイルを使わない通常の Strata ランタイムでは、本変数による切り替えは確認できません。

## 実行時の詳細

`qsa_parity` は選択した pipeline 名で `qsa_attn`、`qsa_attn2`、`qsa_attn3` のいずれかを作成します。variant 2 の場合だけ `qsa_merge2` を選び、それ以外は `qsa_merge` を選びます。ソースコメントは variant 2 に独自の chunking と merge があると説明していますが、同コメントにある「default 3」は実際の式と一致しません。未設定時の実際の既定値は `1` です。

`token_chain` も同じ整数判定で attention pipeline 名を選びます。variant 2 の場合は `qsa_merge2`、それ以外は `qsa_merge` を要求します。このプログラムは `Pn` helper に fallback 名 `qsa_attn` / `qsa_merge` も渡します。どちらのプログラムも、環境変数の値が通常の Strata 実行へ伝播する処理は確認できません。

## 根拠

- `metal/tests/qsa_parity.cpp:1-6,30-47`: テスト・計測プログラムであること、既定値 `1` と attention/merge pipeline の選択。
- `metal/tests/token_chain.cpp:1-6,243-249`: decode 検査プログラム内の同じ既定値・pipeline 選択。
- 調査対象リポジトリ全体で `QSA_ATTN` を検索した結果、実行可能ソース上の読み取りは上記2か所のみでした。`docs/DETAILS.md` に本変数の説明は見つかりませんでした。
