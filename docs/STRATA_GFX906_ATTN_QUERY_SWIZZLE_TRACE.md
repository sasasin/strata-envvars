# `STRATA_GFX906_ATTN_QUERY_SWIZZLE_TRACE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

gfx906 向け HIP 互換ビルドで、batched QSA attention の query-swizzle カーネルを実際に選ぶ条件が成立しているかを stderr に診断表示します。この変数自身はカーネル選択や計算結果を変えません。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | ログを出さない |
| 空文字を含む任意の設定値 | ログを有効にする |

値の文字列や数値は parse せず、`std::getenv(...) != nullptr` だけを見ます。関数内の `static const bool` に保存されるため、プロセス内で最初に `qsa_decode_attn_batch()` がこの判定箇所まで到達した時点の設定が使われ、その後の環境変更は反映されません。

## 有効になる条件

この読み取りとログは `STRATA_HIP_GFX906` 定義時に限られます。CMake の `STRATA_HIP_GFX906` ビルドは CUDA ソースを HIP gfx906 互換バックエンドとしてコンパイルする設定です。通常の CUDA、wave32 HIP、CPU 経路にはこの診断コードがありません。

関数がバッチを処理するには `n_q > 0` で、形状と必要バッファが有効である必要があります。`n_q <= 0` は先に return し、不正な形状やバッファは stderr にエラーを出して終了するため、いずれもこの診断行には到達しません。

## 実行時の詳細

`qsa_decode_attn_batch()` は、診断とは独立に `use_query_swizzle` を計算します。query-swizzle が実際に有効 (`active=1`) になるには、次のすべてが必要です。

- `STRATA_GFX906_ATTN_QUERY_SWIZZLE` が設定され、先頭文字が `1`。文字列全体の比較ではないため `1abc` も有効、空文字や `true` は無効です。この判定も関数内 static に保存されます。
- `STRATA_ATTN_LANECELL` の先頭文字が `1` でない。lane-cell が有効なら query-swizzle は使いません。
- KV pool が `kv_mode == 1`。コード上、これは `k_q` が存在し、`k_q4` がなく、`v_q4` との組み合わせによる mode 2/3 にも該当しない場合です。
- 呼び出しスレッドの現在の HIP device が `gfx906` で wavefront 幅64。device ordinal が変わった場合はプロパティを取り直し、HIP API エラー時は無効として扱います。

診断が有効な場合、各呼び出しスレッドで最初に条件を通った一回だけ、次の形式で stderr に出します（`active` は上記の実際の選択条件の結果です）。

```text
strata attn-query-swizzle: active=%d nq=%lld cap=%lld kv_mode=%d lane_cell=%d
```

`nq` は query 数、`cap` は attention の capacity、`kv_mode` と `lane_cell` はその呼び出しで選択に使う値です。出力済みフラグは `static thread_local` なので、複数スレッドから呼べばスレッドごとに一度ずつ出力されます。関数自体は prefill、verification、MTP の batched attention 経路から呼ばれます。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:618-650`: 早期 return / 入力検査、KV mode、環境変数の読み取り、実際の有効条件、診断ログ。
- `src/kernels/cuda/qsa_decode_attn.cu:547-572`: gfx906 と wave64 の確認、device ordinal ごとのスレッドローカル cache、HIP エラー時の fail-closed。
- `src/kernels/cuda/qsa_decode_attn.cu:660-701`: query-swizzle カーネルと通常経路の分岐。
- `CMakeLists.txt:59-71,122-138`: gfx906 HIP 互換ビルド条件と `STRATA_HIP_GFX906` 定義。
- 呼び出し箇所: `src/prefill/prefill.cpp:2848`、`src/core/verify.cpp:1376,1391`、`src/core/mtp.cpp:825`。
- `docs/AMD_HIP.md:465-477` は gfx906 ビルドを別の opt-in ビルドとして説明しています。診断変数の説明や測定値は同資料にありません。
