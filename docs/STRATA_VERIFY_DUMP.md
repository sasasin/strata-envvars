# `STRATA_VERIFY_DUMP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL エンジンのプロファイル済み expert cache を全件検証するとき、最初に見つかった不一致について、GPU キャッシュから読み戻した内容と GGUF の内容を比較できるようにバイナリファイルへ保存する診断用フックである。キャッシュの選択、読み込み、修復を変える設定ではない。

## 値と判定

| 環境変数の状態 | 動作 |
| --- | --- |
| 未設定 | ダンプしない。 |
| 空文字を含む、何らかの値が設定済み | 値をディレクトリ名として使い、最初の不一致についてダンプを試みる。値の文字列比較、数値変換、空文字検査はない。 |

各ファイルのパスは文字列を加工せず、`<値>/slot<slot番号>.got` と `<値>/slot<slot番号>.want` を連結して作る。`.got` は GPU スロットから読み戻したバイト列、`.want` は GGUF から読み込んだ期待値である。ファイルの長さはその expert の blob サイズ。

そのため `STRATA_VERIFY_DUMP=0` は無効化値ではなく、`0/slotN.got` 等を指す。空文字なら `/slotN.got` 等の絶対パスになる。ディレクトリの作成、末尾区切りの調整、パス検証は行わない。`fopen` が失敗してもエラーを出さず、`fwrite` の戻り値も確認しない。

## 有効になる条件

- 対象コードは `sycl/src/program/generate.cpp` の SYCL 実装である。
- プロファイルがあり expert source が存在し、かつ GGUF からのパイプライン fill が選ばれる必要がある。この経路は `srcp == &gguf_src` かつ per-layer admission ではなく、`STRATA_FILL_SERIAL` が未設定の場合に選ばれる。
- その fill 経路で `STRATA_VERIFY_ALL_SLOTS` が設定されていると、各 filled slot を GGUF と照合する検証関数が登録される。ここも設定値の内容ではなく設定有無で判定するため、空文字でも検証が有効になる。
- `STRATA_VERIFY_ALL_SLOTS` が未設定なら、`STRATA_VERIFY_DUMP` だけを設定してもダンプ処理には到達しない。

## 実行時の詳細

検証関数は fill 直後と session up 時に呼び出される。各呼び出しで不一致数を 0 から数え、最初の不一致（その呼び出し中の `bad == 1`）に限って `STRATA_VERIFY_DUMP` を読み、`.got` と `.want` の保存を試す。環境変数は関数登録時に固定されず、不一致処理のたびに `getenv` される。従ってプロセス内で値が変更された場合、以後の不一致処理では新しい値を参照する。

比較結果と不一致の位置・バイト数、および全 slot の不一致数は標準エラーに出力される。ダンプできなかった場合の専用ログや終了処理はない。検証関数は不一致を検出してログを出すが、この変数による処理は不一致の修正や実行中断を行わない。

## 根拠

- `sycl/src/program/generate.cpp:4633-4648` — プロファイル fill の検証関数と、GGUF pipeline fill を選ぶ条件。
- `sycl/src/program/generate.cpp:4704-4747` — `STRATA_VERIFY_ALL_SLOTS` による検証関数の登録、slot ごとの GGUF 比較、最初の不一致時のダンプ、標準エラー出力。
- `sycl/src/program/generate.cpp:5336-5338` — session up 時にも検証関数を呼ぶ箇所。
- `docs/INTEL.md:745-755` — Intel SYCL の expert cache の不具合調査で `STRATA_VERIFY_ALL_SLOTS`、`STRATA_VERIFY_FIND`、`STRATA_VERIFY_DUMP` を使った経緯。これは調査例であり、上記の値判定や書き込み挙動は実装を根拠とした。
