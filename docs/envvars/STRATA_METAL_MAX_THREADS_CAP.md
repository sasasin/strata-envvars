# `STRATA_METAL_MAX_THREADS_CAP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal runtime が各 compute pipeline に対して保持する `max_threads` を、環境変数で指定した上限まで下げます。Metal が実際に報告した上限を変更する機能ではなく、Strata 側の dispatch 検査を意図的に厳しくするテスト用フックです。ヘッダーのコメントも「この検査を確認する test hook」と説明しています。

対象の `mtl_rt` は、Metal エンジンと Metal parity / bench プログラムで共有されています。Metal ビルドは macOS 専用です。

## 値と判定

値は `std::atoi()` で整数に変換されます。文字列全体の検証はしません。先頭の空白と符号を含む10進整数部分を変換し、整数の後ろに文字があってもその部分は判定に使われません。数値に変換できない文字列や空文字は `atoi` の結果が `0` です。

| 状態・値 | 処理 |
|---|---|
| 未設定 | Metal pipeline が報告した `maxTotalThreadsPerThreadgroup` をそのまま `max_threads` にする |
| `atoi` の結果が 0 以下 | 上限を変えない（空文字、`abc`、`0`、負数など） |
| 正数で、pipeline の報告値より小さい | `max_threads` をその正数に下げる |
| pipeline の報告値以上 | 上限を変えない |

例として `16tail` は `16` として扱われます。変数が設定されていても、値が正数で各 pipeline の実上限より小さくなければ効果はありません。

## 有効になる条件

- `metal/src/mtl_rt.mm` の `Context::pipeline()` で作成する pipeline にだけ作用します。Metal エンジンはこの `mtl_rt` をリンクし、pipeline をキャッシュして利用します。parity / bench の実行ファイルも同じライブラリを使います。
- Metal ビルドが必要です。`metal/CMakeLists.txt` は macOS 以外で configure を失敗させます。
- `metal/src/gpu/runtime.cpp` にある別の Metal runtime の dispatch 上限検査は、この変数を参照せず、Metal API の `maxTotalThreadsPerThreadgroup` を直接使います。この変数の設定値でその別経路の上限が変わるわけではありません。

## 実行時の詳細

Metal が pipeline を作成した後、Strata は実上限を `Pipeline::max_threads` に保存し、その時点で `getenv()` を呼んで cap を適用します。環境変数の結果を static cache には保存しませんが、既に作成された pipeline の値は後から変更されません。エンジンでは pipeline がキャッシュされるため、変更値が反映されるのはその後に新規作成される pipeline です。

`mtl::require_fit()` は dispatch の threadgroup サイズが `max_threads` を超えると stderr に kernel 名、上限、GPU 名、dispatch 箇所、要求 thread 数を出して `exit(6)` します。エンジンでは graph 構築時にこの検査を呼びます。これにより、上限を故意に低くしたときにも、Metal が上限超過 dispatch を黙って飛ばして誤答になる前に停止できます。

## 根拠

- `metal/src/mtl_rt.mm:131-146`: Metal pipeline 作成後に実上限を読み、`atoi()` の結果が正かつ実上限より小さい場合だけ `p.max_threads` に適用。
- `metal/src/mtl_rt.mm:159-169`: 超過 dispatch の stderr 出力と終了コード 6。
- `metal/src/mtl_rt.h:24-29,62-69`: `Pipeline` の上限フィールド、テスト用フックの説明、および dispatch サイズの検査。
- `metal/src/engine/window.cpp:150-175,426-444`: エンジンの pipeline cache、graph build 時の `require_fit()` 呼び出し、Metal `Context` と pipeline を使う初期化。
- `metal/CMakeLists.txt:1-17,32-47,103-123`: macOS 専用ビルド、`mtl_rt` を使う parity / bench とエンジンの構成。
- `metal/src/gpu/runtime.cpp:600-621`: 別の GPU runtime の検査は Metal API の実上限を直接参照し、この環境変数は読まない。

`docs/DETAILS.md` にこの変数の説明や関連測定値は見つかりませんでした。したがって、この文書では測定値や性能効果を述べていません。
