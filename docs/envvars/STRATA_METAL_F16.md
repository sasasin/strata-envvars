# `STRATA_METAL_F16`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

Metal engine の decode window で、一部の量子化重みの GEMV と Q2_0 routed expert 計算を fp16 経路にするかを選ぶ。fp16 経路では重みを half に decode し、window の activation に half plane を追加して計算する。適用中も出力 logits 自体は float バッファに書かれるが、fp32 経路と同じ数値になる保証はソースにない。設定値は `metal_f16()` で選び、Metal library のコンパイル・activation buffer の確保と、各 decode window の `f16_enc_` 判定に使われる（`engine/metal/src/engine/window.cpp:167-170, 793, 834-841, 1046-1057, 1563-1565`）。

この読み取りは Strata の Metal engine にだけある。候補名の他の出現はコメント、設定登録データ、資料、またはテストであり、別の本番読み取り箇所は見つからなかった。通常の Mac setup は `STRATA_METAL_F16` を config に書かず、engine の既定判定に任せる（`engine/metal/setup_mac.py:593-598`）。

## 値と判定

engine 内の `metal_f16()` は最初の呼び出しで `std::getenv` を一度評価し、関数内 `static` の `mode` に保存する。未設定または空文字なら自動判定モード（`-1`）、文字列全体が厳密に `"1"` なら強制 ON、それ以外の非空文字列はすべて明示的 OFF（`0`）となる。数値変換はせず、空白除去・大文字小文字変換・前方一致もしない。したがって `1` だけが明示的 ON、`0`・`true`・`01`・`1x`・` 1` は OFF である。unset と空文字はいずれも自動判定を使う（`engine/metal/src/engine/window.cpp:167-170`）。

| 条件 | unset / 空文字 | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| Metal engine | resident pack の basename に `-IQ3_S-` または `-Q2_0-` があれば自動 ON。それ以外、および streaming pack は OFF | 値が文字列全体で `1` | 空文字以外で `1` と異なるすべての文字列。例: `0`, `true`, `01`, `1x`, ` 1` |

自動判定はモデル path の basename だけを大文字化して部分文字列検索する。そのため pack 名に小文字で書かれていても一致するが、`-IQ3_S-` / `-Q2_0-` のハイフンを含む形が必要。自動判定では `streaming` が true ならファイル名を調べる前に OFF を返す（`engine/metal/src/engine/window.cpp:171-176`）。

## 有効になる条件

- engine が Metal backend の実装を使うこと。環境変数読み取り箇所は `engine/metal/src/engine/window.cpp` 内にある。
- 対象の window が `head` を持ち、streaming ではなく、batch-slot の `rows_` 経路でもないこと。これらを満たしたときだけ `f16_enc_` が true になる。prompt 側・streaming・batch-slot の window は fp16 decode window にしない（`engine/metal/src/engine/window.cpp:1563-1565`）。
- fp16 GEMV は `x16_kind()` が対応する量子化型（IQ4_XS、Q8_0、IQ3_XXS、IQ3_S、NVFP4、Q2_0、Q2_K、Q3_K、Q4_K、Q5_K、Q6_K）で、さらに tile が `gemv16_tile()` の列挙に一致する場合に限る。対象外型や未対応 tile は通常の `gemv_` を選ぶ（`engine/metal/src/engine/window.cpp:178-191, 1046-1057`）。
- routed expert の fp16 分岐はさらに限定され、resident window で、gate/up と down の両方の tensor が Q2_0、かつその layer に Hadamard の gate/up・down 処理がない場合だけ選択される。この場合 `moe_gu16_` と `moe_down16_` pipeline を使い、half activation と half の中間値を渡す（`engine/metal/src/engine/window.cpp:1353-1354, 1372-1391, 1403-1406`）。
- `STRATA_METAL_F16=1` は `metal_f16()` の選択を pack 名に関係なく true にするが、streaming または `head` なし / `rows_` の window では上記の実行条件が成立せず、fp16 decode window は使われない。unset / 空文字の自動 ON は resident IQ3_S / Q2_0 pack 名に限る（`engine/metal/src/engine/window.cpp:167-176, 739-740, 1563-1565`）。

## 実行時の詳細

`Window::init()` は model file を開き、`ExpertStream::wanted()` で streaming 状態を決めた後に `g_f16_auto` を basename と streaming 状態から更新する。その後 `metal_f16()` を使って decode 用 Metal library の prelude に `#define STRATA_METAL_F16 1` を含めるか決め、fp16 用 buffer も必要に応じて確保する（`engine/metal/src/engine/window.cpp:736-740, 791-798, 834-841`; `engine/metal/src/engine/msl_libs.h:25-29`）。

環境変数そのものは `metal_f16()` の最初の呼び出し時に読み、以後プロセス内で cache される。window の自動判定は model open 後の init ごとに設定される。通常の単一 model 起動では engine 初期化中の評価であり、プロセス実行中に環境を書き換えても `mode` は再読込されない。CLI 引数による上書きはこの値の読み取り経路にはなく、同名の他の Strata 本番読み取り箇所も見つからなかった。

各 window では `f16_enc_ = metal_f16() && head && !stream_ && !rows_` とし、dense GEMV の型・tile 条件を満たせば `gemv16_...` pipeline と half activation plane を使う。routed expert では前節の Q2_0 条件を満たす場合に fp16 分岐を選ぶ。それ以外の計算は fp32 経路を使う（`engine/metal/src/engine/window.cpp:1046-1057, 1353-1354, 1563-1565`）。

## ログと測定値

この変数の値や選択結果を出す専用ログ、警告、終了経路は読み取り実装とその利用箇所に見つからなかった。`window.cpp` のコメントには M5 Max 上の decode 速度・top-1 agreement・mean KL と 61-task suite の結果が記されているが、対象モデル、OS、測定回数などの条件一式はそこにないため、一般化できる測定値としては記載しない（`engine/metal/src/engine/window.cpp:159-165`）。

`docs/MAC.md:281` は setup が resident IQ3_S / Q2_0 pack で ON にすると記述している。現行コード上は setup が `STRATA_METAL_F16` を書くのではなく、engine が未設定時に pack 名から自動選択する。setup が config の `env` に入れるのは `STRATA_METAL_STREAM` である（`engine/metal/setup_mac.py:593-598`）。

## 根拠

- `engine/metal/src/engine/window.cpp:159-195` — fp16 経路、環境値の parse/cache、自動判定、入力形式と function constant。
- `engine/metal/src/engine/window.cpp:714-740, 791-798, 834-841` — model open、stream 判定後の自動選択、Metal library と buffer の初期化。
- `engine/metal/src/engine/window.cpp:1046-1057, 1353-1354, 1560-1565` — GEMV・expert の適用条件と decode window の制限。
- `engine/metal/src/engine/msl_libs.h:25-29` — fp16 選択時の Metal library prelude。
- `engine/metal/setup_mac.py:593-598` — setup が config に書く環境変数。
