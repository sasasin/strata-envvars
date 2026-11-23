# `ROCM_KPACK_PATH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata はこの環境変数を設定済みかどうかだけ確認し、未設定の場合に、実行ファイルの隣にある `kpack/` 内の `.kpack` アーカイブを列挙して `ROCM_KPACK_PATH` に設定します。呼び出し元が設定した値は変更しません。Strata 内では値を解釈したり、ライブラリがその値を使ったか検証したりする処理はありません。実装は `strata::core::kpack_path::apply` です。エンジンでは HIP 系 macro を持つ非 Windows ビルドの起動時、画像リーダーでは HIP 版の非 Windows 起動時に呼ばれます（`engine/include/strata/core/kpack_path.hpp:63-75`、`engine/src/program/generate.cpp:3736-3763`、`terminal/tools/vision/strata_vision.cpp:17-20,53-55`）。

## 値と判定

Strata は値を数値や真偽値として parse せず、`std::getenv(...) != nullptr` で設定の有無だけを見ます。したがって空文字も「設定あり」です。変数が設定済みなら内容が `""`、`0`、`1`、`true`、その他の文字列のいずれでもそのまま残し、Strata は検証しません。CLI 引数による上書きはありません（`engine/include/strata/core/kpack_path.hpp:65-75`）。

| 条件 | unset | 設定済み（空文字を含む） | Strata が自動設定する値 |
|---|---|---|---|
| 非 Windows の対応 HIP 実行経路 | 実行ファイル隣の `kpack/` に対象ファイルがあれば一覧を設定。なければ未設定のまま | 既存値を変更しない | `kpack/` の正規ファイル名が `.kpack` で終わるものをファイル名順に並べ、フルパスを `:` で連結 |
| Windows、または対応する HIP 経路以外 | Strata はこの変数を設定しない | この機能による読み取り・変更なし | なし |

自動設定用の列挙では、`kpack/` が開けない場合、空の場合、または対象ファイルがない場合は空文字列を返して何もしません。名前が6文字以下の項目と `.` で始まる項目を除外し、末尾 `.kpack` の比較は大文字小文字を区別します。`stat` が成功し通常ファイルと判定した項目だけを採用します。連結文字列のエスケープや内容検証はありません（`engine/include/strata/core/kpack_path.hpp:25-46`）。

## 有効になる条件

- エンジンでは `STRATA_USE_HIP` または `STRATA_HIP_GFX906` が定義され、かつ Windows 以外である必要があります。`--version`、`--families`、`--geometry`、`--expert-support` の早期終了経路では、この設定ブロックに到達しません（`engine/src/program/generate.cpp:3717-3735,3736-3764`）。
- 画像リーダーでは `STRATA_VISION_HIP` が定義され、かつ Windows 以外である必要があります。呼び出しは引数解析より前なので、`--gpu` の有無には依存しません。CMake はこの macro を HIP 版 `strata-vision-hip` に付けます（`terminal/tools/vision/strata_vision.cpp:53-55,61-70`、`terminal/tools/vision/CMakeLists.txt:84-90`）。
- 実行ファイルの位置を特定でき、隣に `kpack/` と列挙対象のファイルがある場合に限り、未設定値が自動設定されます。Linux 以外の非 Windows で `/proc/self/exe` を読めない場合も、実行ファイル位置が空となるため自動設定されません（`engine/include/strata/core/kpack_path.hpp:49-60`）。
- `STRATA_TRACE` が設定されている（空文字でも可）場合に限り、エンジンが自動設定した値をログに出します。これは記録条件だけを変え、`ROCM_KPACK_PATH` の選択には影響しません（`engine/src/program/generate.cpp:3761-3763`）。

## 実行時の詳細

`apply(pkg_dir)` の呼び出しごとに現在のプロセス環境を読みます。static cache はありません。エンジンの通常経路では早期終了オプションの判定後、HIP 系 macro を持つ非 Windows 用の起動処理内で一度呼ばれます。画像リーダーでは HIP 版の `main` の引数解析前に一度呼ばれます。このため Strata が設定するのは各プロセス内の環境であり、親プロセスの環境を書き換えません（`engine/src/program/generate.cpp:3696-3735,3745-3763`、`terminal/tools/vision/strata_vision.cpp:36-55`）。

値が未設定なら `exe_dir()` が `/proc/self/exe` から実行ファイルのフォルダーを求め、`list_for()` がその `kpack/` を走査します。列挙結果が空でなければ `setenv("ROCM_KPACK_PATH", ..., 0)` を呼びます。設定済みの値を上書きしない指定です。`setenv` の戻り値は確認されず、失敗時も明示的なエラーや終了にはならず、列挙値を呼び出し元へ返します。そのため trace 条件も満たす場合、実際に環境へ設定できたかにかかわらず返却値がログに出る経路があります（`engine/include/strata/core/kpack_path.hpp:49-75`、`engine/src/program/generate.cpp:3761-3763`）。

既存値がある場合や自動列挙が空の場合は、Strata による変更もこの変数に関するログもありません。値の解釈後に Strata が行う分岐、エラー終了、fallback はありません。外部ライブラリが設定値をどう解釈するかは本調査の対象外です。

## ログと測定値

エンジンは自動設定値が空でなく、かつ `STRATA_TRACE` が設定されている場合、stderr に次の形式で出します（文字列は実装どおり）。既存値は `apply()` が空文字列を返すため、このログには出ません。

```text
strata trace: ROCM_KPACK_PATH=<自動列挙した値>
```

画像リーダー側にはこの値に関するログがありません。対象環境変数に関する測定値も Strata の資料から確認できません（`engine/src/program/generate.cpp:3761-3763`、`terminal/tools/vision/strata_vision.cpp:53-55`）。

## 根拠

- `engine/include/strata/core/kpack_path.hpp:25-46` — パッケージ内アーカイブの列挙、除外、並べ替え、連結。
- `engine/include/strata/core/kpack_path.hpp:49-75` — 実行ファイル位置の取得、設定有無の判定、環境への設定。
- `engine/src/program/generate.cpp:3696-3735,3745-3764` — エンジンの早期終了と HIP/Linux 起動経路、trace ログ。
- `terminal/tools/vision/strata_vision.cpp:17-20,36-55` — HIP 画像リーダーでの include と起動時呼び出し。
- `terminal/tools/vision/CMakeLists.txt:84-90` — HIP 画像リーダーへの `STRATA_VISION_HIP` 定義。
- `tools/packaging/build_hip_linux.sh:104-119` — Linux パッケージへ `kpack/` を構成する処理。これはパッケージングの根拠であり、外部ライブラリの実行時挙動を示すものではありません。
