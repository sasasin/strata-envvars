# `DS4_MM_BIG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、表示された変更はありません。

## 役割

DeepSeek V4.1 の Metal prompt chunk expert GEMM が使う scratch buffer `g_mm_hs` と `g_mm_ys` の確保サイズに、64 MiB の下限を設けます。これらの buffer が必要サイズに足りず再確保されるときに効きます。`g_mm_xs` のサイズには適用されません。

## 値と判定

値の内容は parse されず、`std::getenv("DS4_MM_BIG")` が null かどうかだけを調べます。

| 状態 | `g_mm_hs` / `g_mm_ys` の要求サイズ |
|---|---|
| 未設定 | `必要サイズ + floor(必要サイズ / 4)` |
| 設定あり（空文字を含む） | 上記サイズと 64 MiB（67,108,864 bytes）の大きい方 |

したがって `1` など特定の文字列は要求されず、空文字や `0` を含む任意の設定値で下限が有効です。符号、数値変換、範囲 clamp はありません。各 buffer は未確保、または現在の確保量が必要サイズより小さい場合だけ解放・再確保されます。既に十分なサイズの buffer がある場合、この変数は読み直されてもサイズを変えません。

## 有効になる条件

- `STRATA_METAL` ビルドの DeepSeek V4.1 経路でのみ、`ds4_iq.cu` が `iq_set_gu()` / `iq_set_dn()` を呼びます。さらに呼び出し側の `hbounds` が null でない必要があります。
- `mm_set()` に到達しても、`n_exp` と `total_rows` が正、量子化型が対応し、`n_embd` と `n_ff` が 256 の倍数などの検査を通らなければ、buffer の確保まで進みません。
- gate/up の処理では `g_mm_hs` と `g_mm_ys`、down の処理では `g_mm_ys` が対象です。down は先行する gate/up によって `g_mm_hs_ok` が立っていることも要求します。
- CLI 引数や別の環境変数による優先順位・上書きは、この変数の読み取り箇所にはありません。

## 実行時の詳細

`DS4_MM_BIG` は `mm_set()` の buffer 再確保分岐ごとに評価され、static cache はありません。ただし buffer は関数外の grow-only scratch として保持されるため、実際に環境値がサイズへ反映されるのは再確保が必要になった時点です。gate/up は `g_mm_hs` を確保して利用可能状態にし、down は `g_mm_ys` を確保して結果を保存し、dispatch 後に結果を engine の行へコピーします。

この変数専用のログや警告はありません。Metal `Context::alloc()` が buffer を確保できない場合は stderr に `mtl: alloc %zu failed` を出し、終了コード 4 でプロセスを終了します。`mm_set()` の通常の条件不成立は呼び出し側で別の kernel 経路へ進む構造ですが、allocation 失敗は `alloc()` 内で終了するため、その fallback にはなりません。

## 根拠

- 候補一覧に名前があること: `docs/envvars/000_envvers.md:227`。
- Metal buffer と関数の定義、`mm_set()` の形状・型チェック: `metal/src/engine/ds4_finish.cpp:2453-2487`。
- `g_mm_hs` と `g_mm_ys` の再確保および `DS4_MM_BIG` の3箇所: `metal/src/engine/ds4_finish.cpp:2559-2573,2584-2595`。
- `iq_set_gu()` / `iq_set_dn()` が `mm_set()` に渡す処理: `metal/src/engine/ds4_finish.cpp:2637-2643`。
- `STRATA_METAL` 条件、`hbounds != nullptr` の呼び出しと失敗時の通常 kernel 経路: `src/dsv41/ds4_iq.cu:1585-1620`。
- allocation 失敗時の stderr と終了処理: `metal/src/mtl_rt.mm:547-579`。

`docs/DETAILS.md` と関連文書には `DS4_MM_BIG` の説明を確認できませんでした。上記は調査対象 commit のソースコードに基づく記述です。
