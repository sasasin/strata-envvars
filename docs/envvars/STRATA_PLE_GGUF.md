# `STRATA_PLE_GGUF`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

PLE の parity 検査プログラム `ple_parity` が参照する GGUF ファイルのパスを指定します。通常の `strata` 推論プロセスの設定ではなく、CUDA と SYCL の開発・検証用実行ファイルに限った入力指定です。GGUF 内の PLE テーブルを開き、期待する行数・ファイルサイズやテーブル読み出し結果を検査します。

## 値と判定

環境変数の値を文字列としてそのままパスに使います。数値変換、前後空白の除去、値の形式検証はありません。

| 状態 | 初期パス |
|---|---|
| unset | `../../Q2_0/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf` |
| 設定あり（空文字を含む） | 環境変数の文字列そのもの。空文字なら空のパスを使い、既定パスには戻らない |

起動引数 `--gguf F` が指定されると、その `F` が環境変数または既定パスを上書きします。複数回指定した場合は引数処理ループで最後に指定された値が残ります。`--gguf` の直後に値がない場合は有効な指定として消費されず、usage を stderr に出して終了コード 2 になります。

根拠: `src/kernels/ple_parity.cpp:252-269`、`sycl/src/kernels/ple_parity.cpp:301-318`。

## 有効になる条件

- CUDA 側では `src/kernels/ple_parity.cpp` から作られる `ple_parity`、SYCL 側では `sycl/src/kernels/ple_parity.cpp` から作られる同名の parity 実行ファイルが対象です。CMake のテスト登録もこの実行ファイルを使用します（`CMakeLists.txt:976-991`、`sycl/CMakeLists.txt:296-306`）。通常の Strata 推論経路がこの環境変数を読む箇所はありません。
- `--selftest` または `--check-fixtures` のときは、選択したパスを `PleTable::open()` で開き、行数と正確なファイルサイズも事前確認します。失敗時は `ple_parity: required PLE table is missing or incompatible: <パス> (<エラー>)` を stderr に出し、終了コード 2 です。
- 上記フラグを付けない通常の parity 実行でも、後段で同じパスを `PleTable::open()` に渡し、テーブル行を読み出して検査します。
- SYCL の CMake テストでは、CMake キャッシュ変数 `STRATA_PLE_GGUF` が空でなければ `--gguf <値>` を実行引数に加えます。これは環境変数とは別の設定ですが、実行時には `--gguf` が環境変数より優先されます。CUDA の CMake テスト登録はここで `--gguf` を追加していないため、実行環境の `STRATA_PLE_GGUF` またはプログラムの既定パスが使われます。

根拠: `src/kernels/ple_parity.cpp:275-307,456-489`、`sycl/src/kernels/ple_parity.cpp:324-355,505-538`、`CMakeLists.txt:984-991`、`sycl/CMakeLists.txt:299-306`。

## 実行時の詳細

`main()` の冒頭で `std::getenv("STRATA_PLE_GGUF")` を調べ、値があれば `std::string` にコピーします。判定と値取得で `getenv` は二度呼ばれます。その後コマンドライン引数を順に処理し、`--gguf` があればパスを置き換えます。従ってパスはプロセス起動時に決まり、実行中の環境変更は再読込されません。

選択されたパスは `PleTable::open()` に渡されます。同関数はファイルを開き、`per_layer_token_embd.weight` の存在、形状、対応する型などを検査します（`src/kernels/ngram.cpp:230-278`）。その後 `ple_parity` はこの GGUF からテーブル行を読み、期待値との比較に使います。環境変数はファイル選択を行うだけで、GGUF の内容や PLE 計算方式を変更しません。

既定の相対パスは実行時のカレントディレクトリから解決されます。CMake の CUDA/SYCL parity テストは Strata ソースツリーを working directory に指定していますが、手動実行時は利用者のカレントディレクトリが基準です。

## 文書との照合

`docs/INTEL.md:194-198` は `ple_parity` に Q2_0 shard 2 GGUF が必要で、SYCL の CMake 設定 `-DSTRATA_PLE_GGUF=...` で指定できると説明しています。ソースでは加えて、実行時の `STRATA_PLE_GGUF` と `--gguf` による選択、ならびに `--gguf` が優先することを確認できます。

## 根拠

- `src/kernels/ple_parity.cpp:252-269,275-307,456-489`
- `sycl/src/kernels/ple_parity.cpp:301-318,324-355,505-538`
- `src/kernels/ngram.cpp:230-278`
- `CMakeLists.txt:976-991`、`sycl/CMakeLists.txt:296-306`
- `docs/INTEL.md:194-198`
