# `MMVQ_IL_TMIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

CUDA の interleaved MMVQ parity / benchmark ツール `mmvq_il_parity` が検査・計測する token 列数 `T` の下限を指定します。通常の Strata 推論エンジンが読む設定ではありません。ツールの `run_case()` で `T` のループ開始値に使われ、上限は別の `MMVQ_IL_TMAX`（未設定時 8）が決めます。ツールを benchmark モードで起動したときは対象 `T` ごとの `BENCH` 計測にも影響します。

## 値と判定

値は文字列全体の検証なしに `std::atoi()` で `int` に変換されます。空文字は未設定扱いではなく `atoi("")` の結果 0 です。先頭の空白と符号の後に数字があれば数字の部分を読み、後続文字列は無視します。数値として始まらない文字列は 0 になります。

| `MMVQ_IL_TMIN` | `t_min` | ループへの影響（既定の `MMVQ_IL_TMAX=8` の場合） |
|---|---:|---|
| 未設定 | 1 | `T=1..8` を処理 |
| `3` | 3 | `T=3..8` を処理 |
| 空文字、`x`、`0x` | 0 | `T=0..8` を処理。0 は拒否・補正されない |
| `-2` | -2 | `T=-2..8` を処理。負値を拒否・補正しない |
| `4tail` | 4 | `T=4..8` を処理。末尾は検査しない |
| `9` | 9 | `t_min > t_max` となり、`T` ループを実行しない |

`T` ごとにベクトル長や出力バイト数を `T` から計算して CUDA API と kernel 関数へ渡します。従って 0 や負値は有効な token 数へ clamp されません。負値はベクトル長計算で `std::size_t` に変換される箇所もあり、実行時の確実な結果はソースから保証できません。`atoi` の範囲外入力も実装側で検査されません。

## 有効になる条件

- `mmvq_il_parity` 実行ファイルがビルドされて実行される場合に限ります。CMake ではテスト構成内の CUDA 有効時に target と test が登録されます（`CMakeLists.txt:333,1215-1220`）。
- `MMVQ_IL_TMIN` は `run_case()` の各 case ごとに読み取られます。`MMVQ_IL_ONLY` が設定され、case 名に合致しない場合、その case は呼ばれず値も読み取られません。
- 先頭引数 `--bench` の有無は `T` の走査範囲を変えません。`--bench` がある場合、走査した `T` について parity 比較に加えて benchmark の計測・`BENCH` 行の出力を行います。
- CLI 引数で `MMVQ_IL_TMIN` を上書きする仕組みや、他の設定との優先順位はありません。`MMVQ_IL_TMAX` は独立して上限を定め、CLI の `--rounds` 等はこの下限を変更しません。

## 実行時の詳細

`run_case()` は `MMVQ_IL_TMAX` を読み、その後 `MMVQ_IL_TMIN` を読み、`for (int T = t_min; T <= t_max; ++T)` を走らせます。読み取りは `run_case()` の呼び出しごとに行われ、static cache はありません。起動前に設定した環境値がその呼び出しで使われます。通常の単一スレッド実行では各 case の前に読み直されますが、実行中にプロセス環境を変更する仕組みはこのツールにはありません。

各 `T` について、入力・出力領域を確保し、参照 `native_mmvq` と `native_mmvq_il` の結果を比較します。不一致または非有限の参照値は `FAIL ... T=...` を表示し、`bad` を増やします。CUDA 確保エラーは `CUDA: malloc ...` 等を表示して case を失敗扱いにします。最後に `bad` が 0 なら `mmvq_il_parity: OK (every case, T 1-8, rows 1/2/4 and the table, bitwise)`、そうでなければ `mmvq_il_parity: FAIL` を表示し、終了コード 0 / 1 を返します。最終 OK 文言の `T 1-8` は固定文字列で、環境変数に合わせて変化しません。走査が空でも `bad` が 0 なら OK 側になります。

関連資料 `docs/MMVQ_IL_TABLE.md` は、この実行ファイルをカード別の interleaved MMVQ parity 確認とテーブル測定に使う手順を説明しています。同資料の通常の測定例は `T=1..8` を対象にし、`MMVQ_IL_TMIN` 自体の値の規則は説明していません。

## 根拠

- `src/kernels/mmvq_il_parity.cpp:1-25`: 専用 parity / benchmark ツールであること、`MMVQ_IL_TMIN` と `MMVQ_IL_TMAX` が `T` を制限する旨。
- `src/kernels/mmvq_il_parity.cpp:154-185`: 各 case での環境読み取り、`atoi`、既定値 1、上限とのループ条件。
- `src/kernels/mmvq_il_parity.cpp:186-207,224-243,246-279`: `T` を使った領域サイズ・kernel 引数、比較、失敗表示、benchmark 計測。
- `src/kernels/mmvq_il_parity.cpp:470-525`: `--bench` 判定、`MMVQ_IL_ONLY` による case 選択、最終表示と終了コード。
- `CMakeLists.txt:333,1215-1227`: テスト構成かつ CUDA 有効時の target/test 登録。
- `docs/MMVQ_IL_TABLE.md:24-35`: parity 実行ファイルの手動測定・確認用途。
