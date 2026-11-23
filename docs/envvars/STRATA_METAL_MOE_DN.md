# `STRATA_METAL_MOE_DN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal のモデル本体 MoE down カーネルのタイル構成 `L,R,S`（1 行あたりの lanes、lane あたりの rows、simdgroups）を指定し、既定の構成を上書きする。`Window::layer()` が `moe_down_<type>_<L>_<R>_<S>` という関数名と dispatch の threadgroup 数を組み立てるために使う。ルーティングや選ばれる expert、重み、生成結果をこの値で選択する処理はない（`engine/metal/src/engine/window.cpp:1290-1294, 1338-1355, 1372-1375, 1404-1413`）。

この読み取りは `engine/metal` の Metal 実装だけにあり、同 CMake 設定は macOS 専用の別プロジェクトとしている（`engine/metal/CMakeLists.txt:1-9`）。CUDA / HIP / SYCL 実装の設定としては使われない。

## 値と判定

| 条件 | 未設定・空文字・形式不一致 | 3整数を読み取れた場合 |
|---|---|---|
| Metal `Window::layer()` で down tensor が Q2_0 以外 | 型ごとの既定値を使う | `L,R,S` で既定値を上書き |
| down tensor が Q2_0 | `8,1,4` 相当の既定値を使う | 変数は読み取られるが適用しない |

解析は関数内 static lambda が `std::getenv(name)` の値に `std::sscanf(e, "%d,%d,%d", ...)` を実行し、変換数が 3 の場合だけ成功とする。したがって未設定、空文字、3つ目まで変換できない文字列は上書きしない。各 `%d` は符号付き10進整数を読むが、正数・許容範囲・カーネル実装との整合性は検査しない。大文字小文字比較はなく、値は文字列でなく整数として変換される。先頭の空白は `%d` が読み飛ばす一方、カンマは書式中の文字なので区切り位置に必要。3つ目の整数の後ろは書式に指定がないため検査されず、例えば `4,2,4suffix` や `4,2,4,extra` も3変換として受理される。`1,2,x` や `1;2;3` は受理されない（`engine/metal/src/engine/window.cpp:1343-1351`）。

既定の `L,R` は down tensor の型と `m5_layout()` で決まり、`S` は常に 4。Q2_0 では `L=8,R=1`。それ以外では `L=8` となるのは M4 layout かつ Q8_0 の場合で、他は `L=4`。`R=1` となるのは Q2_0、または M4 layout で Q8_0 / Q5_1 / Q5_0 の場合で、他は `R=2`。解析成功時に Q2_0 以外で3値すべてを置き換える（`engine/metal/src/engine/window.cpp:1338-1352`）。

負値や 0 も `sscanf` 上は3変換として受理されるが、意味のあるタイル値としての保証はない。値は `N / (S * (32 / L) * R)` の計算と `tg[0] = 32 * S` に使われ、`L=0` や積が 0 になる入力では整数除算が成立しない。正の値でもビルド済み Metal 関数名が存在する保証はない（`engine/metal/src/engine/window.cpp:1353-1355, 1372-1375, 1410`）。

## 有効になる条件

- Metal エンジンを使い、モデル本体の `Window::layer()` が MoE 層を構築すること。Metal engine は専用プロジェクトで、`STRATA_METAL_ENGINE` が ON のときに組み込まれる（`engine/metal/CMakeLists.txt:103-108`）。
- down tensor が Q2_0 以外であること。Q2_0 のときは読み取り結果を down タイルへ反映せず既定値を使う（`engine/metal/src/engine/window.cpp:1333, 1341-1352`）。
- 初回の `Window::layer()` 呼び出し時に得られた環境値がそのプロセスの static 解析結果になること。変数を実行中に変更しても再解析されない（`engine/metal/src/engine/window.cpp:1344-1349`）。
- 有効な整数値を指定した場合も、対応する `moe_down_<type>_<L>_<R>_<S>` 関数が Metal library に存在し、タイル計算が成立する必要がある。別の環境変数や CLI 引数によるこの値の優先上書きは、この処理にはない（`engine/metal/src/engine/window.cpp:1343-1355, 1374-1375, 1404-1413`）。

## 実行時の詳細

`Window::layer()` は各層の MoE gate/up/down tensor と型を調べ、down tensor の型から既定タイルを選んだ後に環境変数を評価する。解析状態と3整数は関数内 `static` なので、初回到達時の値がプロセス内で共有され、後続層や別の `Window` でも再読込されない。値は down pipeline 名に埋め込まれ、threadgroup 数と grid 次元の計算に使われる（`engine/metal/src/engine/window.cpp:1311-1355, 1372-1413`）。

各 Window は `run()` が window 形状の dispatch graph を初めて組み立てたときに `layer()` を呼ぶ。構築済み形状の再利用時はキャッシュした dispatch を実行するため、環境変数の値を後から変えても反映されない（`engine/metal/src/engine/window.cpp:1489-1492, 1530-1558, 1561-1576, 1614`）。バッチ行も `run_rows()` から `run()` に入る（同 `:1644-1666`）。

## ログと測定値

正常な解析・上書きについて、この変数専用のログ出力はない。指定値に対応する Metal 関数が見つからない場合は `mtl::Context::pipeline()` が `mtl: no function %s %s\n` を stderr に出して終了コード 3 で終了し、関数は見つかったが pipeline 作成に失敗した場合は `mtl: pipeline %s: %s\n` を出して同じく終了コード 3 で終了する（`engine/metal/src/mtl_rt.mm:229-265`）。`L` などに 0 を指定した場合の除算失敗は、この環境変数用の検査や診断経路を通らない（`engine/metal/src/engine/window.cpp:1353-1355`）。

この変数の値ごとの性能・正確性測定値は、調査対象ソースから確認できないため記載しない。

## 根拠

- `engine/metal/src/engine/window.cpp:1311-1355` — MoE down tensor、型別既定タイル、環境変数の解析と適用、タイル計算。
- `engine/metal/src/engine/window.cpp:1372-1413` — down pipeline 名と dispatch の構成。
- `engine/metal/src/engine/window.cpp:1489-1492, 1530-1558, 1561-1576, 1614, 1644-1666` — Window graph 構築・再利用、および batch rows の経路。
- `engine/metal/src/mtl_rt.mm:229-265` — Metal function / pipeline の失敗ログと終了。
- `engine/metal/CMakeLists.txt:1-9, 103-108` — Metal 実装の platform/build 範囲。
