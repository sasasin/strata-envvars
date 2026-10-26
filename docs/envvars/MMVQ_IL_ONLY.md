# `MMVQ_IL_ONLY`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

CUDA の合成データ検査ツール `mmvq_il_parity` が実行するケースを、ケース名の部分一致で絞ります。Strata エンジンの推論・decode 経路から読む環境変数ではありません。この実行ファイルは `STRATA_BUILD_TESTS` と `STRATA_ENABLE_CUDA` が有効な場合に限り CMake で追加されます。

## 値と判定

値は数値や真偽値として parse されず、`std::strstr(c.name, only)` に渡されます。

| 状態 | 対象ケース |
|---|---|
| 未設定 | `CASES` 配列の全ケース |
| 設定済み | `c.name` に値の文字列が含まれるケース |
| 空文字（設定済み） | 空文字列は各ケース名に含まれるため、全ケース |
| 一致する名前がない値 | どのケースも実行しない |

照合は大文字小文字を区別する部分一致です。空白除去、値の正規化、複数パターンの解釈はありません。たとえば `MMVQ_IL_ONLY=Q6_K` は名前に `Q6_K` を含むケースを選び、`q6_k` は一致しません。

## 有効になる条件

`STRATA_BUILD_TESTS` と `STRATA_ENABLE_CUDA` の両方を有効にして `mmvq_il_parity` をビルド・実行する必要があります。通常の Strata 実行ファイルにはこの読み取り経路はありません。`--bench` は別途コマンドライン引数で制御され、この環境変数はケース選択だけを変えます。

## 実行時の詳細

`main()` が起動時に `getenv()` で一度値を取得し、`CASES` を順に走査して各ケース名を部分一致判定します。プロセス起動後の環境変更を再読込する処理はありません。一致したケースでは通常どおり、合成重み・入力を使って plain `native_mmvq` と interleaved `native_mmvq_il` の出力を比較し、`--bench` 指定時は timing も実行します。

このフィルターはテーブル検査 `check_tables()` の後に適用されるため、ケースを絞ってもテーブル検査は実行されます。一致するケースがなくてもケースループは空になりますが、`check_tables()` の結果を含む終了判定と、`--bench --emit-table` による表出力は行われます。終了時の固定メッセージはケースを絞った場合も `mmvq_il_parity: OK (every case, T 1-8, rows 1/2/4 and the table, bitwise)` のままで、実際に全ケースを実行したことを示す表示にはなりません。

## 根拠

- `CMakeLists.txt:268` で始まる `STRATA_BUILD_TESTS` 節の中で、同ファイル `:1097-1102` は `STRATA_ENABLE_CUDA` 条件下に `mmvq_il_parity` を実行ファイルおよび CTest として登録しています。
- `src/kernels/mmvq_il_parity.cpp:298-310` で起動引数から bench/table 出力を決め、テーブル検査後に `MMVQ_IL_ONLY` を読み、ケース名を `strstr` で選別し、最終メッセージと終了コードを決めます。
- `src/kernels/mmvq_il_parity.cpp:83-109,123-147,150-187` は選ばれたケースの合成入力、比較、benchmark 処理を示します。各ケース名は同ファイル `:37-71` に定義されています。
- `docs/MMVQ_IL_TABLE.md:22-25` はこのツールをカード別テーブル測定に使う手順を説明しています。資料中に `MMVQ_IL_ONLY` の説明はありません。
