# `PC_GEMM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の standalone `prompt_chain` テストプログラムで、出力幅が 64 を超える dense GEMM のカーネルタイル `(tm, tn)` を指定します。読み取り箇所は `metal/tests/prompt_chain.cpp` だけです。Metal engine の通常の prompt 経路にも GEMM はありますが、同じ環境変数は読まず、エンジン側の `gemm` は固定タイルを選びます。したがって `PC_GEMM` は通常の `strata` 実行の設定ではありません。

## 値と判定

`main()` が `std::getenv("PC_GEMM")` を一度呼び、そのポインターを後続の GEMM lambda が使います。環境変数が未設定なら各 GEMM で `tm=64`、`tn=(Nn <= 64 ? 32 : 64)` です。設定されている場合でも上書き対象は `Nn > 64` の GEMM に限られます。

その GEMM では `std::sscanf(gk_env, "%d,%d", &tm, &tn)` を呼びます。戻り値を確認せず、範囲検証・clamp・無効値時の fallback もありません。

| 入力状態 | `Nn > 64` の `tm`, `tn` |
| --- | --- |
| unset | `64`, `64` |
| 空文字 | 変換なし。初期値 `64`, `64` のまま |
| 例 `32,16` | `32`, `16` |
| 例 `32` または `32,x` | 先頭の変換だけ成功し、`32`, `64` |
| 先頭の整数変換に失敗 | 初期値 `64`, `64` のまま |
| 例 `32,16junk` | 2つの整数を読み、後続の文字列は検査しない |
| `Nn <= 64` | 環境変数の有無や値にかかわらず、`64`, `32` のまま |

`%d` は符号付き整数変換で、先頭の空白を読み飛ばします。書式中のカンマはその位置に必要です。たとえば `32 ,16` はカンマの直前に空白があるため2つ目まで変換できず、`tm=32`, `tn=64` になります。0 や負数を含め、変換された整数の有効範囲は検査されません。

## 有効になる条件

- `metal/tests/prompt_chain.cpp` の `prompt_chain` を実行し、GEMM を組み立てること。ソースの先頭コメントにある用途は、GGUF 重みを使った prompt 処理時間の計測です。
- Metal のテスト群は `metal/CMakeLists.txt` が `metal/tests/*.cpp` を個別の executable として登録しており、同 CMakeLists は Apple 以外では構成を停止します。
- GEMM ごとに `Nn > 64` の場合だけ `PC_GEMM` の値がタイル選択に反映されます。CLI 引数による上書きはありません。
- 通常の Metal engine 側 `metal/src/engine/prompt_chain.inc` の `gemm` は `tm=64` および幅に応じた `tn=32` / `64` を固定しており、`PC_GEMM` を参照しません。テストプログラムと engine の挙動を混同しないでください。

## 実行時の詳細

テストプログラムは初期値を置いた後、`PC_GEMM` が設定され、かつ GEMM の出力幅が 64 を超えるときだけ `sscanf` でタイル値を読みます。選んだ値で `gemm_f16_<tm>_<tn>_4` という Metal function 名を作り、dispatch grid の幅を `(Nn + tn - 1) / tn`、高さを `(M + tm - 1) / tm` として、その GEMM を dispatch に加えます。値はプログラム起動後、バッファ準備と kernel compile を経た後に一度読み取られ、その後の GEMM 群で使われます。別スレッド等が環境を書き換えた場合の再読込はありません。

タイル値に対応する Metal function が見つからない場合、`Context::pipeline_uncached()` は stderr に `mtl: no function <関数名> <詳細>` を出し、終了コード 3 で終了します。function は見つかっても pipeline 作成に失敗すれば、`mtl: pipeline <関数名>: <詳細>` を出して同じく終了コード 3 です。値の検証がないため、存在しないタイルや不正な寸法を与えた場合の成功は保証されません。

## 根拠

- `metal/tests/prompt_chain.cpp:1-6`: テストプログラムの用途と起動形式。
- `metal/tests/prompt_chain.cpp:57-83`: CLI 引数、モデルファイル読込、開始時の診断出力。
- `metal/tests/prompt_chain.cpp:98-112`: Metal kernel compilation と pipeline helper。
- `metal/tests/prompt_chain.cpp:228-235`: 唯一の `PC_GEMM` 読み取り、parse、kernel 名と dispatch grid。
- `metal/tests/prompt_chain.cpp:490-505,511-554`: 生成済み dispatch の実行、warm-up、計測出力。
- `metal/CMakeLists.txt:13-18,32-48`: Apple 限定の Metal CMake project とテスト executable の登録。
- `metal/src/mtl_rt.mm:472-509`: function / pipeline の失敗ログと終了処理。
- `metal/src/engine/prompt_chain.inc:165-171`: 通常の Metal engine prompt GEMM は固定タイルで、`PC_GEMM` を読まない。
- `docs/envvars/000_envvers.md:485`: 候補一覧への掲載。候補一覧だけでは実利用範囲を示さない。
