# `STRATA_GRP_KEEP_GOING`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP 用の standalone 検証プログラム `gr_parity` で、2 グループに分けた QFUSE parity 検査が不一致を見つけた後も、残りの token 数・反復回数の検査を続けるかを切り替えます。通常の生成 engine、server、model 設定を変える環境変数ではありません。候補名の全参照を確認したところ、実際の環境読み取りは `engine/src/kernels/gr_parity.cpp` の `fused_multi_lds_parity()` にある一箇所だけです（同 `:607`）。同ファイルの `:605` は説明コメント、`terminal/data/settings-register.json:12121-12131` は設定レジストリのメタデータで、いずれも追加の読み取り箇所ではありません。CMake は CUDA または HIP の GPU engine 内に `gr_parity` target を定義し、同名の CTest を登録します（`engine/cmake/strata_gpu_engine.cmake:8,1005-1008`）。

## 値と判定

`std::getenv("STRATA_GRP_KEEP_GOING") != nullptr` の真偽だけを使います。環境変数が未設定なら `false`、設定されていれば中身にかかわらず `true` です。文字列比較・数値変換・trim・大小文字の正規化・範囲検査はありません（`engine/src/kernels/gr_parity.cpp:607`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `gr_parity` の2グループ検査に到達 | 継続しない（最初の失敗後、後続の反復と token 数を止める） | 空文字、`0`、`false`、`1`、` 1`、任意の非空文字列。いずれも継続する | なし。設定値に「無効」と判定される文字列はない |

この変数に数値的な境界値はありません。`STRATA_GRP_REPS` はこの検査の反復数を別に決めますが、本変数との優先順位・上書き関係はありません（同 `:606-607`）。

## 有効になる条件

- CUDA または HIP の GPU engine を構成して `gr_parity` をビルド・実行していること。target 定義は `STRATA_BUILD_TESTS` の条件内ではなく、`strata_gpu_engine()` が GPU backend 有効時にだけ target 群を定義します（`engine/CMakeLists.txt:631`; `engine/cmake/strata_gpu_engine.cmake:6-8,1005-1008`）。
- 実行が `fused_multi_lds_parity()` の `if (!v3)` 節に到達すること。`v3` は `STRATA_GR_V3` を `atoi` で判定した関数内 `static` 値です。`main()` は `STRATA_GR_V3` が未設定の場合だけ `"0"` を設定します。従って `STRATA_GR_V3` の変換結果が非ゼロなら本変数は読まれず、未設定、空文字、`atoi` が 0 を返す値などでは対象節に入ります（`engine/src/kernels/gr_parity.cpp:340-342,745-750,604-607`）。
- `--selftest` はこの検査を有効化する条件ではありません。引数なしでも検査に進み、`--selftest` は全検査が成功した場合の `gr_parity OK` 表示だけを制御します。これら以外の引数は stderr に `usage: gr_parity [--selftest]` を出して終了コード 2 で戻るため、本変数は読みません（同 `:752-756,1089-1093`）。
- この検査は固定形状・合成入力で動き、モデル状態や server モードには依存しません（同 `:598-620,758-785`）。

## 実行時の詳細

`fused_multi_lds_parity()` の先行する検査を終え、`STRATA_GR_V3` が false の場合に、2 グループ検査へ入る時点で一度だけ `getenv` します。値を関数内 `const bool` に保持し、外側の `T=2..8` と内側の反復ループの継続条件に使います。したがって読み取り前にプロセス環境を変更すればその時点の値が参照されますが、読み取り後に変更してもこの呼び出し中の判定は変わりません。static cache ではなく、リクエスト単位の読み取りでもありません（同 `:604-607,621-643`）。

未設定時は、`g2bad` が増えた反復内の処理を終えると、ループ条件 `(!g2bad || keep_going)` が偽になり、次の反復と後続の `T` を実施しません。設定時は `g2bad` が増えても `T=2..8` の各サイズと `STRATA_GRP_REPS` 回数まで続け、検出した失敗を累積します。`STRATA_GRP_REPS` 未設定時の反復数は 200、設定時は `max(1, atoi(value))` です（同 `:606,621-643`）。この検査は group-relative / window-indexed の出力比較、counter 残留、書き込み範囲などを確認します（同 `:653-714`）。

この変数は検査結果を成功扱いにしたり、比較方法・GPU kernel・生成結果を変えたりしません。`g2bad` は関数の `bad` に加算され、`main()` は最終失敗数を表示し、失敗があれば終了コード 1 を返します（同 `:721-740,1089-1093`）。

## ログと測定値

この環境変数自体を示す有効化ログ・警告・エラーはありません。検査終了時の標準出力は、書式文字列 `  fused GR read + q8_1 (STRATA_QFUSE), a window of two groups, T 2..8, %ld runs (%d random inputs each T), group-relative and window-indexed, direct and graph: %s\n` に従い、最後の `%s` は `FAIL` または `pass` です。不一致時には、たとえば `QFUSE two groups: T=%d rep %d: counter %zu left at %u\n` や `QFUSE two groups (window-indexed): T=%d rep %d: token %d (group %d) differs\n` も出力します（同 `:669-692,721-723`）。総失敗数は `gr_read/gr_write: N failures` として表示され、`N` が 0 以外なら終了コード 1 です（同 `:1090-1093`）。この変数の効果に関する測定値は、確認したソースおよび `docs/DETAILS.md` にありません。

## 根拠

- `engine/src/kernels/gr_parity.cpp:598-607` — 対象の2グループ検査、`STRATA_GR_V3` 条件、`STRATA_GRP_REPS` と本変数の読み取り。
- `engine/src/kernels/gr_parity.cpp:621-643,653-714` — 失敗後の継続条件、反復、比較と失敗カウント。
- `engine/src/kernels/gr_parity.cpp:721-740,745-756,1089-1093` — 要約出力、CLI 引数、終了コード。
- `engine/cmake/strata_gpu_engine.cmake:6-8,1005-1008`; `engine/CMakeLists.txt:631` — GPU backend の target と CTest 登録。
