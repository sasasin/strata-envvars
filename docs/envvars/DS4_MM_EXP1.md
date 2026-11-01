# `DS4_MM_EXP1`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリ・GPU driver の挙動は対象外。

## 役割

Metal backend の DSV41 IQ expert down 行列カーネル経路で、`total_rows × n_embd × 4 + 4096` byte の Metal buffer を追加で確保する開発・実験用フックです。確保した buffer は down カーネルの引数にも結果コピーにも渡されず、実装上の計算結果を切り替えません。追加の GPU buffer 確保とその後の保持によるメモリ消費が主な実際の影響です。

## 値と判定

値の内容は parse されず、`std::getenv("DS4_MM_EXP1")` の戻り値が null かどうかだけを見ます。

| 状態 | 分岐 | 結果 |
|---|---|---|
| 未設定 | false | この追加 buffer を確保しない |
| 空文字を含む設定済みの値 | true | 追加 buffer を確保する |
| その他すべての文字列 | true | 追加 buffer を確保する |

`0` / `false` を含め、値による無効化・数値変換・境界判定・fallback はありません。`mm_set()` の各 down 呼び出しで環境を読み直し、static cache はありません。

## 有効になる条件

- `STRATA_METAL` のビルドで、`src/dsv41/ds4_iq.cu` の `set_down()` が `hbounds != nullptr` のとき Metal host の `iq_set_dn()` を先に呼び出す経路です。Metal host が成功を返すと通常の down kernel launch には進みません。
- `mm_set()` は `n_exp <= 0` または `total_rows <= 0` なら先に成功を返し、環境変数を調べません。また IQ block size が 0、次元の 256/128 境界条件不一致、stride 不一致、Metal 準備失敗、tile が空の場合も分岐に到達しないか、通常経路へ戻る条件になります。
- `mm_set(false, ...)` の down 側だけで評価されます。gate/up 側はこの変数を読みません。
- CLI 引数や他の環境変数との優先順位はありません。

## 実行時の詳細

`DS4_MM_EXP1` が設定されていると、down 側で一度 `g_mm_ys` を `by` に入れた後、上記サイズを `g_cx->alloc()` して `by` とローカル変数 `hy` をその buffer に置き換えます。しかし、その後の dispatch は引き続き `g_mm_ys` を引数にし、結果を engine の出力へコピーする箇所も `g_mm_ys` を読みます。置き換え後の `hy` は以降参照されません。そのため、この設定によって結果先や計算値が切り替わる処理は確認できません。

新規 buffer は `Context::alloc()` が保持ハンドルを返しますが、この分岐では `g_cx->free()` を呼ばず、ローカル `by` の寿命終了時にも解放処理はありません。従って呼び出しごとに確保分が保持され続けます。確保に失敗した場合は `Context::alloc()` が stderr に `mtl: alloc <bytes> failed` を出して `exit(4)` します。変数固有のログや警告はありません。

## 根拠

- `src/dsv41/ds4_iq.cu:1604-1608` — Metal build の `set_down()` が bounds のある場合に `iq_set_dn()` を先行呼び出し。
- `metal/src/engine/ds4_finish.cpp:2476-2495` — `mm_set()` の引数、早期条件、tile 作成。
- `metal/src/engine/ds4_finish.cpp:2575-2596` — down 側の環境変数判定と追加確保、および dispatch 引数が依然 `g_mm_ys` であること。
- `metal/src/engine/ds4_finish.cpp:2619-2632` — down 結果のコピー元も `g_mm_ys` であること。
- `metal/src/mtl_rt.mm:547-565` — Metal buffer の確保、ゼロ初期化、保持ハンドルの返却。
- `metal/src/mtl_rt.mm:670-695` — 明示的な `Context::free()` の解放処理。この変数分岐からは呼び出されない。
- `docs/DETAILS.md` に本変数の説明は見つかりませんでした。
