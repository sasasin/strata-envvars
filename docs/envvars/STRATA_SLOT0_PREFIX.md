# `STRATA_SLOT0_PREFIX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

サーバーの batch slot 選択で、Inkling-2-Mini の DSpark drafter が動作し slot 0 が空いているとき、他 slot にある最良の保持 prefix がこの値より短ければ slot 0 を優先する閾値です。保持 prefix が十分長い会話では、その会話の slot を選んで cache を保ちます。slot 0 自体が最良なら閾値に関係なく slot 0 が選ばれます。閾値は `StrataEngine.pick_slot()` の選択だけを変え、モデル引数や生成 token の内容を直接変更する処理ではありません（`terminal/serve/server.py:2494-2496`, `2560-2567`, `2589-2597`）。

## 値と判定

クラス属性の初期化時に `int(os.environ.get("STRATA_SLOT0_PREFIX", "512") or 512)` として読みます（`terminal/serve/server.py:2494-2496`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| サーバーモジュールの読み込み | 既定値 `512` | `int()` が受理する整数表記。例: `512`, `0`, `-1`, `+20`, ` 20 `, `1_024` | 空文字は無効値ではなく `512` に置換。`true`, `false`, `0anything`, `0x10`, 空白だけの文字列など `int()` が変換できない値は `ValueError` |

`os.environ.get` の未設定時の既定文字列は `"512"` です。設定値が空文字 `""` の場合も `or 512` により数値 `512` になります。一方、文字列 `"0"` は空ではないため `int()` に渡されて `0` になります。変換は文字列全体に対する Python の `int()` で、浮動小数点表記や後続文字は受け付けません。正負の整数を許し、非負への clamp や範囲検査はありません。変換失敗をこの式で捕捉する処理もないため、サーバーモジュール読み込み時に例外が伝播します（`terminal/serve/server.py:2496`）。

## 有効になる条件

- サーバーが slot を割り当てる `pick_slot()` 経路に入る必要があります。空き slot がなければ同関数は先に `None` を返し、閾値を使いません（`terminal/serve/server.py:2564-2577`）。
- `StrataEngine` が Inkling 実行ファイルとして識別され、エンジン情報の `drafting` が `"dspark"` である必要があります。その他のエンジン、または DSpark が無効と報告された場合、`drafter_in_slot_zero()` が偽となり、この閾値による優先分岐は通りません（`terminal/serve/server.py:769-771`, `2560-2562`）。
- slot 0 が空いている必要があります。slot 0 が使用中なら他の空き slot に対する prefix 選択に戻ります（`terminal/serve/server.py:2575-2595`）。
- slot 0 が最良の保持 prefix を持つときは、値にかかわらず slot 0 が返ります。別 slot が最良なら、その prefix 長が閾値未満の場合に限って空き slot 0 を優先します。長さが閾値と等しい場合は「未満」ではないため優先されません（`terminal/serve/server.py:2589-2597`）。従って `0` や負値では、別 slot の prefix 長（0以上）が閾値未満にならず、閾値による slot 0 優先は実質的に起きません。
- `pick_slot()` は `slot_gs > 1` の場合、slot 0 の DSpark 分岐より前にグループ内の空き slot 選択を返します。この値は batch slot 数、`--batch-groups` / エンジンの `batch_groups` 情報、エンジンの `INFO slot_read` から算出されます。よって pipelined group 選択が有効なこの経路では閾値は使われません。`INFO slot_read` が立ち `slot_gs` が 0 になる場合など、同条件を満たさない経路では後続の判定に進みます（`terminal/serve/server.py:973-988`, `2578-2589`）。
- OS や GPU backend を直接調べる条件は、この閾値の読み取り・分岐にはありません。実際の DSpark 状態は `self.info["drafting"]` で判定されるため、要求しただけでエンジンが `dspark` と報告しない場合は対象外です（`terminal/serve/server.py:953-959`, `2560-2562`）。
- CLI や別環境変数から閾値を上書きする処理は見つかりません。`--batch-groups` は上記のとおり slot 選択経路に影響しますが、閾値そのものを設定しません（`terminal/serve/server.py:2496`, `973-988`）。

## 実行時の詳細

この式は `StrataEngine` クラス本体の属性定義として評価されるため、環境値は `terminal/serve/server.py` のモジュール読み込み時に一度読み取られ、`SLOT0_PREFIX_MAX` に保持されます。リクエストごとの再読み込みや、起動後にプロセス環境を変えた値の反映はありません（`terminal/serve/server.py:720`, `2494-2496`）。

slot 選択では空き slot のうち prompt の先頭と一致する保持 prefix が最長の slot を `best` とします。Inkling は保持 token との prefix 一致、または prompt-end checkpoint により一致長を求めます。DSpark が slot 0 で使われ、slot 0 が空いている場合、`best == 0` または `best` の保持 prefix 長が閾値未満なら 0 を返します。それ以外は通常の保持 prefix 選択と、prefix が十分でない場合の空き・最古 slot 選択を続けます（`terminal/serve/server.py:2516-2534`, `2589-2608`）。

## ログと測定値

この環境変数の値や閾値判定を出力する専用ログ、警告、測定値はありません。無効な整数表記では `int()` の `ValueError` がモジュール読み込み処理へ伝播しますが、この箇所独自のログや fallback はありません（`terminal/serve/server.py:2496`）。

## 根拠

- `terminal/serve/server.py:2494-2496` — 既定値、環境値の変換とクラス属性への保存。
- `terminal/serve/server.py:769-771`, `953-959`, `2560-2562` — Inkling 実行ファイルの識別とエンジンが報告した DSpark 状態。
- `terminal/serve/server.py:2516-2556` — prompt と保持 slot の prefix 長の算定。
- `terminal/serve/server.py:2564-2608` — 空き slot、group 分岐、閾値比較と最終 slot 選択。
- `terminal/serve/server.py:973-988` — `--batch-groups` / エンジン情報と `slot_gs` の算出。
