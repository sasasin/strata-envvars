# `STRATA_Q2_BITPLANE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象は Strata 所有のソースコードと `docs/DETAILS.md`。外部ライブラリの環境変数動作は対象外。

## 役割

Q2_0 の CPU 行積カーネルで、従来の行カーネルに代えて bit-plane 形式の AVX2 または AVX1 カーネルを選びます。環境変数は Q2_0 の計算方式を変え、浮動小数点の加算順序も変わるため、従来方式と最下位側の結果が異なることがあります。GPU カーネルや AVX-512 の Q2_0 カーネルを切り替える設定ではありません。

## 値と判定

AVX2 実装と AVX1 実装のそれぞれが、ファイル内の `static const bool kBitplane` 初期化時に `std::getenv()` を読み、値の先頭1文字だけを検査します。全文字列の数値変換や trim はありません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字列 | 無効（設定値はあるが先頭文字が `\0`） |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

大文字小文字や後続文字は判定に影響しません。値の読み取りは各カーネル実装の静的初期化時に一度だけ行われるため、初期化後にプロセス環境を変更しても反映されません。

## 有効になる条件

- Q2_0 の CPU 行処理が AVX2 または AVX1 の分岐に到達する必要があります。通常の行 dispatcher は AVX-512 対応時には AVX-512 カーネルを先に選ぶため、この変数は AVX-512 経路には適用されません。
- bit-plane 活性化データの作成は AVX2/AVX1 の activation quantizer 内で、この変数が有効な場合に限って行います。`nchunks`（`n / 32`）が 4 の倍数でない場合は画像を作らず、従来カーネルを使います。通常の Q2_0 入力長では、これは長さが 128 要素の倍数でない場合に該当します。
- 行カーネル側でも Q2_0 の block 数が偶数であり、各 activation に対応する bit-plane pair が用意されている場合だけ bit-plane 計算を実行します。条件を満たさなければ従来の AVX2/AVX1 行カーネルへ戻ります。
- 通常の `generate` では、canonical pack の CPU カーネルは AVX-512 要件の確認を通ります。一方、native pack は AVX-512 がなくても CPU カーネルを使う経路があり、native Q2_0 行処理は `q2_rows_any()` から AVX2、次いで AVX1 を選びます。したがって、AVX-512 のない CPU での実行可否は pack と経路にも依存します。
- `q2_avx1.cpp` は x86 向けのビルド分岐で追加されます。AVX2 実装も x86 CPU カーネルの一部です。

## 実行時の詳細

AVX2/AVX1 の activation quantizer は通常の量子化データを作った後、設定が有効なら bit-plane 用データ（並べ替えた活性値、部分和、scale 配列）も構築します。Q2_0 行カーネルは 64 値ブロックを2個ずつ処理できる場合に bit-plane 配列を使います。それ以外では legacy 関数に委譲します。AVX2 と AVX1 の両方に同じ環境変数判定があり、AVX2 分岐が優先されます。

bit-plane カーネルでは整数積の集計は従来方式と同じ意図ですが、浮動小数点の和の順序が異なります。コードコメントはそのため結果の最下位側が変化すると明記しています。`docs/DETAILS.md` もこの設定が Q2_0 の最下位ビットを変えると説明しています。測定値や一般的な速度向上は、参照した資料には記載がないためここでは示しません。

この環境変数を設定するだけで利用者向けログは出ません。テスト専用の `q2_bitplane_parity` は環境変数未設定時にエラー文字列を出しますが、通常のカーネル経路には同様の設定ログはありません。

## 根拠

- `src/kernels/cpu/q2_avx2.cpp:65-85,146-189,197-227,229-269`: AVX2 bit-plane 計算の説明、先頭文字による設定判定、pair 条件・fallback、activation 画像作成。
- `src/kernels/cpu/q2_avx1.cpp:125-127,178-181,183-213,232-252,254-292`: AVX1 実装と同じ判定、画像作成条件、行カーネルの fallback。
- `src/kernels/cpu/expert_layout.cpp:348-365`: Q2_0 行処理と activation quantizer の AVX-512 → AVX2 → AVX1 dispatcher。
- `src/kernels/cpu/pool.cpp:637-658`: native Q2_0 pack の gate/up/down 行処理から `q2_rows_any()` を呼ぶ箇所。
- `src/program/generate.cpp:2774-2783`: canonical pack は CPU expert support を要求し、AVX-512 のない native pack では使用カーネルをログに示す処理。
- `CMakeLists.txt:1269-1291,1564-1569`: x86 向け AVX1 実装のビルド条件と、テスト時に `STRATA_Q2_BITPLANE=1` を設定する定義。
- `docs/DETAILS.md:272-274`: AVX2・AVX-512 非対応 CPU での Q2_0 用スイッチとして記載。現在のソースには AVX1 実装もあり、対象は AVX2 のみに限られません。
