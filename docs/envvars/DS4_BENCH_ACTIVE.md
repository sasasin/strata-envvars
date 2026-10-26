# `DS4_BENCH_ACTIVE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`ds4_iq_test` の `--bench-big` ベンチマークで、各 layer の plan に残す expert 数を制限するテスト用フックです。値を `na` とすると、各 layer の expert index `na` 以上の plan entry を 0（空 entry）にします。Strata の通常実行バイナリでは参照されず、製品エンジンの expert 選択を変える設定ではありません。

## 値と判定

コードは設定値を `std::atoi` で `int` に変換し、範囲検査や clamp をせずに使います。

| 状態・値 | 結果 |
|---|---|
| 未設定 | plan を変更しない。6 expert すべての entry が残る。 |
| 空文字、数字で始まらない文字列 | `atoi` が 0 を返すため、index 0 以上をすべて空にする。 |
| 数字で始まる文字列 | 先頭の整数として変換する。たとえば `2tail` は 2 として扱われる。 |
| `na <= 0` | expert index 0〜5 のすべてを空にする。 |
| `1 <= na <= 5` | index 0〜`na-1` を残し、index `na`〜5 を空にする。 |
| `na >= 6` | どの entry も空にしない。 |

先頭の空白と符号は `atoi` の変換規則に従います。数値として解釈できない文字列をエラーとして報告する処理はありません。`int` で表現できない値の動作はこのコードで定義・検査されていません。

## 有効になる条件

この変数を読むのは `tests/dsv41/iq_expert_test.cpp` の `bench_big()` だけで、同プログラムの `--bench-big` オプションから呼ばれます。CMake では `STRATA_NATIVE_EXPERTS` の条件下で GPU runtime とリンクする `ds4_iq_test` として定義されています。したがって通常の `strata-dsv41` 実行には適用されません。

別変数 `DS4_BENCH_WIN` が設定されていると、`--bench-big` は window/grouped-entry 経路も使います。`DS4_BENCH_ACTIVE` はその場合も `gate_up` / `down` に渡す各 layer の plan entry を先に空にします。

## 実行時の詳細

`bench_big()` は `NE = 6` として各 layer の plan を構築します。環境変数が設定されていれば、その関数の実行時に一度 `getenv()` し、`atoi()` の結果を `na` にして全 layer の `k = na` から `NE - 1` までの entry を 0 にします。設定値を benchmark 中に読み直す処理はありません。0 でない確保済み plan entry だけを最後に `hipFree()` します。

ベンチマークは `gate_up` と `down` を計時し、標準出力に `big ... ws ... gate/up ... down ...` の行を出します。出力する推定 byte 数 `bg` / `bd` は `NE`（6）全件を前提に計算され、`DS4_BENCH_ACTIVE` による空 entry 数を反映しません。そのため一部 entry を空にして測定した場合、表示上の GB/s や Tw/s は有効 entry だけの実効転送量としては読めません。

## 根拠

- `tests/dsv41/iq_expert_test.cpp:224-240` — `bench_big()` の `NE`, plan 構築、および環境変数の変換と空 entry 化。
- `tests/dsv41/iq_expert_test.cpp:250-274` — plan の切替、`gate_up` / `down` の計時、固定 `NE` に基づく出力 byte 数、確保済み entry の解放。
- `tests/dsv41/iq_expert_test.cpp:352-358` — `--bench-big` から `bench_big()` を呼ぶ処理。
- `CMakeLists.txt:845-883` — `STRATA_NATIVE_EXPERTS` 条件内でのテスト実行ファイル `ds4_iq_test` の定義。
- `docs/DETAILS.md` にこの変数の説明はありません。
